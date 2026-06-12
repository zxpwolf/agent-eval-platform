# Agent Observability

Open-source observability, evaluation, and replay platform for AI Agents. Track, debug, evaluate, and optimize your agent applications with full OpenTelemetry GenAI compatibility.

## Features

- **Automatic Tracing**: Capture LLM calls, tool executions, and agent decision chains
- **OTel GenAI Semantic Conventions**: Full compatibility with OpenTelemetry GenAI standards
- **OTLP Export**: Send traces to any OTLP-compatible backend (Jaeger, Grafana Tempo, Honeycomb, Datadog)
- **Evaluation Framework**: Dataset management, heuristic/LLM-judge/custom evaluators, scoring pipeline
- **Deterministic Replay**: Record and replay agent executions with breakpoints and state inspection
- **Replay Breakpoints**: Pause on specific call indices, action types, errors, or custom conditions
- **State Inspection & Fork**: Inspect replay state at any point and fork into divergent execution paths
- **Real-time Streaming**: SSE-based live trace streaming for dashboard updates without polling
- **Analytics Dashboard**: Time-series, model cost, latency, error rate, and span type analytics
- **Session & Conversation View**: Group traces by session with timeline visualization
- **Trace Comparison**: Side-by-side comparison with delta metrics for duration, tokens, and cost
- **Multi-user Authentication**: JWT-based auth with API keys, registration, and admin roles
- **PostgreSQL Support**: Production-ready PostgreSQL backend with connection pooling and JSONB
- **Cost Tracking & Alerts**: Token usage tracking with configurable cost alerts
- **PII Masking**: Automatic detection and masking of sensitive data in traces
- **Framework Integrations**: LangGraph, LlamaIndex, and CrewAI callback handlers
- **Mock Servers**: Simulate LLM and tool responses without API costs
- **Low Overhead**: Async batch exporting with <5% performance impact
- **SQLite + PostgreSQL**: Lightweight storage with schema migrations and dual database support

## Quick Start

### 1. Install SDK

```bash
cd sdk/python
pip install -r requirements.txt
```

### 2. Add Tracing to Your Code

```python
from agent_trace import trace, get_tracer
from agent_trace.exporters import FileExporter

# Configure exporter
tracer = get_tracer()
tracer._exporter = FileExporter("traces.jsonl")

# Add @trace decorator to your functions
@trace()
def my_agent_function(input: str):
    return process(input)

@trace(span_type="llm")
def call_llm(prompt: str):
    return llm.generate(prompt)
```

### 3. Integrate with LangGraph

```python
from agent_trace.integrations.langgraph import AgentTraceCallbackHandler

# Create callback handler
handler = AgentTraceCallbackHandler()

# Use with LangGraph agent
result = agent.invoke(
    {"messages": [HumanMessage(content="Hello")]},
    callbacks=[handler],
)
```

### 4. Run Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Visit http://localhost:8000/docs for API documentation.

### 5. Run Frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:3000 for the web dashboard.

## OTel GenAI Semantic Conventions

Traces are automatically enriched with OTel GenAI semantic convention attributes:

```python
from agent_trace import SpanType
from agent_trace.otel_mapper import span_type_to_otel_operation, enrich_span_with_otel

# SpanType → OTel operation mapping
span_type_to_otel_operation(SpanType.LLM)       # → "chat"
span_type_to_otel_operation(SpanType.TOOL)       # → "execute_tool"
span_type_to_otel_operation(SpanType.AGENT)      # → "invoke_agent"
span_type_to_otel_operation(SpanType.WORKFLOW)   # → "invoke_workflow"
span_type_to_otel_operation(SpanType.RETRIEVER)  # → "retrieve"

# Enrich a span with OTel attributes
enriched = enrich_span_with_otel(span)
# Adds: gen_ai.operation.name, gen_ai.request.model, gen_ai.usage.input_tokens, etc.
```

## OTLP Export

Export traces to any OTLP-compatible backend:

```python
from agent_trace.otel_exporter import OTLPExporter, OTLPExporterConfig

config = OTLPExporterConfig(
    endpoint="http://localhost:4318/v1/traces",
    resource_attributes={"service.name": "my-agent"},
)
exporter = OTLPExporter(config)

# Export a trace
exporter.export_trace(trace)

# Batch export (auto-flushes when batch is full or timeout)
exporter.batch_export(trace)
exporter.flush()
```

## Evaluation Framework

### Creating Datasets and Evaluators

