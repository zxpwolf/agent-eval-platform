---
sidebar_position: 1
---

# API Overview

The Agent Trace Backend provides a RESTful API for storing, querying, and replaying traces.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, the API supports optional Bearer token authentication:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/traces
```

## Response Format

All responses are JSON:

```json
{
  "trace_id": "abc123",
  "name": "my_trace",
  "spans": [...]
}
```

## Error Responses

```json
{
  "error": "Not Found",
  "detail": "Trace xyz not found"
}
```

## API Sections

- [Traces API](/docs/api/traces) - Manage traces and spans
- [Replay API](/docs/api/replay) - Control replay sessions
- [Alerts API](/docs/api/alerts) - Cost alerting system

## SDK Integration

Instead of calling the API directly, use the SDK exporters:

```python
from agent_trace import HTTPEndpointExporter, BatchExporter

tracer._exporter = BatchExporter(
    exporter=HTTPEndpointExporter(
        endpoint="http://localhost:8000/api/traces",
        api_key="optional-api-key"
    )
)
```
