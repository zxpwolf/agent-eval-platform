"""Data models for agent tracing."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class SpanType(str, Enum):
    """Types of spans in a trace."""
    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    CHAIN = "chain"
    RETRIEVER = "retriever"
    EMBEDDING = "embedding"
    FUNCTION = "function"


class SpanStatus(str, Enum):
    """Status of a span."""
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class SpanEvent:
    """An event within a span (e.g., log message, exception)."""
    timestamp: float
    name: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """Represents a unit of work in a trace."""
    trace_id: str
    span_id: str
    name: str
    span_type: SpanType
    start_time: float
    end_time: Optional[float] = None
    parent_span_id: Optional[str] = None
    status: SpanStatus = SpanStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)

    # LLM-specific fields
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None

    # Input/output
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "span_type": self.span_type.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "parent_span_id": self.parent_span_id,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": [
                {
                    "timestamp": e.timestamp,
                    "name": e.name,
                    "attributes": e.attributes,
                }
                for e in self.events
            ],
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "input_data": self.input_data,
            "output_data": self.output_data,
        }


@dataclass
class Trace:
    """Represents a complete agent execution session."""
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    spans: List[Span] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "spans": [span.to_dict() for span in self.spans],
        }
