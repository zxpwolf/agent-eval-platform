"""API endpoints for trace sampling and advanced filtering."""

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.sampling import (
    SamplingStrategy,
    SamplingEngine,
    TraceFilter,
    create_sampling_rule,
    get_sampling_rule,
    list_sampling_rules,
    update_sampling_rule,
    delete_sampling_rule,
    get_sampling_engine,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sampling", tags=["sampling"])

DB_PATH = os.environ.get("TRACES_DB_PATH", "traces.db")


# ── Request Models ───────────────────────────────────────


class CreateSamplingRuleRequest(BaseModel):
    name: str
    strategy: str
    enabled: bool = True
    priority: int = 0
    params: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None


class UpdateSamplingRuleRequest(BaseModel):
    name: Optional[str] = None
    strategy: Optional[str] = None
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    params: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None


class AdvancedFilterRequest(BaseModel):
    name_pattern: Optional[str] = None
    user_ids: Optional[List[str]] = None
    session_ids: Optional[List[str]] = None
    models: Optional[List[str]] = None
    span_types: Optional[List[str]] = None
    status: Optional[str] = None
    min_cost: Optional[float] = None
    max_cost: Optional[float] = None
    min_latency_ms: Optional[float] = None
    max_latency_ms: Optional[float] = None
    start_time_from: Optional[float] = None
    start_time_to: Optional[float] = None
    attributes: Optional[Dict[str, Any]] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    sort_by: str = "start_time"
    sort_order: str = "desc"


# ── Sampling Rule Endpoints ─────────────────────────────


@router.post("/rules", status_code=201)
async def api_create_rule(request: CreateSamplingRuleRequest):
    """Create a new sampling rule."""
    valid_strategies = {
        SamplingStrategy.ALWAYS, SamplingStrategy.NEVER,
        SamplingStrategy.RATE, SamplingStrategy.LATENCY,
        SamplingStrategy.ERROR, SamplingStrategy.COST,
        SamplingStrategy.ATTRIBUTE,
    }
    if request.strategy not in valid_strategies:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid strategy. Must be one of: {', '.join(valid_strategies)}",
        )

    rule = create_sampling_rule(
        name=request.name,
        strategy=request.strategy,
        enabled=request.enabled,
        priority=request.priority,
        params=request.params,
        filters=request.filters,
    )

    # Reload engine rules
    engine = get_sampling_engine()
    engine.reload_rules()

    return rule


@router.get("/rules")
async def api_list_rules(enabled_only: bool = False):
    """List all sampling rules."""
    rules = list_sampling_rules(enabled_only=enabled_only)
    return {"rules": rules}


@router.get("/rules/{rule_id}")
async def api_get_rule(rule_id: str):
    """Get a sampling rule by ID."""
    rule = get_sampling_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Sampling rule not found")
    return rule


@router.patch("/rules/{rule_id}")
async def api_update_rule(rule_id: str, request: UpdateSamplingRuleRequest):
    """Update a sampling rule."""
    success = update_sampling_rule(rule_id, request.model_dump(exclude_unset=True))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update sampling rule")

    # Reload engine rules
    engine = get_sampling_engine()
    engine.reload_rules()

    return {"message": "Sampling rule updated"}


@router.delete("/rules/{rule_id}")
async def api_delete_rule(rule_id: str):
    """Delete a sampling rule."""
    success = delete_sampling_rule(rule_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete sampling rule")

    # Reload engine rules
    engine = get_sampling_engine()
    engine.reload_rules()

    return {"message": "Sampling rule deleted"}


@router.get("/stats")
async def api_get_sampling_stats():
    """Get sampling statistics."""
    engine = get_sampling_engine()
    return engine.get_stats()


@router.get("/strategies")
async def api_get_strategies():
    """Get available sampling strategies."""
    return {
        "strategies": [
            {
                "type": SamplingStrategy.ALWAYS,
                "description": "Keep all matching traces",
                "params": [],
            },
            {
                "type": SamplingStrategy.NEVER,
                "description": "Drop all matching traces",
                "params": [],
            },
            {
                "type": SamplingStrategy.RATE,
                "description": "Keep a percentage of traces (deterministic by trace_id)",
                "params": [
                    {"name": "rate", "type": "float", "description": "Sampling rate between 0.0 and 1.0", "default": 0.5},
                ],
            },
            {
                "type": SamplingStrategy.LATENCY,
                "description": "Keep traces exceeding a latency threshold",
                "params": [
                    {"name": "threshold_ms", "type": "float", "description": "Minimum latency in milliseconds", "default": 5000},
                ],
            },
            {
                "type": SamplingStrategy.ERROR,
                "description": "Keep or drop traces with error spans",
                "params": [
                    {"name": "keep_errors", "type": "bool", "description": "If True, keep error traces; if False, drop them", "default": True},
                ],
            },
            {
                "type": SamplingStrategy.COST,
                "description": "Keep traces above a cost threshold",
                "params": [
                    {"name": "threshold", "type": "float", "description": "Minimum cost to keep trace", "default": 0.01},
                ],
            },
            {
                "type": SamplingStrategy.ATTRIBUTE,
                "description": "Keep traces matching a metadata attribute",
                "params": [
                    {"name": "key", "type": "str", "description": "Attribute key in trace metadata"},
                    {"name": "value", "type": "any", "description": "Expected attribute value"},
                ],
            },
        ]
    }


# ── Advanced Filtering Endpoint ────────────────────────


@router.post("/filter")
async def api_filter_traces(request: AdvancedFilterRequest):
    """Advanced trace filtering with multiple criteria."""
    result = TraceFilter.filter_traces(
        db_path=DB_PATH,
        name_pattern=request.name_pattern,
        user_ids=request.user_ids,
        session_ids=request.session_ids,
        models=request.models,
        span_types=request.span_types,
        status=request.status,
        min_cost=request.min_cost,
        max_cost=request.max_cost,
        min_latency_ms=request.min_latency_ms,
        max_latency_ms=request.max_latency_ms,
        start_time_from=request.start_time_from,
        start_time_to=request.start_time_to,
        attributes=request.attributes,
        limit=request.limit,
        offset=request.offset,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
    )
    return result
