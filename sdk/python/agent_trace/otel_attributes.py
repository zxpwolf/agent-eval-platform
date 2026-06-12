"""OpenTelemetry GenAI semantic convention attribute constants.

Based on the OpenTelemetry GenAI semantic conventions:
https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/

These constants define the standard attribute keys for GenAI spans.
Values are stored within the span's `attributes` dict.
"""

# ── Core operation attributes ──────────────────────────────

GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_SYSTEM = "gen_ai.system"

# ── Agent attributes ───────────────────────────────────────

GEN_AI_AGENT_ID = "gen_ai.agent.id"
GEN_AI_AGENT_NAME = "gen_ai.agent.name"
GEN_AI_AGENT_DESCRIPTION = "gen_ai.agent.description"
GEN_AI_AGENT_VERSION = "gen_ai.agent.version"

# ── Session / user attributes ──────────────────────────────

GEN_AI_SESSION_ID = "gen_ai.session.id"
GEN_AI_USER_ID = "gen_ai.user.id"

# ── Workflow attributes ────────────────────────────────────

GEN_AI_WORKFLOW_NAME = "gen_ai.workflow.name"

# ── Request attributes ─────────────────────────────────────

GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
GEN_AI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
GEN_AI_REQUEST_ENCODING_FORMAT = "gen_ai.request.encoding_format"

# ── Response attributes ────────────────────────────────────

GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"

# ── Usage attributes ───────────────────────────────────────

GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS = "gen_ai.usage.cache_read.input_tokens"
GEN_AI_TOKEN_TYPE = "gen_ai.token.type"

# ── Tool attributes ────────────────────────────────────────

GEN_AI_TOOL_NAME = "gen_ai.tool.name"
GEN_AI_TOOL_DESCRIPTION = "gen_ai.tool.description"

# ── Provider name ──────────────────────────────────────────

GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"

# ── Opt-in content attributes (sensitive) ──────────────────

GEN_AI_INPUT_MESSAGES = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES = "gen_ai.output.messages"
GEN_AI_SYSTEM_INSTRUCTIONS = "gen_ai.system.instructions"
GEN_AI_TOOL_DEFINITIONS = "gen_ai.tool.definitions"

# ── Network attributes ─────────────────────────────────────

SERVER_ADDRESS = "server.address"
SERVER_PORT = "server.port"

# ── Operation name values ──────────────────────────────────

OPERATION_CREATE_AGENT = "create_agent"
OPERATION_INVOKE_AGENT = "invoke_agent"
OPERATION_INVOKE_WORKFLOW = "invoke_workflow"
OPERATION_EXECUTE_TOOL = "execute_tool"
OPERATION_CHAT = "chat"
OPERATION_TEXT_COMPLETION = "text_completion"
OPERATION_EMBEDDINGS = "embeddings"
OPERATION_RETRIEVE = "retrieve"
