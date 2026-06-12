/**
 * OpenTelemetry GenAI semantic convention attribute constants.
 *
 * Aligned with the Python SDK's otel_attributes module and the
 * OpenTelemetry GenAI Semantic Conventions specification.
 */

// ── Core GenAI attributes ────────────────────────────────────

export const GEN_AI_OPERATION_NAME = 'gen_ai.operation.name'
export const GEN_AI_SYSTEM = 'gen_ai.system'
export const GEN_AI_REQUEST_MODEL = 'gen_ai.request.model'
export const GEN_AI_RESPONSE_MODEL = 'gen_ai.response.model'

// ── Agent attributes ─────────────────────────────────────────

export const GEN_AI_AGENT_ID = 'gen_ai.agent.id'
export const GEN_AI_AGENT_NAME = 'gen_ai.agent.name'
export const GEN_AI_AGENT_DESCRIPTION = 'gen_ai.agent.description'

// ── Session attributes ───────────────────────────────────────

export const GEN_AI_SESSION_ID = 'gen_ai.session.id'
export const GEN_AI_USER_ID = 'gen_ai.user.id'

// ── Request attributes ───────────────────────────────────────

export const GEN_AI_REQUEST_MAX_TOKENS = 'gen_ai.request.max_tokens'
export const GEN_AI_REQUEST_TEMPERATURE = 'gen_ai.request.temperature'
export const GEN_AI_REQUEST_TOP_P = 'gen_ai.request.top_p'
export const GEN_AI_REQUEST_FREQUENCY_PENALTY = 'gen_ai.request.frequency_penalty'
export const GEN_AI_REQUEST_PRESENCE_PENALTY = 'gen_ai.request.presence_penalty'
export const GEN_AI_REQUEST_STOP_SEQUENCES = 'gen_ai.request.stop_sequences'

// ── Response attributes ──────────────────────────────────────

export const GEN_AI_RESPONSE_ID = 'gen_ai.response.id'
export const GEN_AI_RESPONSE_FINISH_REASONS = 'gen_ai.response.finish_reasons'

// ── Usage attributes ─────────────────────────────────────────

export const GEN_AI_USAGE_INPUT_TOKENS = 'gen_ai.usage.input_tokens'
export const GEN_AI_USAGE_OUTPUT_TOKENS = 'gen_ai.usage.output_tokens'
export const GEN_AI_TOKEN_TYPE = 'gen_ai.token.type'

// ── Content attributes ───────────────────────────────────────

export const GEN_AI_PROMPT = 'gen_ai.prompt'
export const GEN_AI_COMPLETION = 'gen_ai.completion'

// ── Operation name values ────────────────────────────────────

export const OPERATION_CREATE_AGENT = 'create_agent'
export const OPERATION_INVOKE_AGENT = 'invoke_agent'
export const OPERATION_INVOKE_WORKFLOW = 'invoke_workflow'
export const OPERATION_EXECUTE_TOOL = 'execute_tool'
export const OPERATION_CHAT = 'chat'
export const OPERATION_EMBEDDINGS = 'embeddings'
export const OPERATION_RETRIEVE = 'retrieve'
export const OPERATION_FUNCTION = 'function'
