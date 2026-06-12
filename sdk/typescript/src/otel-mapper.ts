/**
 * Bidirectional mapping between SpanType and OTel GenAI operation names.
 *
 * Provides functions to convert between the SDK's internal span types
 * and the OpenTelemetry GenAI semantic convention operation names.
 */

import { Span, SpanType } from './models'
import {
  GEN_AI_OPERATION_NAME,
  GEN_AI_REQUEST_MODEL,
  GEN_AI_SYSTEM,
  GEN_AI_USAGE_INPUT_TOKENS,
  GEN_AI_USAGE_OUTPUT_TOKENS,
  OPERATION_CHAT,
  OPERATION_EMBEDDINGS,
  OPERATION_EXECUTE_TOOL,
  OPERATION_FUNCTION,
  OPERATION_INVOKE_AGENT,
  OPERATION_INVOKE_WORKFLOW,
  OPERATION_RETRIEVE,
} from './otel-attributes'

// ── SpanType → OTel operation name ───────────────────────────

const SPAN_TYPE_TO_OPERATION: Record<SpanType, string> = {
  [SpanType.AGENT]: OPERATION_INVOKE_AGENT,
  [SpanType.LLM]: OPERATION_CHAT,
  [SpanType.TOOL]: OPERATION_EXECUTE_TOOL,
  [SpanType.CHAIN]: OPERATION_INVOKE_WORKFLOW,
  [SpanType.RETRIEVER]: OPERATION_RETRIEVE,
  [SpanType.EMBEDDING]: OPERATION_EMBEDDINGS,
  [SpanType.FUNCTION]: OPERATION_FUNCTION,
  [SpanType.WORKFLOW]: OPERATION_INVOKE_WORKFLOW,
  [SpanType.CHAT]: OPERATION_CHAT,
}

// ── OTel operation name → SpanType ───────────────────────────

const OPERATION_TO_SPAN_TYPE: Record<string, SpanType> = {
  create_agent: SpanType.AGENT,
  invoke_agent: SpanType.AGENT,
  invoke_workflow: SpanType.CHAIN,
  execute_tool: SpanType.TOOL,
  chat: SpanType.LLM,
  embeddings: SpanType.EMBEDDING,
  retrieve: SpanType.RETRIEVER,
  function: SpanType.FUNCTION,
}

/**
 * Convert a SpanType to its corresponding OTel operation name.
 */
export function spanTypeToOtelOperation(spanType: SpanType): string {
  return SPAN_TYPE_TO_OPERATION[spanType] || OPERATION_FUNCTION
}

/**
 * Convert an OTel operation name to its corresponding SpanType.
 */
export function otelOperationToSpanType(operation: string): SpanType {
  return OPERATION_TO_SPAN_TYPE[operation] || SpanType.FUNCTION
}

/**
 * Enrich a span with OTel attributes based on its type and data.
 */
export function enrichSpanWithOtel(span: Span): Span {
  const enriched: Span = { ...span }

  // Set operation name if not already present
  if (!enriched.otelOperation) {
    enriched.otelOperation = spanTypeToOtelOperation(enriched.spanType)
  }

  // Add OTel attributes
  enriched.attributes = { ...enriched.attributes }

  enriched.attributes[GEN_AI_OPERATION_NAME] = enriched.otelOperation

  if (enriched.model) {
    enriched.attributes[GEN_AI_REQUEST_MODEL] = enriched.model
    // Derive system from model name
    const system = enriched.model.includes('/')
      ? enriched.model.split('/')[0]
      : 'openai'
    enriched.attributes[GEN_AI_SYSTEM] = system
  }

  if (enriched.promptTokens != null) {
    enriched.attributes[GEN_AI_USAGE_INPUT_TOKENS] = enriched.promptTokens
  }

  if (enriched.completionTokens != null) {
    enriched.attributes[GEN_AI_USAGE_OUTPUT_TOKENS] = enriched.completionTokens
  }

  return enriched
}
