---
sidebar_position: 1
---

# Quick Start

Get started with Agent Trace in less than 5 minutes.

## What is Agent Trace?

Agent Trace is an open-source observability platform for AI Agents. It helps you:

- **Trace** agent executions automatically
- **Debug** issues with deterministic replay
- **Monitor** costs and performance
- **Compare** different agent versions

## Installation

### Python

```bash
pip install agent-trace
```

### TypeScript

```bash
npm install @agent-trace/sdk
```

## Basic Usage

### Python Example

```python
from agent_trace import trace, get_tracer, FileExporter

# Setup tracer
tracer = get_tracer()
tracer._exporter = FileExporter("traces.jsonl")

# Add tracing to your functions
@trace()
def my_agent_function(input: str):
    return process(input)

@trace(span_type="llm")
def call_llm(prompt: str):
    return llm.generate(prompt)

# Execute - traces are automatically captured
result = my_agent_function("Hello")
```

### TypeScript Example

```typescript
import { trace, getTracer, FileExporter } from '@agent-trace/sdk';

// Setup tracer
const tracer = getTracer();
tracer.setExporter(new FileExporter('traces.jsonl'));

// Add tracing to your functions
const myFunction = trace(
  async (input: string) => {
    return await process(input);
  },
  'my_function'
);

// Execute - traces are automatically captured
const result = await myFunction('Hello');
```

## View Traces

### Option 1: File Output

Traces are saved to `traces.jsonl` in JSONL format. Each line is a complete trace.

### Option 2: Backend + Web UI

Start the backend server:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Visit http://localhost:8000/docs for API documentation.

## Next Steps

- Learn about [Python SDK](/docs/python-sdk/installation)
- Explore [Replay Engine](/docs/replay/overview)
- Check out [Examples](/docs/examples/langgraph-agent)
