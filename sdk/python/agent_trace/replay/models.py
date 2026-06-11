"""Data models for replay engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class ReplayAction(str, Enum):
    """Types of actions in a replay log."""
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    FUNCTION_CALL = "function_call"
    STATE_CHANGE = "state_change"
    MESSAGE = "message"
    DECISION = "decision"


class ReplayStatus(str, Enum):
    """Status of a replay session."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class RecordedCall:
    """A single recorded call (LLM, tool, or function)."""
    call_id: str
    action_type: ReplayAction
    timestamp: float
    duration_ms: float = 0.0

    # Input
    input_data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Output
    output_data: Any = None
    error: Optional[str] = None

    # For LLM calls
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    # Context
    span_id: Optional[str] = None
    parent_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "call_id": self.call_id,
            "action_type": self.action_type.value,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "input_data": self.input_data,
            "metadata": self.metadata,
            "output_data": self.output_data,
            "error": self.error,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "span_id": self.span_id,
            "parent_call_id": self.parent_call_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordedCall":
        """Deserialize from dictionary."""
        return cls(
            call_id=data["call_id"],
            action_type=ReplayAction(data["action_type"]),
            timestamp=data["timestamp"],
            duration_ms=data.get("duration_ms", 0.0),
            input_data=data.get("input_data"),
            metadata=data.get("metadata", {}),
            output_data=data.get("output_data"),
            error=data.get("error"),
            model=data.get("model"),
            prompt_tokens=data.get("prompt_tokens"),
            completion_tokens=data.get("completion_tokens"),
            span_id=data.get("span_id"),
            parent_call_id=data.get("parent_call_id"),
        )


@dataclass
class ReplayLog:
    """Complete execution log for a trace, used for replay."""
    trace_id: str
    log_id: str
    created_at: float = field(default_factory=time.time)

    # Recorded calls in order
    calls: List[RecordedCall] = field(default_factory=list)

    # Initial state/context
    initial_state: Dict[str, Any] = field(default_factory=dict)

    # Final state
    final_state: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    agent_config: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "trace_id": self.trace_id,
            "log_id": self.log_id,
            "created_at": self.created_at,
            "calls": [call.to_dict() for call in self.calls],
            "initial_state": self.initial_state,
            "final_state": self.final_state,
            "agent_config": self.agent_config,
            "environment": self.environment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayLog":
        """Deserialize from dictionary."""
        return cls(
            trace_id=data["trace_id"],
            log_id=data["log_id"],
            created_at=data.get("created_at", time.time()),
            calls=[RecordedCall.from_dict(c) for c in data.get("calls", [])],
            initial_state=data.get("initial_state", {}),
            final_state=data.get("final_state", {}),
            agent_config=data.get("agent_config", {}),
            environment=data.get("environment", {}),
        )


@dataclass
class ReplaySession:
    """A replay session with control state."""
    session_id: str
    trace_id: str
    log_id: str
    status: ReplayStatus = ReplayStatus.PENDING

    # Playback position
    current_index: int = 0
    speed_multiplier: float = 1.0

    # Timing
    started_at: Optional[float] = None
    paused_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Results
    replayed_calls: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    # Configuration
    mock_llm: bool = True
    mock_tools: bool = False
    preserve_timing: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "log_id": self.log_id,
            "status": self.status.value,
            "current_index": self.current_index,
            "speed_multiplier": self.speed_multiplier,
            "started_at": self.started_at,
            "paused_at": self.paused_at,
            "completed_at": self.completed_at,
            "replayed_calls": self.replayed_calls,
            "error": self.error,
            "mock_llm": self.mock_llm,
            "mock_tools": self.mock_tools,
            "preserve_timing": self.preserve_timing,
        }
