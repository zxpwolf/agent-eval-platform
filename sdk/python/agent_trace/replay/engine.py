"""Deterministic replay engine.

This module provides the core replay engine that can deterministically
reproduce agent executions using recorded logs and mock servers.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from ..models import Span, SpanType, Trace
from .controller import ReplayController, get_controller
from .mock_server import MockLLMServer, MockToolServer, get_mock_llm_server, get_mock_tool_server
from .models import RecordedCall, ReplayAction, ReplayLog, ReplayStatus
from .recorder import ExecutionRecorder, get_recorder

logger = logging.getLogger(__name__)


class ReplayEngine:
    """Core engine for deterministic replay of agent executions.

    The engine coordinates recording, mock servers, and replay control
    to enable exact reproduction of agent behavior.
    """

    def __init__(
        self,
        recorder: Optional[ExecutionRecorder] = None,
        controller: Optional[ReplayController] = None,
    ):
        self.recorder = recorder or get_recorder()
        self.controller = controller or get_controller()
        self._mock_llm: Optional[MockLLMServer] = None
        self._mock_tool: Optional[MockToolServer] = None

    def initialize_mock_servers(self, log: ReplayLog):
        """Initialize mock servers with a replay log."""
        self._mock_llm = MockLLMServer()
        self._mock_tool = MockToolServer()
        self._mock_llm.load_log(log)
        self._mock_tool.load_log(log)

    async def replay_trace(
        self,
        trace_id: str,
        log_id: Optional[str] = None,
        mock_llm: bool = True,
        mock_tools: bool = False,
        speed_multiplier: float = 1.0,
        preserve_timing: bool = True,
    ) -> Optional[str]:
        """Replay a recorded trace.

        Args:
            trace_id: The trace ID to replay
            log_id: Specific log ID (optional, will find by trace_id if not provided)
            mock_llm: Whether to use mock LLM responses
            mock_tools: Whether to use mock tool responses
            speed_multiplier: Playback speed (1.0 = real-time)
            preserve_timing: Whether to preserve original timing

        Returns:
            Session ID if replay started successfully, None otherwise
        """
        # Load the replay log
        if log_id:
            log = self.recorder.load_log(log_id)
        else:
            # Find log by trace_id
            logs = self.recorder.list_logs()
            matching_log = next((l for l in logs if l["trace_id"] == trace_id), None)
            if not matching_log:
                logger.error(f"No replay log found for trace {trace_id}")
                return None
            log = self.recorder.load_log(matching_log["log_id"])

        if not log:
            logger.error(f"Failed to load replay log for trace {trace_id}")
            return None

        # Create replay session
        session = self.controller.create_session(
            log=log,
            mock_llm=mock_llm,
            mock_tools=mock_tools,
            speed_multiplier=speed_multiplier,
            preserve_timing=preserve_timing,
        )

        # Start replay
        success = await self.controller.play(session.session_id)
        if not success:
            logger.error(f"Failed to start replay for session {session.session_id}")
            return None

        logger.info(f"Started replay for trace {trace_id}, session {session.session_id}")
        return session.session_id

    def compare_replays(
        self,
        session_id_1: str,
        session_id_2: str,
    ) -> Dict[str, Any]:
        """Compare two replay sessions to identify differences.

        Args:
            session_id_1: First session ID
            session_id_2: Second session ID

        Returns:
            Comparison results including differences in outputs, timing, etc.
        """
        session1 = self.controller.get_session(session_id_1)
        session2 = self.controller.get_session(session_id_2)

        if not session1 or not session2:
            return {"error": "One or both sessions not found"}

        comparison = {
            "session_1": {
                "id": session_id_1,
                "trace_id": session1.trace_id,
                "status": session1.status.value,
                "calls_count": len(session1.replayed_calls),
            },
            "session_2": {
                "id": session_id_2,
                "trace_id": session2.trace_id,
                "status": session2.status.value,
                "calls_count": len(session2.replayed_calls),
            },
            "differences": [],
        }

        # Compare call counts
        if len(session1.replayed_calls) != len(session2.replayed_calls):
            comparison["differences"].append({
                "type": "call_count",
                "session_1": len(session1.replayed_calls),
                "session_2": len(session2.replayed_calls),
            })

        # Compare outputs
        min_calls = min(len(session1.replayed_calls), len(session2.replayed_calls))
        for i in range(min_calls):
            call1 = session1.replayed_calls[i]
            call2 = session2.replayed_calls[i]

            if call1.get("output") != call2.get("output"):
                comparison["differences"].append({
                    "type": "output_mismatch",
                    "index": i,
                    "call_id_1": call1.get("call_id"),
                    "call_id_2": call2.get("call_id"),
                })

        return comparison

    def export_replay_log(
        self,
        trace: Trace,
        output_path: Optional[str] = None,
    ) -> Optional[str]:
        """Export a trace as a replay log.

        Converts a completed trace into a replay log format that can be
        used for deterministic replay.

        Args:
            trace: The trace to export
            output_path: Optional custom output path

        Returns:
            Log ID if successful, None otherwise
        """
        # Start recording
        log = self.recorder.start_recording(trace.trace_id)

        # Convert spans to recorded calls
        for span in trace.spans:
            if span.span_type == SpanType.LLM:
                self.recorder.record_llm_call(
                    trace_id=trace.trace_id,
                    span=span,
                    input_data=span.input_data,
                    output_data=span.output_data,
                )
            elif span.span_type == SpanType.TOOL:
                self.recorder.record_tool_call(
                    trace_id=trace.trace_id,
                    span=span,
                    input_data=span.input_data,
                    output_data=span.output_data,
                )
            elif span.span_type in (SpanType.FUNCTION, SpanType.CHAIN):
                self.recorder.record_function_call(
                    trace_id=trace.trace_id,
                    span=span,
                    input_data=span.input_data,
                    output_data=span.output_data,
                )

        # Set states
        self.recorder.set_initial_state(trace.trace_id, trace.metadata)
        self.recorder.set_final_state(trace.trace_id, {})

        # Stop recording and save
        saved_log = self.recorder.stop_recording(trace.trace_id)
        if saved_log:
            logger.info(f"Exported replay log {saved_log.log_id} for trace {trace.trace_id}")
            return saved_log.log_id

        return None


# Global engine instance
_default_engine: Optional[ReplayEngine] = None


def get_engine() -> ReplayEngine:
    """Get the global replay engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = ReplayEngine()
    return _default_engine


def set_engine(engine: ReplayEngine):
    """Set the global replay engine."""
    global _default_engine
    _default_engine = engine
