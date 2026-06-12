"""API endpoints for trace management."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..database import TraceDatabase
from ..models import (
    ErrorResponse,
    StatsResponse,
    TraceListResponse,
    TraceListItem,
    TraceModel,
)
from .streaming import notify

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/traces", tags=["traces"])

# Global database instance
db: Optional[TraceDatabase] = None


def set_database(database: TraceDatabase):
    """Set the database instance."""
    global db
    db = database


@router.post("/", response_model=TraceModel, status_code=201)
async def create_trace(trace: TraceModel):
    """Create or update a trace."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    success = db.store_trace(trace.model_dump())
    if not success:
        raise HTTPException(status_code=500, detail="Failed to store trace")

    # Broadcast SSE event
    notify("trace.created", {
        "trace_id": trace.trace_id,
        "name": trace.name,
        "span_count": len(trace.spans),
    })

    return trace


@router.get("/{trace_id}", response_model=TraceModel)
async def get_trace(trace_id: str):
    """Get a trace by ID."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    trace_data = db.get_trace(trace_id)
    if trace_data is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    # Convert to Pydantic model
    return TraceModel(**trace_data)


@router.get("/", response_model=TraceListResponse)
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    model: Optional[str] = None,
):
    """List traces with optional filtering."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    traces_data = db.list_traces(
        limit=limit,
        offset=offset,
        user_id=user_id,
        session_id=session_id,
        model=model,
    )

    items = []
    for trace_data in traces_data:
        duration_ms = 0.0
        if trace_data.get("end_time") and trace_data.get("start_time"):
            duration_ms = (trace_data["end_time"] - trace_data["start_time"]) * 1000

        items.append(
            TraceListItem(
                trace_id=trace_data["trace_id"],
                name=trace_data["name"],
                start_time=trace_data["start_time"],
                end_time=trace_data.get("end_time"),
                user_id=trace_data.get("user_id"),
                session_id=trace_data.get("session_id"),
                span_count=trace_data.get("span_count", 0),
                total_tokens=trace_data.get("total_tokens", 0),
                total_cost=trace_data.get("total_cost", 0.0),
                duration_ms=duration_ms,
            )
        )

    return TraceListResponse(traces=items, total=len(items))


@router.delete("/{trace_id}")
async def delete_trace(trace_id: str):
    """Delete a trace."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    success = db.delete_trace(trace_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete trace")

    # Broadcast SSE event
    notify("trace.deleted", {"trace_id": trace_id})

    return {"message": "Trace deleted"}


@router.get("/stats/summary", response_model=StatsResponse)
async def get_stats():
    """Get database statistics."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    stats = db.get_stats()
    return StatsResponse(**stats)
