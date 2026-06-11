"""Exporters for sending trace data to storage."""

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import Trace
from .privacy import get_masker, PIIMasker

logger = logging.getLogger(__name__)


class Exporter(ABC):
    """Base exporter interface."""

    def __init__(self, pii_masker: Optional[PIIMasker] = None):
        self.pii_masker = pii_masker

    @abstractmethod
    def export(self, trace: Trace) -> bool:
        """Export a trace. Returns True on success."""
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush any buffered data."""
        pass

    def _apply_pii_mask(self, trace: Trace) -> Trace:
        """Apply PII masking to a trace if enabled."""
        if not self.pii_masker or not self.pii_masker.enabled:
            return trace

        # Mask input/output data
        for span in trace.spans:
            if span.input_data is not None:
                span.input_data = self.pii_masker.mask_data(span.input_data)
            if span.output_data is not None:
                span.output_data = self.pii_masker.mask_data(span.output_data)
            if span.attributes:
                span.attributes = self.pii_masker.mask_data(span.attributes)

        # Mask metadata
        if trace.metadata:
            trace.metadata = self.pii_masker.mask_data(trace.metadata)

        return trace


class ConsoleExporter(Exporter):
    """Exports traces to console (for debugging)."""

    def __init__(self, pretty_print: bool = True, pii_masker: Optional[PIIMasker] = None):
        super().__init__(pii_masker=pii_masker)
        self.pretty_print = pretty_print

    def export(self, trace: Trace) -> bool:
        trace = self._apply_pii_mask(trace)
        if self.pretty_print:
            print(json.dumps(trace.to_dict(), indent=2, default=str))
        else:
            print(json.dumps(trace.to_dict(), default=str))
        return True

    def flush(self) -> None:
        pass


class BatchExporter(Exporter):
    """Buffers traces and exports them in batches."""

    def __init__(
        self,
        exporter: Exporter,
        batch_size: int = 10,
        flush_interval: float = 5.0,
        pii_masker: Optional[PIIMasker] = None,
    ):
        super().__init__(pii_masker=pii_masker)
        self.exporter = exporter
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer: List[Trace] = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._timer: Optional[threading.Timer] = None
        self._start_timer()

    def _start_timer(self):
        """Start periodic flush timer."""
        self._timer = threading.Timer(self.flush_interval, self._periodic_flush)
        self._timer.daemon = True
        self._timer.start()

    def _periodic_flush(self):
        """Periodically flush buffer."""
        with self._lock:
            if self._buffer and (time.time() - self._last_flush >= self.flush_interval):
                self._flush_internal()
        self._start_timer()

    def export(self, trace: Trace) -> bool:
        with self._lock:
            # Apply PII masking before buffering
            trace = self._apply_pii_mask(trace)
            self._buffer.append(trace)
            if len(self._buffer) >= self.batch_size:
                self._flush_internal()
        return True

    def _flush_internal(self) -> None:
        """Internal flush without lock (caller must hold lock)."""
        if not self._buffer:
            return

        traces_to_export = self._buffer.copy()
        self._buffer.clear()
        self._last_flush = time.time()

        for trace in traces_to_export:
            try:
                self.exporter.export(trace)
            except Exception as e:
                logger.error(f"Failed to export trace: {e}")
                # Re-add to buffer on failure
                self._buffer.insert(0, trace)

    def flush(self) -> None:
        with self._lock:
            self._flush_internal()
            if self._timer:
                self._timer.cancel()


class FileExporter(Exporter):
    """Exports traces to a JSONL file."""

    def __init__(self, filepath: str = "traces.jsonl", pii_masker: Optional[PIIMasker] = None):
        super().__init__(pii_masker=pii_masker)
        self.filepath = filepath
        self._file = open(filepath, "a", encoding="utf-8")

    def export(self, trace: Trace) -> bool:
        try:
            trace = self._apply_pii_mask(trace)
            line = json.dumps(trace.to_dict(), default=str)
            self._file.write(line + "\n")
            self._file.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to write trace to file: {e}")
            return False

    def flush(self) -> None:
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class HTTPEndpointExporter(Exporter):
    """Exports traces to an HTTP endpoint."""

    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/traces",
        api_key: Optional[str] = None,
        pii_masker: Optional[PIIMasker] = None,
    ):
        super().__init__(pii_masker=pii_masker)
        self.endpoint = endpoint
        self.api_key = api_key
        self._session = None

    def _get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                if self.api_key:
                    self._session.headers["Authorization"] = f"Bearer {self.api_key}"
                self._session.headers["Content-Type"] = "application/json"
            except ImportError:
                raise ImportError(
                    "requests library is required for HTTP exporter. "
                    "Install it with: pip install requests"
                )
        return self._session

    def export(self, trace: Trace) -> bool:
        try:
            trace = self._apply_pii_mask(trace)
            session = self._get_session()
            response = session.post(self.endpoint, json=trace.to_dict(), timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to export trace via HTTP: {e}")
            return False

    def flush(self) -> None:
        pass
