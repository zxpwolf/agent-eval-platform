"""Replay breakpoints system.

Allows setting breakpoints on specific calls, span types, or conditions
during replay. When a breakpoint is hit, the replay pauses and provides
full state inspection of the current call's inputs/outputs.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from .models import RecordedCall, ReplayAction, ReplaySession

logger = logging.getLogger(__name__)


class BreakpointType(str, Enum):
    """Types of breakpoints that can be set during replay."""
    INDEX = "index"               # Break at a specific call index
    CALL_ID = "call_id"           # Break at a specific call ID
    ACTION_TYPE = "action_type"   # Break on all calls of a given type (llm/tool/function)
    CONDITION = "condition"       # Break when a condition function returns True
    ERROR = "error"               # Break on any call that produces an error
    MODEL = "model"               # Break on calls using a specific model


@dataclass
class Breakpoint:
    """A single breakpoint definition."""
    breakpoint_id: str
    breakpoint_type: BreakpointType
    enabled: bool = True

    # For INDEX type
    index: Optional[int] = None

    # For CALL_ID type
    call_id: Optional[str] = None

    # For ACTION_TYPE type
    action_type: Optional[ReplayAction] = None

    # For MODEL type
    model: Optional[str] = None

    # For CONDITION type
    condition_fn: Optional[Callable[[RecordedCall, int], bool]] = None
    condition_description: str = ""

    # Metadata
    label: str = ""
    hit_count: int = 0
    last_hit_at: Optional[float] = None

    def should_hit(self, call: RecordedCall, index: int) -> bool:
        """Evaluate whether this breakpoint should fire for the given call."""
        if not self.enabled:
            return False

        if self.breakpoint_type == BreakpointType.INDEX:
            return index == self.index

        if self.breakpoint_type == BreakpointType.CALL_ID:
            return call.call_id == self.call_id

        if self.breakpoint_type == BreakpointType.ACTION_TYPE:
            return call.action_type == self.action_type

        if self.breakpoint_type == BreakpointType.ERROR:
            return call.error is not None

        if self.breakpoint_type == BreakpointType.MODEL:
            return call.model == self.model

        if self.breakpoint_type == BreakpointType.CONDITION:
            if self.condition_fn:
                try:
                    return self.condition_fn(call, index)
                except Exception:
                    return False
            return False

        return False

    def hit(self) -> None:
        """Record that this breakpoint was hit."""
        self.hit_count += 1
        self.last_hit_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "breakpoint_id": self.breakpoint_id,
            "breakpoint_type": self.breakpoint_type.value,
            "enabled": self.enabled,
            "index": self.index,
            "call_id": self.call_id,
            "action_type": self.action_type.value if self.action_type else None,
            "model": self.model,
            "condition_description": self.condition_description,
            "label": self.label,
            "hit_count": self.hit_count,
            "last_hit_at": self.last_hit_at,
        }


@dataclass
class BreakpointHitInfo:
    """Information about a breakpoint hit event."""
    breakpoint: Breakpoint
    call: RecordedCall
    index: int
    timestamp: float = field(default_factory=time.time)
    state_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "breakpoint": self.breakpoint.to_dict(),
            "call": self.call.to_dict(),
            "index": self.index,
            "timestamp": self.timestamp,
            "state_snapshot": self.state_snapshot,
        }


class BreakpointManager:
    """Manages breakpoints for replay sessions.

    Each session can have its own set of breakpoints. The manager
    evaluates breakpoints during replay and triggers pause when hit.
    """

    def __init__(self):
        self._session_breakpoints: Dict[str, List[Breakpoint]] = {}
        self._hit_history: Dict[str, List[BreakpointHitInfo]] = {}
        self._on_hit_callbacks: Dict[str, List[Callable[[BreakpointHitInfo], None]]] = {}

    def add_breakpoint(
        self,
        session_id: str,
        breakpoint_type: BreakpointType,
        index: Optional[int] = None,
        call_id: Optional[str] = None,
        action_type: Optional[ReplayAction] = None,
        model: Optional[str] = None,
        condition_fn: Optional[Callable] = None,
        condition_description: str = "",
        label: str = "",
    ) -> Breakpoint:
        """Add a breakpoint to a replay session."""
        import uuid

        bp = Breakpoint(
            breakpoint_id=str(uuid.uuid4()),
            breakpoint_type=breakpoint_type,
            index=index,
            call_id=call_id,
            action_type=action_type,
            model=model,
            condition_fn=condition_fn,
            condition_description=condition_description,
            label=label,
        )

        if session_id not in self._session_breakpoints:
            self._session_breakpoints[session_id] = []

        self._session_breakpoints[session_id].append(bp)
        logger.info(f"Added breakpoint {bp.breakpoint_id} ({breakpoint_type.value}) to session {session_id}")
        return bp

    def remove_breakpoint(self, session_id: str, breakpoint_id: str) -> bool:
        """Remove a breakpoint from a session."""
        bps = self._session_breakpoints.get(session_id, [])
        for i, bp in enumerate(bps):
            if bp.breakpoint_id == breakpoint_id:
                bps.pop(i)
                return True
        return False

    def enable_breakpoint(self, session_id: str, breakpoint_id: str) -> bool:
        """Enable a breakpoint."""
        bp = self._find_breakpoint(session_id, breakpoint_id)
        if bp:
            bp.enabled = True
            return True
        return False

    def disable_breakpoint(self, session_id: str, breakpoint_id: str) -> bool:
        """Disable a breakpoint without removing it."""
        bp = self._find_breakpoint(session_id, breakpoint_id)
        if bp:
            bp.enabled = False
            return True
        return False

    def get_breakpoints(self, session_id: str) -> List[Breakpoint]:
        """Get all breakpoints for a session."""
        return self._session_breakpoints.get(session_id, [])

    def clear_breakpoints(self, session_id: str) -> None:
        """Remove all breakpoints for a session."""
        self._session_breakpoints.pop(session_id, None)

    def evaluate_breakpoints(
        self,
        session_id: str,
        call: RecordedCall,
        index: int,
        state_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[BreakpointHitInfo]:
        """Evaluate all breakpoints for a session against a call.

        Returns the first breakpoint hit info, or None if no breakpoint was hit.
        """
        bps = self._session_breakpoints.get(session_id, [])

        for bp in bps:
            if bp.should_hit(call, index):
                bp.hit()

                hit_info = BreakpointHitInfo(
                    breakpoint=bp,
                    call=call,
                    index=index,
                    state_snapshot=state_snapshot or {},
                )

                # Record hit
                if session_id not in self._hit_history:
                    self._hit_history[session_id] = []
                self._hit_history[session_id].append(hit_info)

                # Fire callbacks
                for cb in self._on_hit_callbacks.get(session_id, []):
                    try:
                        cb(hit_info)
                    except Exception as e:
                        logger.error(f"Breakpoint callback error: {e}")

                logger.info(
                    f"Breakpoint {bp.breakpoint_id} hit at index {index} "
                    f"(call {call.call_id}, type {call.action_type.value})"
                )
                return hit_info

        return None

    def on_hit(
        self,
        session_id: str,
        callback: Callable[[BreakpointHitInfo], None],
    ) -> Callable[[], None]:
        """Register a callback for breakpoint hits. Returns unsubscribe function."""
        if session_id not in self._on_hit_callbacks:
            self._on_hit_callbacks[session_id] = []
        self._on_hit_callbacks[session_id].append(callback)

        def unsubscribe():
            cbs = self._on_hit_callbacks.get(session_id, [])
            if callback in cbs:
                cbs.remove(callback)

        return unsubscribe

    def get_hit_history(self, session_id: str) -> List[BreakpointHitInfo]:
        """Get the full breakpoint hit history for a session."""
        return self._hit_history.get(session_id, [])

    def _find_breakpoint(self, session_id: str, breakpoint_id: str) -> Optional[Breakpoint]:
        """Find a specific breakpoint by ID."""
        for bp in self._session_breakpoints.get(session_id, []):
            if bp.breakpoint_id == breakpoint_id:
                return bp
        return None


# Convenience functions for common breakpoint types

def break_on_index(session_id: str, index: int, manager: Optional[BreakpointManager] = None, label: str = "") -> Breakpoint:
    """Set a breakpoint at a specific call index."""
    mgr = manager or get_breakpoint_manager()
    return mgr.add_breakpoint(session_id, BreakpointType.INDEX, index=index, label=label)


def break_on_llm_calls(session_id: str, manager: Optional[BreakpointManager] = None, label: str = "Break on LLM") -> Breakpoint:
    """Break on every LLM call."""
    mgr = manager or get_breakpoint_manager()
    return mgr.add_breakpoint(session_id, BreakpointType.ACTION_TYPE, action_type=ReplayAction.LLM_CALL, label=label)


def break_on_tool_calls(session_id: str, manager: Optional[BreakpointManager] = None, label: str = "Break on Tools") -> Breakpoint:
    """Break on every tool call."""
    mgr = manager or get_breakpoint_manager()
    return mgr.add_breakpoint(session_id, BreakpointType.ACTION_TYPE, action_type=ReplayAction.TOOL_CALL, label=label)


def break_on_errors(session_id: str, manager: Optional[BreakpointManager] = None, label: str = "Break on Error") -> Breakpoint:
    """Break on any call that produces an error."""
    mgr = manager or get_breakpoint_manager()
    return mgr.add_breakpoint(session_id, BreakpointType.ERROR, label=label)


def break_on_model(session_id: str, model: str, manager: Optional[BreakpointManager] = None, label: str = "") -> Breakpoint:
    """Break on calls using a specific model."""
    mgr = manager or get_breakpoint_manager()
    return mgr.add_breakpoint(session_id, BreakpointType.MODEL, model=model, label=label or f"Model: {model}")


# Global breakpoint manager
_default_manager: Optional[BreakpointManager] = None


def get_breakpoint_manager() -> BreakpointManager:
    """Get the global breakpoint manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = BreakpointManager()
    return _default_manager
