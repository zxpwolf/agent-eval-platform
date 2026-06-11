"""Decorators for easy tracing integration."""

import functools
import inspect
from typing import Any, Callable, Optional

from .models import SpanType
from .tracer import get_tracer


def trace(
    name: Optional[str] = None,
    span_type: SpanType = SpanType.FUNCTION,
):
    """Decorator to trace function execution.

    Usage:
        @trace()
        def my_function(arg1, arg2):
            ...

        @trace(name="custom_name", span_type=SpanType.TOOL)
        def my_tool(arg1, arg2):
            ...
    """

    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                span = tracer.start_span(
                    name=func_name,
                    span_type=span_type,
                    attributes={
                        "function": func.__qualname__,
                        "args": _serialize_args(args),
                        "kwargs": _serialize_kwargs(kwargs),
                    },
                )

                try:
                    result = await func(*args, **kwargs)
                    tracer.end_span(span, output_data=_safe_serialize(result))
                    return result
                except Exception as e:
                    tracer.record_error(span, e)
                    tracer.end_span(span)
                    raise

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                span = tracer.start_span(
                    name=func_name,
                    span_type=span_type,
                    attributes={
                        "function": func.__qualname__,
                        "args": _serialize_args(args),
                        "kwargs": _serialize_kwargs(kwargs),
                    },
                )

                try:
                    result = func(*args, **kwargs)
                    tracer.end_span(span, output_data=_safe_serialize(result))
                    return result
                except Exception as e:
                    tracer.record_error(span, e)
                    tracer.end_span(span)
                    raise

            return sync_wrapper

    return decorator


def trace_llm(
    name: Optional[str] = None,
    model: Optional[str] = None,
):
    """Decorator specifically for LLM calls.

    Usage:
        @trace_llm(model="gpt-4")
        def call_llm(prompt):
            ...
    """

    def decorator(func: Callable) -> Callable:
        func_name = name or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = get_tracer()
                span = tracer.start_span(
                    name=func_name,
                    span_type=SpanType.LLM,
                    attributes={
                        "model": model,
                        "function": func.__qualname__,
                    },
                )

                try:
                    result = await func(*args, **kwargs)
                    # Try to extract token usage from result
                    if hasattr(result, "usage_metadata"):
                        usage = result.usage_metadata
                        tracer.record_llm_call(
                            span,
                            model=model or "unknown",
                            prompt_tokens=getattr(usage, "input_tokens", 0),
                            completion_tokens=getattr(usage, "output_tokens", 0),
                        )
                    tracer.end_span(span, output_data=_safe_serialize(result))
                    return result
                except Exception as e:
                    tracer.record_error(span, e)
                    tracer.end_span(span)
                    raise

            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = get_tracer()
                span = tracer.start_span(
                    name=func_name,
                    span_type=SpanType.LLM,
                    attributes={
                        "model": model,
                        "function": func.__qualname__,
                    },
                )

                try:
                    result = func(*args, **kwargs)
                    if hasattr(result, "usage_metadata"):
                        usage = result.usage_metadata
                        tracer.record_llm_call(
                            span,
                            model=model or "unknown",
                            prompt_tokens=getattr(usage, "input_tokens", 0),
                            completion_tokens=getattr(usage, "output_tokens", 0),
                        )
                    tracer.end_span(span, output_data=_safe_serialize(result))
                    return result
                except Exception as e:
                    tracer.record_error(span, e)
                    tracer.end_span(span)
                    raise

            return sync_wrapper

    return decorator


def _serialize_args(args: tuple) -> list:
    """Serialize function arguments safely."""
    result = []
    for arg in args:
        result.append(_safe_serialize(arg))
    return result


def _serialize_kwargs(kwargs: dict) -> dict:
    """Serialize keyword arguments safely."""
    return {k: _safe_serialize(v) for k, v in kwargs.items()}


def _safe_serialize(obj: Any, max_depth: int = 3) -> Any:
    """Safely serialize an object, avoiding circular references and large data."""

    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    # Handle common types
    if isinstance(obj, (list, tuple)):
        if len(obj) > 100:
            return f"<list/tuple with {len(obj)} items>"
        return [_safe_serialize(item, max_depth - 1) for item in obj[:100]]

    if isinstance(obj, dict):
        if len(obj) > 100:
            return f"<dict with {len(obj)} keys>"
        return {
            str(k): _safe_serialize(v, max_depth - 1)
            for k, v in list(obj.items())[:100]
        }

    # Handle objects with __dict__
    if hasattr(obj, "__dict__"):
        if max_depth <= 0:
            return f"<{type(obj).__name__}>"
        try:
            return {
                "__type__": type(obj).__name__,
                **_safe_serialize(obj.__dict__, max_depth - 1),
            }
        except Exception:
            return f"<{type(obj).__name__}>"

    # Fallback: convert to string
    try:
        result = str(obj)
        if len(result) > 1000:
            return result[:1000] + "..."
        return result
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"
