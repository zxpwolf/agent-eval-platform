"""Replay controller for managing playback state and controls."""

import asyncio
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from .models import RecordedCall, ReplayAction, ReplayLog, ReplaySession, ReplayStatus
from .mock_server import MockLLMServer, MockToolServer, initialize_mock_servers

logger = logging.getLogger(__name__)


class ReplayController:
    """Controls the playback of recorded agent executions.

    Provides play, pause, step, and stop functionality similar to a video player,
    but for agent execution traces.
    """

    def __init__(self):
        self._sessions: Dict[str, ReplaySession] = {}
        self._logs: Dict[str, ReplayLog] = {}
        self._active_session: Optional[ReplaySession] = None
        self._replay_task: Optional[asyncio.Task] = None

    def create_session(
        self,
        log: ReplayLog,
        mock_llm: bool = True,
        mock_tools: bool = False,
        speed_multiplier: float = 1.0,
        preserve_timing: bool = True,
    ) -> ReplaySession:
        """Create a new replay session."""
        session = ReplaySession(
            session_id=str(uuid.uuid4()),
            trace_id=log.trace_id,
            log_id=log.log_id,
            mock_llm=mock_llm,
            mock_tools=mock_tools,
            speed_multiplier=speed_multiplier,
            preserve_timing=preserve_timing,
        )

        self._sessions[session.session_id] = session
        self._logs[log.log_id] = log

        # Initialize mock servers if needed
        if mock_llm or mock_tools:
            initialize_mock_servers(log)

        logger.info(f"Created replay session {session.session_id} for trace {log.trace_id}")
        return session

    def get_session(self, session_id: str) -> Optional[ReplaySession]:
        """Get a replay session by ID."""
        return self._sessions.get(session_id)

    async def play(self, session_id: str) -> bool:
        """Start or resume replay."""
        session = self._sessions.get(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return False

        if session.status == ReplayStatus.RUNNING:
            logger.warning(f"Session {session_id} is already running")
            return True

        log = self._logs.get(session.log_id)
        if not log:
            logger.error(f"Log {session.log_id} not found")
            return False

        # Update session state
        session.status = ReplayStatus.RUNNING
        session.started_at = session.started_at or time.time()
        session.paused_at = None
        self._active_session = session

        # Start replay task
        self._replay_task = asyncio.create_task(self._execute_replay(session, log))

        return True

    async def _execute_replay(self, session: ReplaySession, log: ReplayLog):
        """Execute the replay logic."""
        try:
            calls = log.calls
            start_index = session.current_index

            for i in range(start_index, len(calls)):
                if session.status != ReplayStatus.RUNNING:
                    break

                call = calls[i]
                session.current_index = i

                # Calculate delay based on timing
                if session.preserve_timing and i > 0:
                    prev_call = calls[i - 1]
                    delay = (call.timestamp - prev_call.timestamp) / session.speed_multiplier
                    if delay > 0:
                        await asyncio.sleep(delay)

                # Execute the call
                result = await self._replay_call(call, session)
                session.replayed_calls.append(result)

            # Completed
            if session.status == ReplayStatus.RUNNING:
                session.status = ReplayStatus.COMPLETED
                session.completed_at = time.time()

        except Exception as e:
            logger.error(f"Replay failed: {e}")
            session.status = ReplayStatus.FAILED
            session.error = str(e)

    async def _replay_call(
        self,
        call: RecordedCall,
        session: ReplaySession,
    ) -> Dict[str, Any]:
        """Replay a single call."""
        result = {
            "call_id": call.call_id,
            "action_type": call.action_type.value,
            "timestamp": time.time(),
            "status": "success",
        }

        if call.action_type == ReplayAction.LLM_CALL and session.mock_llm:
            # Use mock LLM server
            from .mock_server import get_mock_llm_server
            mock_server = get_mock_llm_server()
            response = mock_server.sync_chat_completion(
                messages=[{"role": "user", "content": str(call.input_data)}],
                model=call.model or "gpt-4",
            )
            result["output"] = response.content
            result["model"] = response.model

        elif call.action_type == ReplayAction.TOOL_CALL and session.mock_tools:
            # Use mock tool server
            from .mock_server import get_mock_tool_server
            mock_server = get_mock_tool_server()
            output = mock_server.execute_tool(
                tool_name=call.metadata.get("tool_name", "unknown"),
                input_data=call.input_data,
            )
            result["output"] = output

        else:
            # Return recorded output
            result["output"] = call.output_data

        return result

    def pause(self, session_id: str) -> bool:
        """Pause replay."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.status != ReplayStatus.RUNNING:
            return False

        session.status = ReplayStatus.PAUSED
        session.paused_at = time.time()
        logger.info(f"Paused session {session_id}")
        return True

    def resume(self, session_id: str) -> bool:
        """Resume paused replay."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.status != ReplayStatus.PAUSED:
            return False

        session.status = ReplayStatus.RUNNING
        session.paused_at = None
        logger.info(f"Resumed session {session_id}")

        # Restart replay task
        log = self._logs.get(session.log_id)
        if log:
            self._replay_task = asyncio.create_task(self._execute_replay(session, log))

        return True

    async def step(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Execute a single step in the replay."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        log = self._logs.get(session.log_id)
        if not log:
            return None

        if session.current_index >= len(log.calls):
            return None

        call = log.calls[session.current_index]
        result = await self._replay_call(call, session)
        session.replayed_calls.append(result)
        session.current_index += 1

        return result

    def stop(self, session_id: str) -> bool:
        """Stop replay."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = ReplayStatus.STOPPED
        session.completed_at = time.time()

        # Cancel replay task if running
        if self._replay_task and not self._replay_task.done():
            self._replay_task.cancel()

        logger.info(f"Stopped session {session_id}")
        return True

    def seek(self, session_id: str, index: int) -> bool:
        """Seek to a specific position in the replay."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        log = self._logs.get(session.log_id)
        if not log:
            return False

        if index < 0 or index > len(log.calls):
            return False

        session.current_index = index
        logger.info(f"Seeked session {session_id} to index {index}")
        return True

    def get_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current replay status."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        log = self._logs.get(session.log_id)
        total_calls = len(log.calls) if log else 0

        return {
            "session_id": session.session_id,
            "status": session.status.value,
            "current_index": session.current_index,
            "total_calls": total_calls,
            "progress": (session.current_index / total_calls * 100) if total_calls > 0 else 0,
            "speed_multiplier": session.speed_multiplier,
            "replayed_calls_count": len(session.replayed_calls),
            "error": session.error,
        }

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all replay sessions."""
        return [
            {
                "session_id": sid,
                "trace_id": s.trace_id,
                "status": s.status.value,
                "current_index": s.current_index,
            }
            for sid, s in self._sessions.items()
        ]


# Global controller instance
_default_controller: Optional[ReplayController] = None


def get_controller() -> ReplayController:
    """Get the global replay controller."""
    global _default_controller
    if _default_controller is None:
        _default_controller = ReplayController()
    return _default_controller


def set_controller(controller: ReplayController):
    """Set the global replay controller."""
    global _default_controller
    _default_controller = controller
