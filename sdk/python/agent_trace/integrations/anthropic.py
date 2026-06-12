"""Anthropic SDK auto-instrumentation for automatic tracing.

Monkey-patches the Anthropic Python SDK to capture message creations
as Agent Trace spans without requiring any code changes from the user.

Usage:
    from agent_trace.integrations.anthropic import instrument_anthropic
    instrument_anthropic()

    # All anthropic calls are now automatically traced
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}],
    )
"""

import logging
import time
from typing import Any, Dict, List, Optional

from ..models import Span, SpanStatus, SpanType
from ..tracer import Tracer, get_tracer

logger = logging.getLogger(__name__)

_original_messages_create = None


def instrument_anthropic(tracer: Optional[Tracer] = None) -> None:
    """Auto-instrument the Anthropic SDK for tracing.

    Monkey-patches anthropic.resources.messages.Messages.create
    to automatically capture API calls as spans.

    Call this once at application startup, before making any API calls.
    """
    try:
        import anthropic

        _instrument_messages(anthropic, tracer)

        logger.info("Anthropic SDK auto-instrumentation enabled")
    except ImportError:
        logger.warning(
            "anthropic is not installed. Install it with: pip install anthropic"
        )
        raise


def _instrument_messages(anthropic_module: Any, tracer: Optional[Tracer] = None) -> None:
    """Patch messages.create to capture chat calls."""
    global _original_messages_create

    t = tracer or get_tracer()

    try:
        from anthropic.resources import messages as msg_mod
        Messages = msg_mod.Messages
    except (ImportError, AttributeError):
        logger.warning("Could not find anthropic resources.messages.Messages")
        return

    if getattr(Messages.create, "_agent_trace_patched", False):
        return

    _original_messages_create = Messages.create

    def traced_messages_create(self, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        max_tokens = kwargs.get("max_tokens", 0)
        system = kwargs.get("system", None)

        span = t.start_span(
            name=f"anthropic_messages_{model}",
            span_type=SpanType.LLM,
            attributes={
                "provider": "anthropic",
                "operation": "messages.create",
                "model": model,
                "max_tokens": max_tokens,
            },
        )

        # Serialize input
        input_data: Dict[str, Any] = {}
        if isinstance(messages, list):
            input_data["messages"] = [
                {
                    "role": getattr(m, "role", m.get("role", "user") if isinstance(m, dict) else "user"),
                    "content": str(getattr(m, "content", m.get("content", "")) if isinstance(m, dict) else m)[:500],
                }
                for m in messages[:20]
            ]
        if system:
            input_data["system"] = str(system)[:500]
        span.input_data = input_data
        span.model = model

        try:
            result = _original_messages_create(self, *args, **kwargs)

            # Extract token usage
            if hasattr(result, "usage") and result.usage:
                prompt_tokens = getattr(result.usage, "input_tokens", 0) or 0
                completion_tokens = getattr(result.usage, "output_tokens", 0) or 0
                t.record_llm_call(
                    span,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

            # Extract output
            if hasattr(result, "content") and result.content:
                if len(result.content) == 1:
                    span.output_data = str(result.content[0].text)[:2000] if hasattr(result.content[0], "text") else str(result.content[0])[:2000]
                else:
                    span.output_data = [
                        str(c.text)[:500] if hasattr(c, "text") else str(c)[:500]
                        for c in result.content[:5]
                    ]

            # Record stop reason
            if hasattr(result, "stop_reason"):
                span.attributes["stop_reason"] = result.stop_reason

            t.end_span(span)
            return result
        except Exception as e:
            t.record_error(span, e)
            t.end_span(span)
            raise

    traced_messages_create._agent_trace_patched = True  # type: ignore[attr-defined]
    Messages.create = traced_messages_create  # type: ignore[assignment]


def uninstrument_anthropic() -> None:
    """Remove Anthropic SDK instrumentation patches."""
    try:
        from anthropic.resources import messages as msg_mod

        if _original_messages_create is not None:
            msg_mod.Messages.create = _original_messages_create

        logger.info("Anthropic SDK instrumentation removed")
    except Exception as e:
        logger.warning(f"Failed to uninstrument Anthropic: {e}")
