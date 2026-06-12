"""OTLP trace exporter for sending traces to OpenTelemetry collectors.

Exports agent traces as OTLP spans using the OpenTelemetry GenAI semantic
conventions, enabling integration with any OTLP-compatible backend
(Jaeger, Grafana Tempo, Honeycomb, Datadog, etc.).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from .models import Span, SpanType, Trace
from .otel_attributes import (
    GEN_AI_AGENT_NAME,
    GEN_AI_OPERATION_NAME,
    GEN_AI_REQUEST_MODEL,
    GEN_AI_SYSTEM,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
)
from .otel_mapper import span_type_to_otel_operation

logger = logging.getLogger(__name__)


@dataclass
class OTLPExporterConfig:
    """Configuration for the OTLP exporter."""
    endpoint: str = "http://localhost:4318/v1/traces"
    protocol: str = "http/json"
    headers: Dict[str, str] = field(default_factory=dict)
    timeout: float = 10.0
    resource_attributes: Dict[str, str] = field(default_factory=lambda: {
        "service.name": "agent-eval-platform",
        "service.version": "0.1.0",
    })
    max_batch_size: int = 50
    batch_timeout: float = 5.0


class OTLPExporter:
    """Export agent traces to an OTLP-compatible endpoint.

    Converts the platform's Trace/Span models into OTLP JSON format
    following the GenAI semantic conventions.

    Usage:
        config = OTLPExporterConfig(endpoint="http://jaeger:4318/v1/traces")
        exporter = OTLPExporter(config)
        exporter.export_trace(trace)
    """

    def __init__(self, config: Optional[OTLPExporterConfig] = None):
        self.config = config or OTLPExporterConfig()
        self._batch: List[Dict[str, Any]] = []
        self._last_flush_time = time.time()
        self._export_count = 0
        self._error_count = 0

    def export_trace(self, trace: Trace) -> bool:
        """Export a complete trace to the OTLP endpoint."""
        otlp_spans = self._convert_trace_to_otlp(trace)
        payload = self._build_otlp_payload(otlp_spans)

        success = self._send_payload(payload)
        if success:
            self._export_count += 1
        else:
            self._error_count += 1
        return success

    def export_span(self, span: Span, trace_id: str, trace_name: str = "") -> bool:
        """Export a single span."""
        otlp_span = self._convert_span_to_otlp(span, trace_id, trace_name)
        payload = self._build_otlp_payload([otlp_span])

        success = self._send_payload(payload)
        if success:
            self._export_count += 1
        else:
            self._error_count += 1
        return success

    def batch_export(self, trace: Trace) -> None:
        """Add a trace to the export batch.

        Traces are sent when the batch reaches max_batch_size or
        batch_timeout has elapsed. Call flush() to force-send.
        """
        otlp_spans = self._convert_trace_to_otlp(trace)
        self._batch.extend(otlp_spans)

        now = time.time()
        should_flush = (
            len(self._batch) >= self.config.max_batch_size
            or (now - self._last_flush_time) >= self.config.batch_timeout
        )
        if should_flush:
            self.flush()

    def flush(self) -> bool:
        """Flush any pending batched spans."""
        if not self._batch:
            return True

        payload = self._build_otlp_payload(self._batch)
        self._batch.clear()
        self._last_flush_time = time.time()
        return self._send_payload(payload)

    def get_stats(self) -> Dict[str, Any]:
        """Get exporter statistics."""
        return {
            "export_count": self._export_count,
            "error_count": self._error_count,
            "pending_batch_size": len(self._batch),
        }

    # ── Internal conversion ──────────────────────────────────

    def _convert_trace_to_otlp(self, trace: Trace) -> List[Dict[str, Any]]:
        """Convert a Trace to a list of OTLP spans."""
        return [
            self._convert_span_to_otlp(span, trace.trace_id, trace.name)
            for span in trace.spans
        ]

    def _convert_span_to_otlp(
        self,
        span: Span,
        trace_id: str,
        trace_name: str = "",
    ) -> Dict[str, Any]:
        """Convert a single Span to OTLP span format."""
        otlp_trace_id = self._to_hex_id(trace_id, 32)
        otlp_span_id = self._to_hex_id(span.span_id, 16)
        otlp_parent_span_id = ""
        if span.parent_span_id:
            otlp_parent_span_id = self._to_hex_id(span.parent_span_id, 16)

        # Determine operation name
        try:
            st = SpanType(span.span_type)
        except ValueError:
            st = SpanType.FUNCTION
        operation = span.otel_operation or span_type_to_otel_operation(st)

        # Build attributes
        attributes = self._build_span_attributes(span, operation, trace_name)

        # Timestamps to nanoseconds
        start_ns = int(span.start_time * 1e9) if span.start_time else 0
        end_ns = int(span.end_time * 1e9) if span.end_time else start_ns

        # Status mapping
        status_code = 1  # STATUS_CODE_OK
        status_message = ""
        if span.status == "error":
            status_code = 2  # STATUS_CODE_ERROR
            status_message = "error"

        otlp_span: Dict[str, Any] = {
            "traceId": otlp_trace_id,
            "spanId": otlp_span_id,
            "name": span.name or operation,
            "kind": 1,  # SPAN_KIND_INTERNAL
            "startTimeUnixNano": str(start_ns),
            "endTimeUnixNano": str(end_ns),
            "attributes": attributes,
            "status": {"code": status_code, "message": status_message},
        }

        if otlp_parent_span_id:
            otlp_span["parentSpanId"] = otlp_parent_span_id

        # Events
        if span.events:
            otlp_span["events"] = [
                {
                    "name": evt.name if hasattr(evt, 'name') else evt.get("name", "event"),
                    "timeUnixNano": str(int(
                        (evt.timestamp if hasattr(evt, 'timestamp') else evt.get("timestamp", 0)) * 1e9
                    )),
                    "attributes": self._dict_to_attributes(
                        evt.attributes if hasattr(evt, 'attributes') else evt.get("attributes", {})
                    ),
                }
                for evt in span.events
            ]

        return otlp_span

    def _build_span_attributes(
        self, span: Span, operation: str, trace_name: str
    ) -> List[Dict[str, Any]]:
        """Build OTLP attributes list from span data."""
        attrs: List[Dict[str, Any]] = []
        attrs.append(self._kv(GEN_AI_OPERATION_NAME, operation))

        if span.model:
            attrs.append(self._kv(GEN_AI_REQUEST_MODEL, span.model))
            system = span.model.split("/")[0] if "/" in span.model else "openai"
            attrs.append(self._kv(GEN_AI_SYSTEM, system))

        if span.prompt_tokens is not None:
            attrs.append(self._kv_int(GEN_AI_USAGE_INPUT_TOKENS, span.prompt_tokens))
        if span.completion_tokens is not None:
            attrs.append(self._kv_int(GEN_AI_USAGE_OUTPUT_TOKENS, span.completion_tokens))

        if trace_name:
            attrs.append(self._kv(GEN_AI_AGENT_NAME, trace_name))

        # Custom attributes
        if span.attributes:
            for key, value in span.attributes.items():
                if isinstance(value, str):
                    attrs.append(self._kv(key, value))
                elif isinstance(value, bool):
                    attrs.append(self._kv_bool(key, value))
                elif isinstance(value, (int, float)):
                    attrs.append(self._kv_int(key, int(value)))

        # Input/output (truncated)
        if span.input_data:
            input_str = json.dumps(span.input_data) if not isinstance(span.input_data, str) else span.input_data
            attrs.append(self._kv("gen_ai.input", input_str[:4096]))
        if span.output_data:
            output_str = json.dumps(span.output_data) if not isinstance(span.output_data, str) else span.output_data
            attrs.append(self._kv("gen_ai.output", output_str[:4096]))

        if span.cost is not None:
            attrs.append(self._kv("gen_ai.usage.cost", str(span.cost)))

        return attrs

    def _build_otlp_payload(self, spans: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build the full OTLP export payload."""
        resource_attrs = [
            self._kv(k, v) for k, v in self.config.resource_attributes.items()
        ]
        return {
            "resourceSpans": [
                {
                    "resource": {"attributes": resource_attrs},
                    "scopeSpans": [
                        {
                            "scope": {
                                "name": "agent-eval-platform",
                                "version": "0.1.0",
                            },
                            "spans": spans,
                        }
                    ],
                }
            ]
        }

    def _send_payload(self, payload: Dict[str, Any]) -> bool:
        """Send the OTLP payload to the configured endpoint."""
        try:
            body = json.dumps(payload).encode("utf-8")
            req = Request(
                self.config.endpoint,
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    **self.config.headers,
                },
            )
            with urlopen(req, timeout=self.config.timeout) as resp:
                if 200 <= resp.status < 300:
                    span_count = len(
                        payload.get("resourceSpans", [{}])[0]
                        .get("scopeSpans", [{}])[0]
                        .get("spans", [])
                    )
                    logger.debug(f"OTLP export succeeded: {span_count} spans")
                    return True
                else:
                    logger.error(f"OTLP export failed: HTTP {resp.status}")
                    return False
        except HTTPError as e:
            logger.error(f"OTLP export HTTP error: {e}")
            return False
        except URLError as e:
            logger.error(f"OTLP export URL error: {e}")
            return False
        except Exception as e:
            logger.error(f"OTLP export error: {e}")
            return False

    # ── Attribute helpers ────────────────────────────────────

    @staticmethod
    def _kv(key: str, value: str) -> Dict[str, Any]:
        return {"key": key, "value": {"stringValue": value}}

    @staticmethod
    def _kv_int(key: str, value: int) -> Dict[str, Any]:
        return {"key": key, "value": {"intValue": str(value)}}

    @staticmethod
    def _kv_bool(key: str, value: bool) -> Dict[str, Any]:
        return {"key": key, "value": {"boolValue": value}}

    @staticmethod
    def _to_hex_id(id_str: str, length: int) -> str:
        """Convert an ID string to a zero-padded hex string."""
        try:
            int_val = int(id_str, 16)
        except ValueError:
            import hashlib
            h = hashlib.md5(id_str.encode()).hexdigest()
            int_val = int(h[:length], 16)
        return format(int_val, f"0{length}x")[:length]

    @staticmethod
    def _dict_to_attributes(d: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert a dict to OTLP attributes list."""
        attrs = []
        for k, v in d.items():
            if isinstance(v, str):
                attrs.append(OTLPExporter._kv(k, v))
            elif isinstance(v, bool):
                attrs.append(OTLPExporter._kv_bool(k, v))
            elif isinstance(v, (int, float)):
                attrs.append(OTLPExporter._kv_int(k, int(v)))
            else:
                attrs.append(OTLPExporter._kv(k, str(v)))
        return attrs