```python
from agent_trace.eval import (
    EvaluationPipeline,
    RegexMatchEvaluator,
    ContainsEvaluator,
    LLMJudgeEvaluator,
    CustomEvaluator,
)

# Heuristic evaluators
contains = ContainsEvaluator(value="expected keyword")
regex = RegexMatchEvaluator(pattern=r"\d{3}-\d{4}")
exact = ExactMatchEvaluator(expected="exact output")

# LLM-as-judge evaluator
judge = LLMJudgeEvaluator(
    rubric="Rate the response quality from 0-1",
    judge_fn=lambda prompt: call_my_llm(prompt),
)

# Custom evaluator
custom = CustomEvaluator(fn=lambda input, expected, actual: {
    "score": 0.9, "passed": True, "reasoning": "Custom check passed"
})

# Run evaluation pipeline
pipeline = EvaluationPipeline(evaluators=[contains, judge])
results = pipeline.run(
    inputs=["input 1", "input 2"],
    expected_outputs=["expected 1", "expected 2"],
    actual_outputs=["actual 1", "actual 2"],
)
```

### Evaluation API

```
POST   /api/evaluations/datasets          - Create dataset
GET    /api/evaluations/datasets          - List datasets
GET    /api/evaluations/datasets/{id}     - Get dataset with items
POST   /api/evaluations/datasets/{id}/items - Add items
POST   /api/evaluations/evaluators        - Create evaluator
GET    /api/evaluations/evaluators        - List evaluators
POST   /api/evaluations/runs              - Start evaluation run
GET    /api/evaluations/runs              - List runs
GET    /api/evaluations/runs/{id}         - Get run with results
POST   /api/evaluations/runs/{id}/cancel  - Cancel run
POST   /api/evaluations/compare           - Compare two runs
```

## Replay Engine

### Basic Replay

```python
from agent_trace.replay import get_engine

engine = get_engine()

# Export a trace as replay log
log_id = engine.export_replay_log(trace)

# Replay with mock LLM
session_id = await engine.replay_trace(
    trace_id=trace.trace_id,
    mock_llm=True,
    speed_multiplier=1.0,
)

# Compare two replays
comparison = engine.compare_replays(session_1, session_2)
```

### Breakpoints

```python
from agent_trace.replay import get_breakpoint_manager
from agent_trace.replay.breakpoints import (
    break_on_llm_calls,
    break_on_tool_calls,
    break_on_errors,
    break_on_index,
    break_on_model,
    BreakpointType,
)

mgr = get_breakpoint_manager()

# Convenience functions
break_on_llm_calls(session_id)
break_on_errors(session_id)
break_on_index(session_id, index=5)
break_on_model(session_id, model="gpt-4")

# Custom breakpoint
mgr.add_breakpoint(
    session_id,
    BreakpointType.ACTION_TYPE,
    action_type=ReplayAction.TOOL_CALL,
    label="Stop at tools",
)

# Register hit callback
mgr.on_hit(session_id, lambda hit: print(f"Breakpoint hit: {hit.call.call_id}"))
```

### State Inspection & Forking

```python
# Inspect state at current position
state = controller.inspect_state(session_id)
# Returns: current call, call chain, token counts, output history

# Fork session at any point
forked = controller.fork_session(session_id, from_index=5)
# Creates a new session starting from the same position
```

## Real-time Streaming

The backend supports SSE (Server-Sent Events) for real-time trace updates:

```
GET /api/stream/traces  # SSE endpoint
```

Events:
- `trace.created` - New trace stored
- `trace.deleted` - Trace deleted
- `eval.run.progress` - Evaluation run progress
- `eval.run.completed` - Evaluation run finished

Frontend React hooks are available in `frontend/lib/sse.ts`:

```typescript
import { useTraceCreated, useTraceStreamCallback } from '@/lib/sse'

// Auto-refresh list when new traces arrive
useTraceStreamCallback(() => loadData(), ['trace.created', 'trace.deleted'])
```

## Project Structure

