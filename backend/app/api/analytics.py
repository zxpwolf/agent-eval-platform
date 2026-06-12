"""API endpoints for analytics and dashboards."""

import json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..database import TraceDatabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Global database instance
db: Optional[TraceDatabase] = None


def set_database(database: TraceDatabase):
    """Set the database instance."""
    global db
    db = database


def _get_conn() -> sqlite3.Connection:
    """Get a direct SQLite connection for analytics queries."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ── Time Series ────────────────────────────────────────────


@router.get("/timeseries")
async def get_timeseries(
    granularity: str = Query(default="hour", pattern="^(hour|day|week)$"),
    limit: int = Query(default=48, ge=1, le=720),
):
    """Get time-series data for traces, spans, tokens, and cost.

    Returns aggregated data bucketed by the specified granularity.
    """
    conn = _get_conn()
    try:
        if granularity == "hour":
            bucket_expr = "CAST(strftime('%s', datetime(start_time, 'unixepoch')) / 3600 AS INTEGER) * 3600"
            group_order = "bucket"
        elif granularity == "day":
            bucket_expr = "CAST(strftime('%s', datetime(start_time, 'unixepoch', 'start of day')) AS INTEGER)"
            group_order = "bucket"
        else:  # week
            bucket_expr = "CAST(strftime('%s', datetime(start_time, 'unixepoch', 'start of day', 'weekday 0', '-6 days')) AS INTEGER)"
            group_order = "bucket"

        # Trace time series
        rows = conn.execute(
            f"""
            SELECT {bucket_expr} as bucket, COUNT(*) as count
            FROM traces
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        trace_series = [{"timestamp": r["bucket"], "count": r["count"]} for r in reversed(rows)]

        # Span time series
        rows = conn.execute(
            f"""
            SELECT {bucket_expr} as bucket, COUNT(*) as count
            FROM spans
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        span_series = [{"timestamp": r["bucket"], "count": r["count"]} for r in reversed(rows)]

        # Cost time series
        rows = conn.execute(
            f"""
            SELECT {bucket_expr} as bucket,
                   COALESCE(SUM(cost), 0) as total_cost,
                   COALESCE(SUM(total_tokens), 0) as total_tokens
            FROM spans
            WHERE cost IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        cost_series = [
            {
                "timestamp": r["bucket"],
                "cost": r["total_cost"],
                "tokens": r["total_tokens"],
            }
            for r in reversed(rows)
        ]

        # Error rate time series
        rows = conn.execute(
            f"""
            SELECT {bucket_expr} as bucket,
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors
            FROM spans
            GROUP BY bucket
            ORDER BY bucket DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        error_series = [
            {
                "timestamp": r["bucket"],
                "total": r["total"],
                "errors": r["errors"],
                "error_rate": round(r["errors"] / r["total"], 4) if r["total"] > 0 else 0,
            }
            for r in reversed(rows)
        ]

        return {
            "granularity": granularity,
            "trace_series": trace_series,
            "span_series": span_series,
            "cost_series": cost_series,
            "error_series": error_series,
        }
    except Exception as e:
        logger.error(f"Analytics timeseries error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Model Analytics ────────────────────────────────────────


@router.get("/models")
async def get_model_analytics():
    """Get per-model analytics: cost, tokens, call count, avg latency."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT
                model,
                COUNT(*) as call_count,
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(cost), 0) as total_cost,
                AVG(CASE WHEN end_time IS NOT NULL AND start_time IS NOT NULL
                    THEN (end_time - start_time) * 1000 ELSE NULL END) as avg_latency_ms,
                MIN(start_time) as first_seen,
                MAX(start_time) as last_seen
            FROM spans
            WHERE model IS NOT NULL
            GROUP BY model
            ORDER BY total_cost DESC
            """
        ).fetchall()

        models = []
        for r in rows:
            models.append({
                "model": r["model"],
                "call_count": r["call_count"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "total_tokens": r["total_tokens"],
                "total_cost": r["total_cost"],
                "avg_latency_ms": round(r["avg_latency_ms"], 2) if r["avg_latency_ms"] else None,
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
            })

        return {"models": models}
    except Exception as e:
        logger.error(f"Analytics models error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Latency Analytics ──────────────────────────────────────


@router.get("/latency")
async def get_latency_analytics():
    """Get latency percentiles by span type."""
    conn = _get_conn()
    try:
        # Get latency stats per span type
        rows = conn.execute(
            """
            SELECT
                span_type,
                COUNT(*) as count,
                AVG((end_time - start_time) * 1000) as avg_ms,
                MIN((end_time - start_time) * 1000) as min_ms,
                MAX((end_time - start_time) * 1000) as max_ms
            FROM spans
            WHERE end_time IS NOT NULL AND start_time IS NOT NULL
            GROUP BY span_type
            ORDER BY avg_ms DESC
            """
        ).fetchall()

        by_type = []
        for r in rows:
            by_type.append({
                "span_type": r["span_type"],
                "count": r["count"],
                "avg_ms": round(r["avg_ms"], 2),
                "min_ms": round(r["min_ms"], 2),
                "max_ms": round(r["max_ms"], 2),
            })

        # Overall latency stats
        overall = conn.execute(
            """
            SELECT
                COUNT(*) as count,
                AVG((end_time - start_time) * 1000) as avg_ms,
                MIN((end_time - start_time) * 1000) as min_ms,
                MAX((end_time - start_time) * 1000) as max_ms
            FROM spans
            WHERE end_time IS NOT NULL AND start_time IS NOT NULL
            """
        ).fetchone()

        return {
            "by_type": by_type,
            "overall": {
                "count": overall["count"],
                "avg_ms": round(overall["avg_ms"], 2) if overall["avg_ms"] else 0,
                "min_ms": round(overall["min_ms"], 2) if overall["min_ms"] else 0,
                "max_ms": round(overall["max_ms"], 2) if overall["max_ms"] else 0,
            },
        }
    except Exception as e:
        logger.error(f"Analytics latency error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Error Analytics ────────────────────────────────────────


@router.get("/errors")
async def get_error_analytics():
    """Get error rate and error breakdown by type."""
    conn = _get_conn()
    try:
        # Overall error rate
        total = conn.execute("SELECT COUNT(*) as cnt FROM spans").fetchone()["cnt"]
        errors = conn.execute(
            "SELECT COUNT(*) as cnt FROM spans WHERE status = 'error'"
        ).fetchone()["cnt"]

        # Errors by span type
        rows = conn.execute(
            """
            SELECT span_type, COUNT(*) as error_count
            FROM spans
            WHERE status = 'error'
            GROUP BY span_type
            ORDER BY error_count DESC
            """
        ).fetchall()
        by_type = [{"span_type": r["span_type"], "count": r["error_count"]} for r in rows]

        # Recent errors (last 20)
        rows = conn.execute(
            """
            SELECT s.span_id, s.trace_id, s.name, s.span_type, s.start_time,
                   t.name as trace_name
            FROM spans s
            LEFT JOIN traces t ON s.trace_id = t.trace_id
            WHERE s.status = 'error'
            ORDER BY s.start_time DESC
            LIMIT 20
            """
        ).fetchall()
        recent_errors = []
        for r in rows:
            # Get the exception event if present
            span_row = conn.execute(
                "SELECT events FROM spans WHERE span_id = ?", (r["span_id"],)
            ).fetchone()
            events = json.loads(span_row["events"]) if span_row and span_row["events"] else []
            error_event = next((e for e in events if e.get("name") == "exception"), None)

            recent_errors.append({
                "span_id": r["span_id"],
                "trace_id": r["trace_id"],
                "trace_name": r["trace_name"],
                "span_name": r["name"],
                "span_type": r["span_type"],
                "start_time": r["start_time"],
                "error_type": error_event["attributes"].get("type", "Unknown") if error_event else "Unknown",
                "error_message": error_event["attributes"].get("message", "") if error_event else "",
            })

        return {
            "total_spans": total,
            "error_count": errors,
            "error_rate": round(errors / total, 4) if total > 0 else 0,
            "by_type": by_type,
            "recent_errors": recent_errors,
        }
    except Exception as e:
        logger.error(f"Analytics errors error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Top Traces ─────────────────────────────────────────────


@router.get("/top-traces")
async def get_top_traces(
    sort_by: str = Query(default="cost", pattern="^(cost|latency|tokens)$"),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get top traces sorted by cost, latency, or token usage."""
    conn = _get_conn()
    try:
        if sort_by == "cost":
            order_clause = "total_cost DESC"
        elif sort_by == "latency":
            order_clause = "duration_ms DESC"
        else:  # tokens
            order_clause = "total_tokens DESC"

        rows = conn.execute(
            f"""
            SELECT
                t.trace_id,
                t.name,
                t.start_time,
                t.end_time,
                t.user_id,
                t.session_id,
                COUNT(s.span_id) as span_count,
                COALESCE(SUM(s.total_tokens), 0) as total_tokens,
                COALESCE(SUM(s.cost), 0) as total_cost,
                CASE WHEN t.end_time IS NOT NULL AND t.start_time IS NOT NULL
                    THEN (t.end_time - t.start_time) * 1000 ELSE 0 END as duration_ms
            FROM traces t
            LEFT JOIN spans s ON t.trace_id = s.trace_id
            GROUP BY t.trace_id
            ORDER BY {order_clause}
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        traces = []
        for r in rows:
            traces.append({
                "trace_id": r["trace_id"],
                "name": r["name"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "user_id": r["user_id"],
                "session_id": r["session_id"],
                "span_count": r["span_count"],
                "total_tokens": r["total_tokens"],
                "total_cost": r["total_cost"],
                "duration_ms": round(r["duration_ms"], 2),
            })

        return {"sort_by": sort_by, "traces": traces}
    except Exception as e:
        logger.error(f"Analytics top traces error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ── Span Type Distribution ─────────────────────────────────


@router.get("/span-types")
async def get_span_type_distribution():
    """Get distribution of spans by type with cost and token breakdowns."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT
                span_type,
                COUNT(*) as count,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(cost), 0) as total_cost,
                AVG(CASE WHEN end_time IS NOT NULL AND start_time IS NOT NULL
                    THEN (end_time - start_time) * 1000 ELSE NULL END) as avg_latency_ms,
                SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as error_count
            FROM spans
            GROUP BY span_type
            ORDER BY count DESC
            """
        ).fetchall()

        types = []
        total_count = sum(r["count"] for r in rows)
        for r in rows:
            types.append({
                "span_type": r["span_type"],
                "count": r["count"],
                "percentage": round(r["count"] / total_count, 4) if total_count > 0 else 0,
                "total_tokens": r["total_tokens"],
                "total_cost": r["total_cost"],
                "avg_latency_ms": round(r["avg_latency_ms"], 2) if r["avg_latency_ms"] else 0,
                "error_count": r["error_count"],
            })

        return {"span_types": types}
    except Exception as e:
        logger.error(f"Analytics span types error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
