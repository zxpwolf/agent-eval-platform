"""API endpoints for replay functionality."""

import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from ..database import TraceDatabase
from ..models import ErrorResponse, TraceModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/replay", tags=["replay"])

# Global instances
db: Optional[TraceDatabase] = None
engine = None


def set_database(database: TraceDatabase):
    """Set the database instance."""
    global db
    db = database


def set_replay_engine(replay_engine):
    """Set the replay engine instance."""
    global engine
    engine = replay_engine


@router.post("/export/{trace_id}")
async def export_replay_log(trace_id: str):
    """Export a trace as a replay log.

    Converts a stored trace into a replay log format that can be used
    for deterministic replay.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    # Get the trace
    trace_data = db.get_trace(trace_id)
    if not trace_data:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")

    # Convert to Trace model
    trace = TraceModel(**trace_data)

    # Export as replay log
    from agent_trace.models import Span, SpanType, Trace

    # Create Trace object
    trace_obj = Trace(
        trace_id=trace.trace_id,
        name=trace.name,
        start_time=trace.start_time,
        end_time=trace.end_time,
        user_id=trace.user_id,
        session_id=trace.session_id,
        metadata=trace.metadata,
    )

    # Add spans
    for span_data in trace.spans:
        span = Span(
            trace_id=span_data.trace_id,
            span_id=span_data.span_id,
            name=span_data.name,
            span_type=SpanType(span_data.span_type),
            start_time=span_data.start_time,
            end_time=span_data.end_time,
            parent_span_id=span_data.parent_span_id,
            status=span_data.status,
            attributes=span_data.attributes,
            model=span_data.model,
            prompt_tokens=span_data.prompt_tokens,
            completion_tokens=span_data.completion_tokens,
            total_tokens=span_data.total_tokens,
            cost=span_data.cost,
            input_data=span_data.input_data,
            output_data=span_data.output_data,
        )
        trace_obj.spans.append(span)

    # Export
    log_id = engine.export_replay_log(trace_obj)
    if not log_id:
        raise HTTPException(status_code=500, detail="Failed to export replay log")

    return {"log_id": log_id, "message": "Replay log exported successfully"}


@router.post("/start")
async def start_replay(
    trace_id: str,
    mock_llm: bool = True,
    mock_tools: bool = False,
    speed_multiplier: float = 1.0,
):
    """Start a replay session.

    Begins deterministic replay of a recorded trace.
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    session_id = await engine.replay_trace(
        trace_id=trace_id,
        mock_llm=mock_llm,
        mock_tools=mock_tools,
        speed_multiplier=speed_multiplier,
    )

    if not session_id:
        raise HTTPException(status_code=500, detail="Failed to start replay")

    return {
        "session_id": session_id,
        "trace_id": trace_id,
        "status": "started",
    }


@router.post("/{session_id}/pause")
async def pause_replay(session_id: str):
    """Pause an active replay session."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    success = engine.controller.pause(session_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to pause replay")

    return {"session_id": session_id, "status": "paused"}


@router.post("/{session_id}/resume")
async def resume_replay(session_id: str):
    """Resume a paused replay session."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    success = engine.controller.resume(session_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume replay")

    return {"session_id": session_id, "status": "resumed"}


@router.post("/{session_id}/step")
async def step_replay(session_id: str):
    """Execute a single step in the replay."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    result = await engine.controller.step(session_id)
    if result is None:
        raise HTTPException(status_code=400, detail="No more steps to execute")

    return {"session_id": session_id, "step_result": result}


@router.post("/{session_id}/stop")
async def stop_replay(session_id: str):
    """Stop an active replay session."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    success = engine.controller.stop(session_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to stop replay")

    return {"session_id": session_id, "status": "stopped"}


@router.get("/{session_id}/status")
async def get_replay_status(session_id: str):
    """Get the status of a replay session."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    status = engine.controller.get_status(session_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return status


@router.get("/sessions")
async def list_replay_sessions():
    """List all replay sessions."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    sessions = engine.controller.list_sessions()
    return {"sessions": sessions}


