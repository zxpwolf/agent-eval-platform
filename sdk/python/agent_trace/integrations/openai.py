"""OpenAI SDK auto-instrumentation for automatic tracing.

Monkey-patches the OpenAI Python SDK to capture chat completions,
embeddings, and other API calls as Agent Trace spans without
requiring any code changes from the user.

Usage:
    from agent_trace.integrations.openai import instrument_openai
    instrument_openai()

    # All openai calls are now automatically traced
    client = openai.OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
    )
"""

import logging
import time
from typing import Any, Dict, List, Optional

from ..models import Span, SpanStatus, SpanType
from ..tracer import Tracer, get_tracer

logger = logging.getLogger(__name__)

_original_chat_create = None
_original_chat_acreate = None
_original_embeddings_create = None
_original_embeddings_acreate = None


def instrument_openai(tracer: Optional[Tracer] = None) -> None:
    """Auto-instrument the OpenAI SDK for tracing.

    Monkey-patches openai.resources.chat.completions.Completions.create
    and openai.resources.embeddings.Embeddings.create to automatically
    capture LLM calls as spans.

    Call this once at application startup, before making any API calls.
    """
    try:
        import openai

        _instrument_chat(openai, tracer)
        _instrument_embeddings(openai, tracer)

        logger.info("OpenAI SDK auto-instrumentation enabled")
    except ImportError:
        logger.warning(
            "openai is not installed. Install it with: pip install openai"
        )
        raise


def _instrument_chat(openai_module: Any, tracer: Optional[Tracer] = None) -> None:
    """Patch chat.completions.create to capture LLM calls."""
    global _original_chat_create

    t = tracer or get_tracer()

    try:
        from openai.resources.chat import completions as chat_mod
        Completions = chat_mod.Completions
    except (ImportError, AttributeError):
        logger.warning("Could not find openai chat.completions.Completions")
        return

    if getattr(Completions.create, "_agent_trace_patched", False):
        return

    _original_chat_create = Completions.create

    def traced_chat_create(self, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", args[1] if len(args) > 1 else "unknown")
        messages = kwargs.get("messages", args[0] if len(args) > 0 else [])

        span = t.start_span(
            name=f"openai_chat_{model}",
            span_type=SpanType.LLM,
            attributes={
                "provider": "openai",
                "operation": "chat.completions",
                "model": model,
            },
        )

        # Serialize input messages
        if isinstance(messages, list):
            span.input_data = [
                {
                    "role": getattr(m, "role", m.get("role", "user") if isinstance(m, dict) else "user"),
                    "content": str(getattr(m, "content", m.get("content", "")) if isinstance(m, dict) else m)[:500],
                }
                for m in messages[:20]
            ]

        span.model = model

        try:
            result = _original_chat_create(self, *args, **kwargs)

            # Extract token usage
            if hasattr(result, "usage") and result.usage:
                t.record_llm_call(
                    span,
                    model=model,
                    prompt_tokens=result.usage.prompt_tokens or 0,
                    completion_tokens=result.usage.completion_tokens or 0,
                )

            # Extract output
            if hasattr(result, "choices") and result.choices:
                if len(result.choices) == 1:
                    span.output_data = str(result.choices[0].message.content)[:2000] if result.choices[0].message else None
                else:
                    span.output_data = [
                        str(c.message.content)[:500] if c.message else None
                        for c in result.choices[:5]
                    ]

            t.end_span(span)
            return result
        except Exception as e:
            t.record_error(span, e)
            t.end_span(span)
            raise

    traced_chat_create._agent_trace_patched = True  # type: ignore[attr-defined]
    Completions.create = traced_chat_create  # type: ignore[assignment]


def _instrument_embeddings(openai_module: Any, tracer: Optional[Tracer] = None) -> None:
    """Patch embeddings.create to capture embedding calls."""
    global _original_embeddings_create

    t = tracer or get_tracer()

    try:
        from openai.resources import embeddings as emb_mod
        Embeddings = emb_mod.Embeddings
    except (ImportError, AttributeError):
        logger.warning("Could not find openai embeddings.Embeddings")
        return

    if getattr(Embeddings.create, "_agent_trace_patched", False):
        return

    _original_embeddings_create = Embeddings.create

    def traced_embeddings_create(self, *args: Any, **kwargs: Any) -> Any:
        model = kwargs.get("model", "unknown")
        input_data = kwargs.get("input", [])

        span = t.start_span(
            name=f"openai_embedding_{model}",
            span_type=SpanType.EMBEDDING,
            attributes={
                "provider": "openai",
                "operation": "embeddings",
                "model": model,
            },
        )

        # Serialize input
        if isinstance(input_data, list):
            span.input_data = {"text_count": len(input_data), "sample": str(input_data[0])[:200] if input_data else ""}
        else:
            span.input_data = str(input_data)[:500]

        span.model = model

        try:
            result = _original_embeddings_create(self, *args, **kwargs)

            # Extract usage
            if hasattr(result, "usage") and result.usage:
                t.record_llm_call(
                    span,
                    model=model,
                    prompt_tokens=result.usage.prompt_tokens or 0,
                    completion_tokens=0,
                )

            # Output summary
            if hasattr(result, "data"):
                span.output_data = f"{len(result.data)} embeddings, dim={len(result.data[0].embedding) if result.data else 0}"

            t.end_span(span)
            return result
        except Exception as e:
            t.record_error(span, e)
            t.end_span(span)
            raise

    traced_embeddings_create._agent_trace_patched = True  # type: ignore[attr-defined]
    Embeddings.create = traced_embeddings_create  # type: ignore[assignment]


def uninstrument_openai() -> None:
    """Remove OpenAI SDK instrumentation patches."""
    try:
        import openai
        from openai.resources.chat import completions as chat_mod
        from openai.resources import embeddings as emb_mod

        if _original_chat_create is not None:
            chat_mod.Completions.create = _original_chat_create
        if _original_embeddings_create is not None:
            emb_mod.Embeddings.create = _original_embeddings_create

        logger.info("OpenAI SDK instrumentation removed")
    except Exception as e:
        logger.warning(f"Failed to uninstrument OpenAI: {e}")
