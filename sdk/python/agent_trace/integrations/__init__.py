"""Integration modules for various frameworks.

Framework-specific packages (llama_index, langchain, crewai) are optional
dependencies. Imports are lazy so missing packages don't break the SDK.
"""


def __getattr__(name: str):
    """Lazy-load integration classes to avoid hard dependency on frameworks."""
    _langgraph_exports = {"AgentTraceCallbackHandler"}
    _llamaindex_exports = {"LlamaIndexTraceHandler", "setup_llamaindex_tracing"}
    _crewai_exports = {"CrewAITraceHandler", "setup_crewai_tracing"}

    if name in _langgraph_exports:
        from .langgraph import AgentTraceCallbackHandler
        return AgentTraceCallbackHandler
    elif name in _llamaindex_exports:
        from . import llamaindex as _mod
        return getattr(_mod, name)
    elif name in _crewai_exports:
        from .crewai import CrewAITraceHandler, setup_crewai_tracing
        return CrewAITraceHandler if name == "CrewAITraceHandler" else setup_crewai_tracing
    raise AttributeError(f"module 'agent_trace.integrations' has no attribute {name!r}")


__all__ = [
    "AgentTraceCallbackHandler",
    "LlamaIndexTraceHandler",
    "setup_llamaindex_tracing",
    "CrewAITraceHandler",
    "setup_crewai_tracing",
]
