"""Bidirectional mapping between internal span types and OTel GenAI operations.

Provides conversion utilities for translating between the agent-trace
data model and OpenTelemetry GenAI semantic conventions.
"""

from typing import Any, Dict, Optional

from .models import Span, SpanType
from . import otel_attributes as otel

# ── SpanType → OTel operation name ─────────────────────────

_SPAN_TYPE_TO_OPERATION: Dict[SpanType, str] = {
    SpanType.AGENT: otel.OPERATION_INVOKE_AGENT,
    SpanType.LLM: otel.OPERATION_CHAT,
    SpanType.TOOL: otel.OPERATION_EXECUTE_TOOL,
    SpanType.CHAIN: otel.OPERATION_INVOKE_WORKFLOW,
    SpanType.RETRIEVER: otel.OPERATION_RETRIEVE,
    SpanType.EMBEDDING: otel.OPERATION_EMBEDDINGS,
    SpanType.FUNCTION: otel.OPERATION_INVOKE_AGENT,  # closest match
    SpanType.WORKFLOW: otel.OPERATION_INVOKE_WORKFLOW,
    SpanType.CHAT: otel.OPERATION_CHAT,
}

# ── OTel operation name → SpanType ─────────────────────────

_OPERATION_TO_SPAN_TYPE: Dict[str, SpanType] = {
    otel.OPERATION_CREATE_AGENT: SpanType.AGENT,
    otel.OPERATION_INVOKE_AGENT: SpanType.AGENT,
    otel.OPERATION_INVOKE_WORKFLOW: SpanType.WORKFLOW,
    otel.OPERATION_EXECUTE_TOOL: SpanType.TOOL,
    otel.OPERATION_CHAT: SpanType.CHAT,
    otel.OPERATION_TEXT_COMPLETION: SpanType.LLM,
    otel.OPERATION_EMBEDDINGS: SpanType.EMBEDDING,
    otel.OPERATION_RETRIEVE: SpanType.RETRIEVER,
}


def span_type_to_otel_operation(span_type: SpanType) -> str:
    """Map a SpanType to its corresponding OTel gen_ai.operation.name."""
    return _SPAN_TYPE_TO_OPERATION.get(span_type, otel.OPERATION_INVOKE_AGENT)


def otel_operation_to_span_type(operation: str) -> SpanType:
    """Map an OTel gen_ai.operation.name to a SpanType."""
    return _OPERATION_TO_SPAN_TYPE.get(operation, SpanType.AGENT)


def span_to_otel_attributes(span: Span) -> Dict[str, Any]:
    """Convert an internal Span to a dict of OTel GenAI attributes.

    The returned dict can be merged into the span's existing `attributes`
    or used as the attribute payload for OTLP export.
    """
    attrs: Dict[str, Any] = {}

    # Operation name
    operation = span.otel_operation or span_type_to_otel_operation(span.span_type)
    attrs[otel.GEN_AI_OPERATION_NAME] = operation

    # Model / provider
    if span.model:
        attrs[otel.GEN_AI_REQUEST_MODEL] = span.model
        attrs[otel.GEN_AI_RESPONSE_MODEL] = span.model
        # Infer provider from model name if not already set
        if "/" in span.model:
            attrs[otel.GEN_AI_PROVIDER_NAME] = span.model.split("/")[0]

    # Token usage
    if span.prompt_tokens is not None:
        attrs[otel.GEN_AI_USAGE_INPUT_TOKENS] = span.prompt_tokens
    if span.completion_tokens is not None:
        attrs[otel.GEN_AI_USAGE_OUTPUT_TOKENS] = span.completion_tokens

    # Span-type-specific attributes
    if span.span_type == SpanType.AGENT:
        agent_name = span.attributes.get("agent_name", span.name)
        attrs[otel.GEN_AI_AGENT_NAME] = agent_name
        if "agent_id" in span.attributes:
            attrs[otel.GEN_AI_AGENT_ID] = span.attributes["agent_id"]

    elif span.span_type == SpanType.TOOL:
        tool_name = span.attributes.get("tool_name", span.name)
        attrs[otel.GEN_AI_TOOL_NAME] = tool_name
        if "tool_description" in span.attributes:
            attrs[otel.GEN_AI_TOOL_DESCRIPTION] = span.attributes["tool_description"]

    elif span.span_type in (SpanType.CHAIN, SpanType.WORKFLOW):
        attrs[otel.GEN_AI_WORKFLOW_NAME] = span.name

    # Include any request config from attributes
    for key in ("temperature", "max_tokens", "top_p", "stop_sequences"):
        if key in span.attributes:
            otel_key = getattr(otel, f"GEN_AI_REQUEST_{key.upper()}", None)
            if otel_key:
                attrs[otel_key] = span.attributes[key]

    return attrs


def enrich_span_with_otel(span: Span) -> Span:
    """Enrich a span in-place with OTel attributes and operation name.

    This is a convenience function that:
    1. Sets span.otel_operation if not already set
    2. Merges OTel attributes into span.attributes
    """
    if span.otel_operation is None:
        span.otel_operation = span_type_to_otel_operation(span.span_type)

    otel_attrs = span_to_otel_attributes(span)
    # Only add attributes that aren't already present
    for key, value in otel_attrs.items():
        if key not in span.attributes:
            span.attributes[key] = value

    return span
