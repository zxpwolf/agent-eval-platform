---
sidebar_position: 1
---

# Replay Engine Overview

The Replay Engine allows you to record agent executions and replay them deterministically for debugging and testing.

## Key Features

- **Deterministic Replay**: Reproduce exact agent behavior
- **Mock Servers**: Simulate LLM and tool responses without API costs
- **Playback Controls**: Play, pause, step through executions
- **Comparison Mode**: Compare different agent versions side-by-side

## Architecture

```
Agent Execution → Recorder → Replay Log → Mock Servers → Replay
```

## Basic Workflow

1. **Record**: Capture an agent execution
2. **Export**: Save as a replay log
3. **Replay**: Replay with mock responses
4. **Compare**: Identify differences between runs

## Quick Example

```python
from agent_trace.replay import get_engine

engine = get_engine()

# Export a trace as replay log
log_id = engine.export_replay_log(trace)

# Replay with mock LLM
session_id = await engine.replay_trace(
    trace_id=trace.trace_id,
    mock_llm=True,
    speed_multiplier=1.0
)

# Check status
status = engine.controller.get_status(session_id)
print(f"Progress: {status['progress']}%")
```

## Use Cases

### Debugging

Replay failed executions to understand what went wrong without incurring additional API costs.

### Regression Testing

Ensure agent behavior remains consistent across code changes.

### A/B Testing

Compare different prompts or models by replaying the same inputs.

### Training

Use recorded executions as training data for fine-tuning.
