"""Database layer for storing traces in SQLite.

Backwards-compatible wrapper that delegates to the new repository-based
implementation in app.db. Existing code that imports TraceDatabase
continues to work unchanged.
"""

import logging
from typing import Any, Dict, List, Optional

from .db.sqlite_impl import SQLiteTraceRepository

logger = logging.getLogger(__name__)


class TraceDatabase:
    """SQLite database for storing and querying traces.

    This is a thin wrapper around SQLiteTraceRepository to maintain
    backwards compatibility with existing API modules.
    """

    def __init__(self, db_path: str = "traces.db"):
        self.db_path = db_path
        self._repo = SQLiteTraceRepository(db_path=db_path)
        # Ensure schema exists (for code that uses TraceDatabase directly
        # without going through the migration runner)
        self._ensure_legacy_schema()

    def _ensure_legacy_schema(self):
        """Run migrations to ensure the schema is up to date."""
        try:
            from .db.migrations.runner import run_migrations
            run_migrations(self.db_path)
        except Exception as e:
            logger.warning(f"Migration runner failed: {e}")
            # Fallback: create tables directly if migration runner fails
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript("""
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
            except Exception as e2:
                logger.error(f"Failed to initialize database: {e2}")
                raise
            finally:
                conn.close()

    def store_trace(self, trace_data: Dict[str, Any]) -> bool:
        """Store a complete trace with all its spans."""
        return self._repo.store_trace(trace_data)

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a trace by ID with all its spans."""
        return self._repo.get_trace(trace_id)

    def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List traces with optional filtering."""
        return self._repo.list_traces(
            limit=limit, offset=offset, user_id=user_id,
            session_id=session_id, model=model,
        )

    def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace and all its spans."""
        return self._repo.delete_trace(trace_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        return self._repo.get_stats()