```
agent-eval-platform/
├── sdk/
│   ├── python/
│   │   └── agent_trace/
│   │       ├── __init__.py          # Package exports (45 items)
│   │       ├── models.py            # Data models (Span, Trace, SpanType)
│   │       ├── tracer.py            # Core tracer
│   │       ├── decorators.py        # @trace decorators
│   │       ├── exporters.py         # Data exporters (Console, File, HTTP, Batch)
│   │       ├── otel_attributes.py   # OTel GenAI attribute constants
│   │       ├── otel_mapper.py       # SpanType ↔ OTel operation mapping
│   │       ├── otel_exporter.py       # OTLP trace exporter
│   │       ├── eval/                # Evaluation framework
│   │       │   ├── base.py          # Evaluator ABC + EvaluationResult
│   │       │   ├── heuristic.py     # Regex, Contains, JsonValid, etc.
│   │       │   ├── llm_judge.py     # LLM-as-judge evaluator
│   │       │   ├── custom.py        # Custom callable evaluator
│   │       │   └── pipeline.py      # EvaluationPipeline orchestrator
│   │       ├── replay/              # Replay engine
│   │       │   ├── models.py        # ReplayLog, RecordedCall, ReplaySession
│   │       │   ├── recorder.py      # Execution recorder
│   │       │   ├── mock_server.py   # Mock LLM/tool servers
│   │       │   ├── controller.py    # Replay controller (play/pause/step/fork)
│   │       │   ├── breakpoints.py   # Breakpoint system (6 types)
│   │       │   └── engine.py        # Replay engine
│   │       └── integrations/        # Framework integrations (lazy-loaded)
│   │           ├── langgraph.py     # LangChain/LangGraph callback handler
│   │           ├── llamaindex.py    # LlamaIndex event handler
│   │           └── crewai.py        # CrewAI crew/agent/task tracer
│   └── typescript/
│       └── src/
│           ├── models.ts            # Data models (aligned with Python SDK)
│           ├── tracer.ts            # Core tracer
│           ├── instrumentation.ts   # Auto-instrumentation helpers
│           ├── exporters.ts         # Data exporters
│           ├── otel-attributes.ts   # OTel GenAI attribute constants
│           └── otel-mapper.ts       # SpanType ↔ OTel operation mapping
├── backend/
│   ├── app/
│   │   ├── auth.py                 # JWT auth + password hashing + API keys
│   │   ├── database.py             # Legacy DB wrapper
│   │   ├── errors.py               # Custom exceptions (NotFound, Validation, etc.)
│   │   ├── models.py               # Pydantic models
│   │   ├── db/                     # Database abstraction layer
│   │   │   ├── base.py             # Abstract TraceRepository + EvaluationRepository
│   │   │   ├── sqlite_impl.py      # SQLite implementations
│   │   │   ├── postgres_impl.py    # PostgreSQL implementations (psycopg2, JSONB)
│   │   │   ├── connection.py       # Connection factory (auto-detect SQLite/PostgreSQL)
│   │   │   └── migrations/         # Schema migration runner
│   │   │       ├── runner.py
│   │   │       └── versions/       # Migration files (001-003)
│   │   ├── api/
│   │   │   ├── traces.py           # Trace API + SSE notifications
│   │   │   ├── replay.py           # Replay API + breakpoints + state + fork
│   │   │   ├── evaluations.py      # Evaluation CRUD + runs + comparison
│   │   │   ├── analytics.py        # Time-series, model cost, latency, errors
│   │   │   ├── auth_routes.py      # Register, login, API keys, token refresh
│   │   │   ├── streaming.py        # SSE streaming endpoint
│   │   │   └── alerts.py           # Cost alert API
│   │   └── services/
│   │       ├── alerts.py           # Cost alert manager
│   │       └── evaluation_runner.py # Background eval runner
│   └── main.py                     # FastAPI app + error handlers + lifespan
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # Dashboard (traces list + stats)
│   │   ├── login/page.tsx          # Login / register page
│   │   ├── analytics/page.tsx      # Analytics dashboard (charts + tables)
│   │   ├── traces/
│   │   │   ├── [id]/page.tsx       # Trace detail (span tree + timeline)
│   │   │   └── compare/page.tsx    # Trace comparison
│   │   ├── sessions/
│   │   │   └── [id]/page.tsx       # Session/conversation view
│   │   └── evaluations/
│   │       ├── page.tsx            # Evaluation dashboard
│   │       ├── datasets/[id]/page.tsx # Dataset detail + item management
│   │       └── runs/[id]/page.tsx  # Eval run results + progress
│   ├── components/
│   │   ├── SpanTree.tsx            # Span tree visualization
│   │   ├── TimelineView.tsx        # Timeline visualization
│   │   └── ReplayPlayer.tsx        # Replay controls
│   └── lib/
│       ├── api.ts                  # Typed API client
│       ├── utils.ts                # Formatting utilities
│       └── sse.ts                  # SSE client + React hooks
├── examples/
│   ├── langgraph-agent/            # LangGraph tracing example
│   └── replay-demo/                # Replay engine demo
└── docker-compose.yml
```

## Architecture

```
Agent App → SDK (Decorators) → Exporter → Backend API → SQLite / PostgreSQL
                    ↓                          ↓
              OTLP Export              SSE Streaming → Web UI
                    ↓                          ↓
         Jaeger/Tempo/Datadog     Evaluation Runner → Results
                    ↓                          ↓
              Replay Engine → Mock Servers   Auth (JWT/API Keys)
                    ↓                          ↓
              Breakpoints → Fork       Analytics Dashboard
```

## API Endpoints

### Traces
- `POST /api/traces/` - Create/update a trace
- `GET /api/traces/` - List traces with filtering
- `GET /api/traces/{id}` - Get trace details
- `DELETE /api/traces/{id}` - Delete a trace
- `GET /api/traces/stats/summary` - Get statistics
- `GET /api/traces/sessions` - List sessions
- `GET /api/traces/sessions/{id}` - Get session traces

