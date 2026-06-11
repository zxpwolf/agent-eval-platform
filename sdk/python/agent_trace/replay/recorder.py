"""Execution recorder for capturing agent runs for replay."""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import Span, SpanType, Trace
from .models import RecordedCall, ReplayAction, ReplayLog

logger = logging.getLogger(__name__)


class ExecutionRecorder:
    """Records agent execution for later replay.

    This recorder captures all external calls (LLM, tools, functions)
    and state changes during an agent run, creating a complete log
    that can be used for deterministic replay.
    """

    def __init__(self, storage_dir: str = "replay_logs"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._active_logs: Dict[str, ReplayLog] = {}

    def start_recording(self, trace_id: str, agent_config: Optional[Dict[str, Any]] = None) -> ReplayLog:
        """Start recording a new execution."""
        log = ReplayLog(
            trace_id=trace_id,
            log_id=str(uuid.uuid4()),
            agent_config=agent_config or {},
        )
        self._active_logs[trace_id] = log
        logger.info(f"Started recording for trace {trace_id}")
        return log

    def record_llm_call(
        self,
        trace_id: str,
        span: Span,
        input_data: Any,
        output_data: Any,
    ):
        """Record an LLM call."""
        log = self._active_logs.get(trace_id)
        if not log:
            logger.warning(f"No active log for trace {trace_id}")
            return

        call = RecordedCall(
            call_id=str(uuid.uuid4()),
            action_type=ReplayAction.LLM_CALL,
            timestamp=time.time(),
            duration_ms=span.duration_ms,
            input_data=input_data,
            output_data=output_data,
            model=span.model,
            prompt_tokens=span.prompt_tokens,
            completion_tokens=span.completion_tokens,
            span_id=span.span_id,
        )
        log.calls.append(call)

    def record_tool_call(
        self,
        trace_id: str,
        span: Span,
        input_data: Any,
        output_data: Any,
    ):
        """Record a tool call."""
        log = self._active_logs.get(trace_id)
        if not log:
            logger.warning(f"No active log for trace {trace_id}")
            return

        call = RecordedCall(
            call_id=str(uuid.uuid4()),
            action_type=ReplayAction.TOOL_CALL,
            timestamp=time.time(),
            duration_ms=span.duration_ms,
            input_data=input_data,
            output_data=output_data,
            span_id=span.span_id,
        )
        log.calls.append(call)

    def record_function_call(
        self,
        trace_id: str,
        span: Span,
        input_data: Any,
        output_data: Any,
    ):
        """Record a function call."""
        log = self._active_logs.get(trace_id)
        if not log:
            logger.warning(f"No active log for trace {trace_id}")
            return

        call = RecordedCall(
            call_id=str(uuid.uuid4()),
            action_type=ReplayAction.FUNCTION_CALL,
            timestamp=time.time(),
            duration_ms=span.duration_ms,
            input_data=input_data,
            output_data=output_data,
            span_id=span.span_id,
        )
        log.calls.append(call)

    def set_initial_state(self, trace_id: str, state: Dict[str, Any]):
        """Set the initial state for the execution."""
        log = self._active_logs.get(trace_id)
        if log:
            log.initial_state = state

    def set_final_state(self, trace_id: str, state: Dict[str, Any]):
        """Set the final state for the execution."""
        log = self._active_logs.get(trace_id)
        if log:
            log.final_state = state

    def stop_recording(self, trace_id: str) -> Optional[ReplayLog]:
        """Stop recording and save the log."""
        log = self._active_logs.pop(trace_id, None)
        if not log:
            return None

        # Save to file
        filepath = self.storage_dir / f"{log.log_id}.json"
        with open(filepath, "w") as f:
            json.dump(log.to_dict(), f, indent=2, default=str)

        logger.info(f"Saved replay log to {filepath}")
        return log

    def load_log(self, log_id: str) -> Optional[ReplayLog]:
        """Load a replay log from file."""
        filepath = self.storage_dir / f"{log_id}.json"
        if not filepath.exists():
            # Try finding by trace_id
            for f in self.storage_dir.glob("*.json"):
                with open(f, "r") as file:
                    data = json.load(file)
                    if data.get("trace_id") == log_id:
                        return ReplayLog.from_dict(data)
            return None

        with open(filepath, "r") as f:
            data = json.load(f)
            return ReplayLog.from_dict(data)

    def list_logs(self) -> List[Dict[str, Any]]:
        """List all available replay logs."""
        logs = []
        for filepath in self.storage_dir.glob("*.json"):
            with open(filepath, "r") as f:
                data = json.load(f)
                logs.append({
                    "log_id": data["log_id"],
                    "trace_id": data["trace_id"],
                    "created_at": data.get("created_at"),
                    "call_count": len(data.get("calls", [])),
                })
        return logs

    def delete_log(self, log_id: str) -> bool:
        """Delete a replay log."""
        filepath = self.storage_dir / f"{log_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False


# Global recorder instance
_default_recorder: Optional[ExecutionRecorder] = None


def get_recorder() -> ExecutionRecorder:
    """Get the global recorder instance."""
    global _default_recorder
    if _default_recorder is None:
        _default_recorder = ExecutionRecorder()
    return _default_recorder


def set_recorder(recorder: ExecutionRecorder):
    """Set the global recorder."""
    global _default_recorder
    _default_recorder = recorder
