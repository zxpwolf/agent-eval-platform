"""Agent Trace - Observability and Replay for AI Agents."""

from .decorators import trace, trace_llm
from .exporters import (
    BatchExporter,
    ConsoleExporter,
    Exporter,
    FileExporter,
    HTTPEndpointExporter,
)
from .models import Span, SpanEvent, SpanStatus, SpanType, Trace
from .privacy import PIIMasker, get_masker, mask_pii, set_masker
from .tracer import Tracer, get_tracer, set_tracer

# Replay module
try:
    from . import replay
    from .replay import (
        ExecutionRecorder,
        ReplayController,
        ReplayEngine,
        ReplayLog,
        RecordedCall,
        ReplaySession,
        get_controller,
        get_engine,
        get_recorder,
    )
except ImportError:
    # Replay module is optional
    pass

__version__ = "0.1.0"
__all__ = [
    # Core
    "Tracer",
    "get_tracer",
    "set_tracer",
    # Models
    "Trace",
    "Span",
    "SpanEvent",
    "SpanType",
    "SpanStatus",
    # Decorators
    "trace",
    "trace_llm",
    # Privacy
    "PIIMasker",
    "get_masker",
    "mask_pii",
    "set_masker",
    # Exporters
    "Exporter",
    "ConsoleExporter",
    "FileExporter",
    "BatchExporter",
    "HTTPEndpointExporter",
    # Replay
    "replay",
    "ReplayEngine",
    "ReplayController",
    "ExecutionRecorder",
    "ReplayLog",
    "RecordedCall",
    "ReplaySession",
    "get_engine",
    "get_controller",
    "get_recorder",
]
