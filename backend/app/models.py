"""Pydantic models for API requests/responses."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SpanEventModel(BaseModel):
    """Span event model."""
    timestamp: float
    name: str
    attributes: Dict[str, Any] = {}


class SpanModel(BaseModel):
    """Span model for API."""
    span_id: str
    trace_id: str
    name: str
    span_type: str
    start_time: float
    end_time: Optional[float] = None
    parent_span_id: Optional[str] = None
    status: str = "ok"
    attributes: Dict[str, Any] = {}
    events: List[SpanEventModel] = []
    model: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None


class TraceModel(BaseModel):
    """Trace model for API."""
    trace_id: str
    name: str = ""
    start_time: float
    end_time: Optional[float] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = {}
    spans: List[SpanModel] = []


class TraceListItem(BaseModel):
    """Simplified trace item for list view."""
    trace_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    span_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    duration_ms: float = 0.0


class TraceListResponse(BaseModel):
    """Response for listing traces."""
    traces: List[TraceListItem]
    total: int


class StatsResponse(BaseModel):
    """Response for database statistics."""
    trace_count: int
    span_count: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float
    models: List[Dict[str, Any]]


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