### Replay
- `POST /api/replay/export/{trace_id}` - Export trace as replay log
- `POST /api/replay/start` - Start a replay session
- `POST /api/replay/{id}/pause` - Pause replay
- `POST /api/replay/{id}/resume` - Resume replay
- `POST /api/replay/{id}/step` - Execute single step
- `POST /api/replay/{id}/stop` - Stop replay
- `GET /api/replay/{id}/status` - Get replay status
- `POST /api/replay/compare` - Compare two replays
- `GET /api/replay/logs` - List replay logs
- `POST /api/replay/{id}/breakpoints` - Add breakpoint
- `GET /api/replay/{id}/breakpoints` - List breakpoints
- `DELETE /api/replay/{id}/breakpoints/{bp_id}` - Remove breakpoint
- `GET /api/replay/{id}/state` - Inspect replay state
- `POST /api/replay/{id}/fork` - Fork replay session
- `GET /api/replay/{id}/breakpoint-hits` - Get hit history

### Streaming
- `GET /api/stream/traces` - SSE endpoint for real-time events

### Evaluations
- `POST /api/evaluations/datasets` - Create dataset
- `GET /api/evaluations/datasets` - List datasets
- `GET /api/evaluations/datasets/{id}` - Get dataset with items
- `PUT /api/evaluations/datasets/{id}` - Update dataset
- `DELETE /api/evaluations/datasets/{id}` - Delete dataset
- `POST /api/evaluations/datasets/{id}/items` - Add items
- `DELETE /api/evaluations/datasets/{id}/items/{item_id}` - Remove item
- `POST /api/evaluations/evaluators` - Create evaluator
- `GET /api/evaluations/evaluators` - List evaluators
- `GET /api/evaluations/evaluators/{id}` - Get evaluator
- `DELETE /api/evaluations/evaluators/{id}` - Delete evaluator
- `POST /api/evaluations/runs` - Start evaluation run (background)
- `GET /api/evaluations/runs` - List runs
- `GET /api/evaluations/runs/{id}` - Get run with results
- `GET /api/evaluations/runs/{id}/results` - Get run results
- `POST /api/evaluations/runs/{id}/cancel` - Cancel run
- `POST /api/evaluations/compare` - Compare two runs

### Analytics
- `GET /api/analytics/timeseries` - Time-series data (hour/day/week granularity)
- `GET /api/analytics/models` - Per-model cost, tokens, and latency breakdown
- `GET /api/analytics/latency` - Latency stats by span type (avg/min/max)
- `GET /api/analytics/errors` - Error rate, breakdown by type, recent errors
- `GET /api/analytics/top-traces` - Top traces by cost, latency, or tokens
- `GET /api/analytics/span-types` - Span type distribution with percentages

### Authentication
- `POST /api/auth/register` - Register new user (returns JWT token)
- `POST /api/auth/login` - Login with username/password (returns JWT token)
- `GET /api/auth/me` - Get current user profile
- `GET /api/auth/users` - List all users (admin only)
- `POST /api/auth/refresh` - Refresh JWT token
- `POST /api/auth/api-keys` - Create API key
- `GET /api/auth/api-keys` - List API keys
- `DELETE /api/auth/api-keys/{id}` - Delete API key

Auth methods: `Authorization: Bearer <jwt>` or `X-API-Key: <key>`

## Development

### Running Tests

```bash
cd sdk/python
python test_sdk.py      # Core SDK tests
python test_replay.py   # Replay engine tests
```

### Local Development

Start backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Start frontend:
```bash
cd frontend
npm install
npm run dev
```

Run examples:
```bash
cd examples/langgraph-agent
python main.py

cd ../replay-demo
python main.py
```

## Roadmap

- [x] Core SDK with tracing
- [x] LangGraph integration
- [x] SQLite storage
- [x] REST API
- [x] Replay engine
- [x] Web UI (Next.js)
- [x] TypeScript SDK
- [x] OTel GenAI semantic conventions
- [x] OTLP exporter
- [x] Evaluation framework
- [x] Real-time SSE streaming
- [x] Replay breakpoints & state inspection
- [x] Cost tracking and alerts
- [x] Database abstraction with migration path
- [x] PostgreSQL support
- [x] Framework integrations (LlamaIndex, CrewAI)
- [x] Advanced analytics & dashboards
- [x] Multi-user authentication
- [x] Docker Compose deployment
- [ ] OpenAI / Anthropic SDK auto-instrumentation
- [ ] Alert notification channels (Slack, email, webhook)
- [ ] Custom dashboard builder (drag-and-drop widgets)
- [ ] Trace sampling and filtering
- [ ] RBAC (role-based access control) with team/org support
- [ ] Data retention policies and auto-cleanup

## License

MIT