@router.post("/compare")
async def compare_replays(session_id_1: str, session_id_2: str):
    """Compare two replay sessions."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    comparison = engine.compare_replays(session_id_1, session_id_2)
    return comparison


@router.get("/logs")
async def list_replay_logs():
    """List all available replay logs."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    logs = engine.recorder.list_logs()
    return {"logs": logs}


@router.delete("/logs/{log_id}")
async def delete_replay_log(log_id: str):
    """Delete a replay log."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    success = engine.recorder.delete_log(log_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Log {log_id} not found")

    return {"message": "Replay log deleted"}


# ── Breakpoint & State Inspection endpoints ──────────────────


@router.post("/{session_id}/breakpoints")
async def add_breakpoint(session_id: str, body: Dict[str, Any]):
    """Add a breakpoint to a replay session.

    Body: {"type": "index|call_id|action_type|error|model",
           "index": 5, "call_id": "...", "action_type": "llm_call", "model": "gpt-4"}
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    from agent_trace.replay.breakpoints import (
        BreakpointType,
        get_breakpoint_manager,
    )
    from agent_trace.replay.models import ReplayAction

    bp_type_str = body.get("type")
    if not bp_type_str:
        raise HTTPException(status_code=400, detail="'type' is required")

    try:
        bp_type = BreakpointType(bp_type_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid breakpoint type: {bp_type_str}")

    mgr = get_breakpoint_manager()

    kwargs: Dict[str, Any] = {"label": body.get("label", "")}
    if bp_type == BreakpointType.INDEX:
        kwargs["index"] = body.get("index")
    elif bp_type == BreakpointType.CALL_ID:
        kwargs["call_id"] = body.get("call_id")
    elif bp_type == BreakpointType.ACTION_TYPE:
        action_str = body.get("action_type")
        if action_str:
            kwargs["action_type"] = ReplayAction(action_str)
    elif bp_type == BreakpointType.MODEL:
        kwargs["model"] = body.get("model")

    bp = mgr.add_breakpoint(session_id, bp_type, **kwargs)
    return bp.to_dict()


@router.get("/{session_id}/breakpoints")
async def list_breakpoints(session_id: str):
    """List all breakpoints for a replay session."""
    from agent_trace.replay.breakpoints import get_breakpoint_manager

    mgr = get_breakpoint_manager()
    bps = mgr.get_breakpoints(session_id)
    return {"breakpoints": [bp.to_dict() for bp in bps]}


@router.delete("/{session_id}/breakpoints/{breakpoint_id}")
async def remove_breakpoint(session_id: str, breakpoint_id: str):
    """Remove a breakpoint."""
    from agent_trace.replay.breakpoints import get_breakpoint_manager

    mgr = get_breakpoint_manager()
    success = mgr.remove_breakpoint(session_id, breakpoint_id)
    if not success:
        raise HTTPException(status_code=404, detail="Breakpoint not found")
    return {"message": "Breakpoint removed"}


@router.get("/{session_id}/state")
async def inspect_replay_state(session_id: str):
    """Inspect the full state of a replay session at its current position."""
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    state = engine.controller.inspect_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return state


@router.post("/{session_id}/fork")
async def fork_replay(session_id: str, from_index: Optional[int] = None):
    """Fork a replay session at the current or specified index.

    Creates a new session starting from the same position.
    """
    if engine is None:
        raise HTTPException(status_code=500, detail="Replay engine not initialized")

    forked = engine.controller.fork_session(session_id, from_index=from_index)
    if not forked:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return {
        "session_id": forked.session_id,
        "trace_id": forked.trace_id,
        "status": forked.status.value,
        "current_index": forked.current_index,
        "forked_from": session_id,
    }


@router.get("/{session_id}/breakpoint-hits")
async def get_breakpoint_hits(session_id: str):
    """Get the breakpoint hit history for a session."""
    from agent_trace.replay.breakpoints import get_breakpoint_manager

    mgr = get_breakpoint_manager()
    hits = mgr.get_hit_history(session_id)
    return {"hits": [h.to_dict() for h in hits]}
