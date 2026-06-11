---
sidebar_position: 1
---

# Python SDK Installation

## Requirements

- Python 3.8+
- Optional: LangChain, LlamaIndex for integrations

## Install from PyPI

```bash
pip install agent-trace
```

## Install from Source

```bash
git clone https://github.com/agent-trace/agent-observability.git
cd agent-observability/sdk/python
pip install -e .
```

## Optional Dependencies

For LangGraph integration:
```bash
pip install langchain langgraph
```

For LlamaIndex integration:
```bash
pip install llama-index
```

## Verify Installation

```python
import agent_trace
print(agent_trace.__version__)
```
