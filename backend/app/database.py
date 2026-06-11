"""Database layer for storing traces in SQLite."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TraceDatabase:
    """SQLite database for storing and querying traces."""

    def __init__(self, db_path: str = "traces.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent performance
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            conn.executescript("""
                -- Traces table
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    user_id TEXT,
                    session_id TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Spans table
                CREATE TABLE IF NOT EXISTS spans (
                    span_id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    span_type TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    parent_span_id TEXT,
                    status TEXT NOT NULL DEFAULT 'ok',
                    attributes TEXT,
                    events TEXT,
                    model TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    cost REAL,
                    input_data TEXT,
                    output_data TEXT,
                    FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
                );

                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_traces_user_id ON traces(user_id);
                CREATE INDEX IF NOT EXISTS idx_traces_session_id ON traces(session_id);
                CREATE INDEX IF NOT EXISTS idx_traces_start_time ON traces(start_time DESC);
                CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
                CREATE INDEX IF NOT EXISTS idx_spans_parent_span_id ON spans(parent_span_id);
                CREATE INDEX IF NOT EXISTS idx_spans_span_type ON spans(span_type);
                CREATE INDEX IF NOT EXISTS idx_spans_model ON spans(model);
            """)
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
        finally:
            conn.close()

    def store_trace(self, trace_data: Dict[str, Any]) -> bool:
        """Store a complete trace with all its spans."""
        conn = self._get_connection()
        try:
            # Insert trace
            conn.execute(
                """
                INSERT OR REPLACE INTO traces
                (trace_id, name, start_time, end_time, user_id, session_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_data["trace_id"],
                    trace_data.get("name", ""),
                    trace_data["start_time"],
                    trace_data.get("end_time"),
                    trace_data.get("user_id"),
                    trace_data.get("session_id"),
                    json.dumps(trace_data.get("metadata", {})),
                ),
            )

            # Insert spans
            for span_data in trace_data.get("spans", []):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO spans
                    (span_id, trace_id, name, span_type, start_time, end_time,
                     parent_span_id, status, attributes, events, model,
                     prompt_tokens, completion_tokens, total_tokens, cost,
                     input_data, output_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        span_data["span_id"],
                        span_data["trace_id"],
                        span_data["name"],
                        span_data["span_type"],
                        span_data["start_time"],
                        span_data.get("end_time"),
                        span_data.get("parent_span_id"),
                        span_data.get("status", "ok"),
                        json.dumps(span_data.get("attributes", {})),
                        json.dumps(span_data.get("events", [])),
                        span_data.get("model"),
                        span_data.get("prompt_tokens"),
                        span_data.get("completion_tokens"),
                        span_data.get("total_tokens"),
                        span_data.get("cost"),
                        json.dumps(span_data.get("input_data")) if span_data.get("input_data") else None,
                        json.dumps(span_data.get("output_data")) if span_data.get("output_data") else None,
                    ),
                )

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store trace: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a trace by ID with all its spans."""
        conn = self._get_connection()
        try:
            # Get trace
            trace_row = conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()

            if not trace_row:
                return None

            trace = dict(trace_row)
            trace["metadata"] = json.loads(trace["metadata"]) if trace["metadata"] else {}

            # Get spans
            span_rows = conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC",
                (trace_id,),
            ).fetchall()

            spans = []
            for span_row in span_rows:
                span = dict(span_row)
                span["attributes"] = json.loads(span["attributes"]) if span["attributes"] else {}
                span["events"] = json.loads(span["events"]) if span["events"] else []
                span["input_data"] = json.loads(span["input_data"]) if span.get("input_data") else None
                span["output_data"] = json.loads(span["output_data"]) if span.get("output_data") else None
                spans.append(span)

            trace["spans"] = spans
            return trace
        except Exception as e:
            logger.error(f"Failed to get trace: {e}")
            return None
        finally:
            conn.close()

    def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List traces with optional filtering."""
        conn = self._get_connection()
        try:
            query = "SELECT * FROM traces WHERE 1=1"
            params = []

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)

            if model:
                query += " AND trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE model = ?)"
                params.append(model)

            query += " ORDER BY start_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()

            traces = []
            for row in rows:
                trace = dict(row)
                trace["metadata"] = json.loads(trace["metadata"]) if trace["metadata"] else {}

                # Get span count and total tokens
                stats = conn.execute(
                    """
                    SELECT COUNT(*) as span_count,
                           COALESCE(SUM(total_tokens), 0) as total_tokens,
                           COALESCE(SUM(cost), 0) as total_cost
                    FROM spans WHERE trace_id = ?
                    """,
                    (trace["trace_id"],),
                ).fetchone()

                trace["span_count"] = stats["span_count"]
                trace["total_tokens"] = stats["total_tokens"]
                trace["total_cost"] = stats["total_cost"]

                traces.append(trace)

            return traces
        except Exception as e:
            logger.error(f"Failed to list traces: {e}")
            return []
        finally:
            conn.close()

    def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace and all its spans."""
        conn = self._get_connection()
        try:
            conn.execute("DELETE FROM traces WHERE trace_id = ?", (trace_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete trace: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = self._get_connection()
        try:
            trace_count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
            span_count = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]

            token_stats = conn.execute(
                """
                SELECT
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cost), 0) as total_cost
                FROM spans
                WHERE total_tokens IS NOT NULL
                """
            ).fetchone()

            model_stats = conn.execute(
                """
                SELECT model, COUNT(*) as call_count,
                       COALESCE(SUM(total_tokens), 0) as tokens
                FROM spans
                WHERE model IS NOT NULL
                GROUP BY model
                ORDER BY call_count DESC
                """
            ).fetchall()

            return {
                "trace_count": trace_count,
                "span_count": span_count,
                "total_prompt_tokens": token_stats["total_prompt_tokens"],
                "total_completion_tokens": token_stats["total_completion_tokens"],
                "total_tokens": token_stats["total_tokens"],
                "total_cost": token_stats["total_cost"],
                "models": [dict(row) for row in model_stats],
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
        finally:
            conn.close()
