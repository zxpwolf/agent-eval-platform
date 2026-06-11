"""Core tracer for agent observability."""

import contextvars
import time
import uuid
from typing import Any, Dict, List, Optional

from .models import Span, SpanEvent, SpanStatus, SpanType, Trace


# Context variable to track current span in async context
_current_span: contextvars.ContextVar[Optional["SpanContext"]] = contextvars.ContextVar(
    "current_span", default=None
)


class SpanContext:
    """Context for tracking spans."""

    def __init__(self, trace: Trace, span: Span):
        self.trace = trace
        self.span = span


class Tracer:
    """Main tracer for capturing agent execution."""

    def __init__(self, project_name: str = "default"):
        self.project_name = project_name
        self._active_traces: Dict[str, Trace] = {}

    def start_trace(
        self,
        name: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Trace:
        """Start a new trace."""
        trace = Trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        self._active_traces[trace.trace_id] = trace
        return trace

    def end_trace(self, trace_id: str) -> Optional[Trace]:
        """End a trace and return it."""
        trace = self._active_traces.pop(trace_id, None)
        if trace:
            trace.end_time = time.time()
        return trace

    def get_active_trace(self) -> Optional[Trace]:
        """Get the currently active trace from context."""
        ctx = _current_span.get()
        if ctx:
            return ctx.trace
        return None

    def start_span(
        self,
        name: str,
        span_type: SpanType,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span within the current trace context."""
        # Get or create trace
        ctx = _current_span.get()
        if ctx is None:
            # Auto-create trace if not exists
            trace = self.start_trace(name=f"auto_{name}")
        else:
            trace = ctx.trace

        # Determine parent
        if parent_span_id is None and ctx:
            parent_span_id = ctx.span.span_id

        span = Span(
            trace_id=trace.trace_id,
            span_id=str(uuid.uuid4()),
            name=name,
            span_type=span_type,
            start_time=time.time(),
            parent_span_id=parent_span_id,
            attributes=attributes or {},
        )

        trace.spans.append(span)

        # Set as current context
        new_ctx = SpanContext(trace=trace, span=span)
        _current_span.set(new_ctx)

        return span

    def end_span(
        self,
        span: Span,
        status: SpanStatus = SpanStatus.OK,
        output_data: Any = None,
    ) -> Span:
        """End a span."""
        span.end_time = time.time()
        span.status = status
        if output_data is not None:
            span.output_data = output_data

        # Restore parent context
        ctx = _current_span.get()
        if ctx and ctx.span.parent_span_id:
            # Find parent span
            parent_span = next(
                (s for s in ctx.trace.spans if s.span_id == ctx.span.parent_span_id),
                None,
            )
            if parent_span:
                _current_span.set(SpanContext(trace=ctx.trace, span=parent_span))
        else:
            _current_span.set(None)

        return span

    def record_event(self, span: Span, name: str, attributes: Dict[str, Any]):
        """Record an event within a span."""
        event = SpanEvent(
            timestamp=time.time(),
            name=name,
            attributes=attributes,
        )
        span.events.append(event)

    def record_llm_call(
        self,
        span: Span,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: Optional[float] = None,
    ):
        """Record LLM call metrics."""
        span.model = model
        span.prompt_tokens = prompt_tokens
        span.completion_tokens = completion_tokens
        span.total_tokens = prompt_tokens + completion_tokens
        span.cost = cost

    def record_error(self, span: Span, error: Exception):
        """Record an error in a span."""
        span.status = SpanStatus.ERROR
        self.record_event(
            span,
            "exception",
            {
                "type": type(error).__name__,
                "message": str(error),
            },
        )


# Global tracer instance
_default_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    global _default_tracer
    if _default_tracer is None:
        _default_tracer = Tracer()
    return _default_tracer


def set_tracer(tracer: Tracer):
    """Set the global tracer."""
    global _default_tracer
    _default_tracer = tracer
