# Agent Observability

Open-source observability and replay platform for AI Agents. Track, debug, and optimize your agent applications with minimal instrumentation.

## Features

- **Automatic Tracing**: Capture LLM calls, tool executions, and agent decision chains
- **LangGraph Integration**: Seamless integration with LangChain/LangGraph agents
- **Deterministic Replay**: Record and replay agent executions for debugging and testing
- **Mock Servers**: Simulate LLM and tool responses without API costs
- **Low Overhead**: Async batch exporting with <5% performance impact
- **SQLite Storage**: Lightweight storage perfect for local development
- **REST API**: FastAPI backend with comprehensive endpoints
- **Comparison Mode**: Compare multiple replays to identify differences

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

## Replay Engine

The replay engine allows you to record agent executions and replay them deterministically:

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

### Replay API Endpoints

- `POST /api/replay/export/{trace_id}` - Export trace as replay log
- `POST /api/replay/start` - Start a replay session
- `POST /api/replay/{session_id}/pause` - Pause replay
- `POST /api/replay/{session_id}/resume` - Resume replay
- `POST /api/replay/{session_id}/step` - Step through replay
- `GET /api/replay/{session_id}/status` - Get replay status
- `POST /api/replay/compare` - Compare two replays

## Project Structure

```
agent-observability/
├── sdk/
│   └── python/
│       └── agent_trace/
│           ├── __init__.py
│           ├── models.py        # Data models
│           ├── tracer.py        # Core tracer
│           ├── decorators.py    # @trace decorators
│           ├── exporters.py     # Data exporters
│           ├── integrations/
│           │   └── langgraph.py # LangGraph integration
│           └── replay/          # Replay engine
│               ├── models.py    # Replay data models
│               ├── recorder.py  # Execution recorder
│               ├── mock_server.py # Mock LLM/tool servers
│               ├── controller.py # Replay controller
│               └── engine.py    # Replay engine
├── backend/
│   ├── app/
│   │   ├── database.py         # SQLite storage
│   │   ├── models.py           # Pydantic models
│   │   └── api/
│   │       ├── traces.py       # Trace API
│   │       └── replay.py       # Replay API
│   └── main.py                 # FastAPI app
├── examples/
│   ├── langgraph-agent/        # LangGraph tracing example
│   └── replay-demo/            # Replay engine demo
└── docker-compose.yml
```

## Architecture

```
Agent App → SDK (Decorators) → Exporter → Backend API → SQLite
                                    ↓
                              Replay Engine → Mock Servers
                                    ↓
                              Web UI (coming soon)
```

## Examples

See the `examples/` directory for complete examples:

- `langgraph-agent/main.py`: LangGraph agent with tracing
- `replay-demo/main.py`: Replay engine demonstration

## API Endpoints

### Traces
- `POST /api/traces/` - Create/update a trace
- `GET /api/traces/` - List traces with filtering
- `GET /api/traces/{id}` - Get trace details
- `DELETE /api/traces/{id}` - Delete a trace
- `GET /api/traces/stats/summary` - Get statistics

### Replay
- `POST /api/replay/export/{trace_id}` - Export trace as replay log
- `POST /api/replay/start` - Start a replay session
- `POST /api/replay/{session_id}/pause` - Pause replay
- `POST /api/replay/{session_id}/resume` - Resume replay
- `POST /api/replay/{session_id}/step` - Execute single step
- `POST /api/replay/{session_id}/stop` - Stop replay
- `GET /api/replay/{session_id}/status` - Get replay status
- `POST /api/replay/compare` - Compare two replays
- `GET /api/replay/logs` - List replay logs

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
- [ ] Web UI (Next.js)
- [ ] TypeScript SDK
- [ ] More framework integrations (LlamaIndex, CrewAI)
- [ ] Cost tracking and alerts
- [ ] Advanced analytics

## License

MIT
