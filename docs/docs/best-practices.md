---
sidebar_position: 10
---

# Best Practices

## Performance

### Minimize Overhead

```python
# Use batch exporting for production
from agent_trace import BatchExporter, HTTPEndpointExporter

tracer._exporter = BatchExporter(
    exporter=HTTPEndpointExporter("http://localhost:8000/api/traces"),
    batch_size=20,
    flush_interval=10.0
)
```

### Sample in Production

```python
import random

if random.random() < 0.1:  # Trace 10% of requests
    tracer = get_tracer()
    # ... tracing code
```

## Privacy & Security

### Enable PII Masking

```python
from agent_trace import PIIMasker, FileExporter

masker = PIIMasker(enabled=True)
tracer._exporter = FileExporter(
    "traces.jsonl",
    pii_masker=masker
)
```

### Custom PII Patterns

```python
masker.add_pattern(
    name="custom_token",
    pattern=r'\btok-[a-zA-Z0-9]{20}\b',
    mask_value='[TOKEN_REDACTED]'
)
```

## Organization

### Use Meaningful Names

```python
# Good
@trace(name="customer_support_agent")

# Bad
@trace()
```

### Add Metadata

```python
trace = tracer.start_trace(
    name="rag_query",
    metadata={
        "environment": "production",
        "version": "1.2.3",
        "feature": "search"
    }
)
```

### Group by Session

```python
trace = tracer.start_trace(
    name="chat_session",
    session_id=user_session_id,
    user_id=current_user_id
)
```

## Cost Management

### Set Budget Alerts

```bash
curl -X POST http://localhost:8000/api/alerts/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily Budget",
    "threshold": 10.0,
    "level": "warning"
  }'
```

### Track by Model

```python
# Always specify model name
tracer.record_llm_call(
    span,
    model="gpt-4-turbo",  # Be specific
    prompt_tokens=prompt_tokens,
    completion_tokens=completion_tokens
)
```

## Error Handling

### Capture Exceptions

```python
@trace()
def risky_operation():
    try:
        return do_something()
    except Exception as e:
        # Error is automatically recorded
        raise
```

### Add Context

```python
span = tracer.start_span("operation")
try:
    result = execute()
except Exception as e:
    tracer.record_event(span, "error_context", {
        "input_size": len(input_data),
        "retry_count": retry_count
    })
    raise
```

## Testing

### Unit Tests with Console Exporter

```python
import pytest
from agent_trace import ConsoleExporter

@pytest.fixture
def tracer():
    t = get_tracer()
    t._exporter = ConsoleExporter(pretty_print=False)
    return t

def test_agent(tracer):
    # Test code here
    pass
```

### Replay for Regression Tests

```python
async def test_regression():
    engine = get_engine()

    # Record baseline
    baseline_log_id = engine.export_replay_log(baseline_trace)

    # Run new version
    new_trace = run_agent_v2()
    new_log_id = engine.export_replay_log(new_trace)

    # Compare
    comparison = engine.compare_logs(baseline_log_id, new_log_id)
    assert len(comparison['differences']) == 0
```
