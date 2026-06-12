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

# OTel GenAI semantic conventions
from . import otel_attributes
from .otel_mapper import (
    span_type_to_otel_operation,
    otel_operation_to_span_type,
    enrich_span_with_otel,
)

# OTLP exporter
from .otel_exporter import OTLPExporter, OTLPExporterConfig

# Framework integrations (lazy-loaded to avoid hard dependencies)
from .integrations.crewai import CrewAITraceHandler, setup_crewai_tracing

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
    from .replay.breakpoints import (
        Breakpoint,
        BreakpointManager,
        BreakpointType,
        BreakpointHitInfo,
        get_breakpoint_manager,
        break_on_index,
        break_on_llm_calls,
        break_on_tool_calls,
        break_on_errors,
        break_on_model,
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
    # OTel
    "otel_attributes",
    "span_type_to_otel_operation",
    "otel_operation_to_span_type",
    "enrich_span_with_otel",
    # OTLP Exporter
    "OTLPExporter",
    "OTLPExporterConfig",
    # Framework Integrations
    "CrewAITraceHandler",
    "setup_crewai_tracing",
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
    # Breakpoints
    "Breakpoint",
    "BreakpointManager",
    "BreakpointType",
    "BreakpointHitInfo",
    "get_breakpoint_manager",
    "break_on_index",
    "break_on_llm_calls",
    "break_on_tool_calls",
    "break_on_errors",
    "break_on_model",
]
