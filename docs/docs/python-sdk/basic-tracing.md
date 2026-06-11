---
sidebar_position: 2
---

# Basic Tracing

## Core Concepts

### Trace

A **Trace** represents a complete agent execution session. It contains multiple spans.

### Span

A **Span** is a unit of work within a trace (e.g., LLM call, tool execution).

### Span Types

- `AGENT`: High-level agent execution
- `LLM`: Language model API call
- `TOOL`: Tool/function invocation
- `CHAIN`: Sequential operations
- `RETRIEVER`: Vector search/retrieval
- `EMBEDDING`: Text embedding
- `FUNCTION`: Generic function call

## Using Decorators

### Basic Function Tracing

```python
from agent_trace import trace

@trace()
def my_function(arg1, arg2):
    return arg1 + arg2
```

### Custom Name and Type

```python
from agent_trace import trace
from agent_trace.models import SpanType

@trace(name="search_tool", span_type=SpanType.TOOL)
def search_web(query: str):
    return search(query)
```

### LLM Call Tracing

```python
from agent_trace import trace_llm

@trace_llm(model="gpt-4")
def call_llm(prompt: str):
    response = llm.complete(prompt)
    return response
```

## Manual Tracing

```python
from agent_trace import get_tracer
from agent_trace.models import SpanType

tracer = get_tracer()

# Start a trace
trace = tracer.start_trace(
    name="my_agent_run",
    user_id="user_123",
    session_id="session_abc"
)

# Create spans
span = tracer.start_span("my_operation", SpanType.FUNCTION)

# Record metrics
tracer.record_llm_call(
    span,
    model="gpt-4",
    prompt_tokens=100,
    completion_tokens=50,
    cost=0.003
)

# End span
tracer.end_span(span, output_data="result")

# End trace
tracer.end_trace(trace.trace_id)
```

## Exporters

### File Exporter

```python
from agent_trace import FileExporter

tracer._exporter = FileExporter("traces.jsonl")
```

### HTTP Exporter

```python
from agent_trace import HTTPEndpointExporter, BatchExporter

tracer._exporter = BatchExporter(
    exporter=HTTPEndpointExporter(
        endpoint="http://localhost:8000/api/traces"
    ),
    batch_size=10,
    flush_interval=5.0
)
```

### Console Exporter (Debugging)

```python
from agent_trace import ConsoleExporter

tracer._exporter = ConsoleExporter(pretty_print=True)
```
