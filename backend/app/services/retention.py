"""Data retention policies and auto-cleanup service.

Provides configurable retention policies for traces, spans, and
other data. Supports automatic cleanup of expired data based on
age, count, or size thresholds. Can run cleanup on schedule or
on-demand.
"""

import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("TRACES_DB_PATH", "traces.db")


# ── Retention Policy Types ──────────────────────────────


class RetentionType:
    """Available retention policy types."""
    AGE = "age"            # Delete data older than N days
    COUNT = "count"        # Keep at most N traces
    SIZE = "size"          # Keep database under N MB


class RetentionPolicy:
    """A single retention policy with type and parameters."""

    def __init__(
        self,
        policy_id: str,
        name: str,
        retention_type: str,
        enabled: bool = True,
        params: Optional[Dict[str, Any]] = None,
        scope: str = "all",
        created_at: Optional[float] = None,
        last_run: Optional[float] = None,
    ):
        self.policy_id = policy_id
        self.name = name
        self.retention_type = retention_type
        self.enabled = enabled
        self.params = params or {}
        self.scope = scope  # "all", "traces", "spans", "evaluations", "alerts"
        self.created_at = created_at or time.time()
        self.last_run = last_run

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "retention_type": self.retention_type,
            "enabled": self.enabled,
            "params": self.params,
            "scope": self.scope,
            "created_at": self.created_at,
            "last_run": self.last_run,
        }


# ── Database Schema ─────────────────────────────────────


def _ensure_retention_tables():
    """Create retention policy tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retention_policies (
                policy_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                retention_type TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                params TEXT NOT NULL DEFAULT '{}',
                scope TEXT NOT NULL DEFAULT 'all',
                created_at REAL,
                last_run REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS retention_runs (
                run_id TEXT PRIMARY KEY,
                policy_id TEXT NOT NULL,
                started_at REAL NOT NULL,
                completed_at REAL,
                status TEXT NOT NULL DEFAULT 'running',
                items_deleted INTEGER NOT NULL DEFAULT 0,
                bytes_freed INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                FOREIGN KEY (policy_id) REFERENCES retention_policies(policy_id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_retention_runs_policy ON retention_runs(policy_id)")
        conn.commit()
    finally:
        conn.close()


# ── Retention Engine ────────────────────────────────────


class RetentionEngine:
    """Executes retention policies and manages cleanup."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH

    def run_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single retention policy.

        Returns a summary of what was deleted.
        """
        import secrets
        run_id = secrets.token_hex(8)
        started_at = time.time()

        # Record run start
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO retention_runs
                (run_id, policy_id, started_at, status)
                VALUES (?, ?, ?, 'running')""",
                (run_id, policy["policy_id"], started_at),
            )
            conn.commit()
        finally:
            conn.close()

        try:
            result = self._execute_policy(policy)
            completed_at = time.time()

            # Record run completion
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    """UPDATE retention_runs
                    SET completed_at = ?, status = 'completed',
                        items_deleted = ?, bytes_freed = ?
                    WHERE run_id = ?""",
                    (completed_at, result["items_deleted"], result["bytes_freed"], run_id),
                )
                # Update policy last_run
                conn.execute(
                    "UPDATE retention_policies SET last_run = ? WHERE policy_id = ?",
                    (completed_at, policy["policy_id"]),
                )
                conn.commit()
            finally:
                conn.close()

            result["run_id"] = run_id
            result["duration_ms"] = (completed_at - started_at) * 1000
            return result

        except Exception as e:
            logger.error(f"Retention policy execution failed: {e}")
            # Record run failure
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    """UPDATE retention_runs
                    SET completed_at = ?, status = 'failed', error = ?
                    WHERE run_id = ?""",
                    (time.time(), str(e), run_id),
                )
                conn.commit()
            finally:
                conn.close()

            return {
                "run_id": run_id,
                "policy_id": policy["policy_id"],
                "status": "failed",
                "error": str(e),
                "items_deleted": 0,
                "bytes_freed": 0,
            }

    def _execute_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual retention logic based on policy type."""
        retention_type = policy["retention_type"]
        params = policy.get("params", {})
        if isinstance(params, str):
            params = json.loads(params)
        scope = policy.get("scope", "all")

        if retention_type == RetentionType.AGE:
            return self._cleanup_by_age(params, scope)
        elif retention_type == RetentionType.COUNT:
            return self._cleanup_by_count(params, scope)
        elif retention_type == RetentionType.SIZE:
            return self._cleanup_by_size(params, scope)
        else:
            raise ValueError(f"Unknown retention type: {retention_type}")

    def _cleanup_by_age(self, params: Dict[str, Any], scope: str) -> Dict[str, Any]:
        """Delete records older than max_age_days."""
        max_age_days = params.get("max_age_days", 30)
        cutoff = time.time() - (max_age_days * 86400)
        total_deleted = 0

        conn = sqlite3.connect(self.db_path)
        try:
            if scope in ("all", "traces"):
                # Delete spans belonging to old traces first
                cur = conn.execute(
                    "DELETE FROM spans WHERE trace_id IN (SELECT trace_id FROM traces WHERE start_time < ?)",
                    (cutoff,),
                )
                total_deleted += cur.rowcount

                cur = conn.execute(
                    "DELETE FROM traces WHERE start_time < ?",
                    (cutoff,),
                )
                total_deleted += cur.rowcount

            if scope in ("all", "evaluations"):
                cur = conn.execute(
                    "DELETE FROM evaluation_results WHERE run_id IN (SELECT run_id FROM evaluation_runs WHERE created_at < ?)",
                    (cutoff,),
                )
                total_deleted += cur.rowcount

                cur = conn.execute(
                    "DELETE FROM evaluation_runs WHERE created_at < ?",
                    (cutoff,),
                )
                total_deleted += cur.rowcount

            if scope in ("all", "alerts"):
                cur = conn.execute(
                    "DELETE FROM alert_events WHERE timestamp < ?",
                    (cutoff,),
                )
                total_deleted += cur.rowcount

            if scope in ("all", "dashboards"):
                cur = conn.execute(
                    "DELETE FROM dashboard_widgets WHERE created_at < ?",
                    (cutoff,),
                )
                total_deleted += cur.rowcount

            conn.commit()

            # VACUUM to reclaim space
            bytes_freed = self._vacuum_and_measure(conn)

            return {"items_deleted": total_deleted, "bytes_freed": bytes_freed}
        finally:
            conn.close()

    def _cleanup_by_count(self, params: Dict[str, Any], scope: str) -> Dict[str, Any]:
        """Keep at most max_count traces, deleting the oldest."""
        max_count = params.get("max_count", 10000)
        total_deleted = 0

        conn = sqlite3.connect(self.db_path)
        try:
            if scope in ("all", "traces"):
                # Count current traces
                count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
                if count > max_count:
                    excess = count - max_count
                    # Delete oldest traces
                    old_trace_ids = conn.execute(
                        "SELECT trace_id FROM traces ORDER BY start_time ASC LIMIT ?",
                        (excess,),
                    ).fetchall()

                    trace_ids = [row[0] for row in old_trace_ids]
                    if trace_ids:
                        placeholders = ",".join("?" * len(trace_ids))
                        cur = conn.execute(
                            f"DELETE FROM spans WHERE trace_id IN ({placeholders})",
                            trace_ids,
                        )
                        total_deleted += cur.rowcount

                        cur = conn.execute(
                            f"DELETE FROM traces WHERE trace_id IN ({placeholders})",
                            trace_ids,
                        )
                        total_deleted += cur.rowcount

            conn.commit()

            bytes_freed = self._vacuum_and_measure(conn)

            return {"items_deleted": total_deleted, "bytes_freed": bytes_freed}
        finally:
            conn.close()

    def _cleanup_by_size(self, params: Dict[str, Any], scope: str) -> Dict[str, Any]:
        """Keep database under max_size_mb by deleting oldest data."""
        max_size_mb = params.get("max_size_mb", 100)
        total_deleted = 0

        conn = sqlite3.connect(self.db_path)
        try:
            # Get current DB size
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            current_size_mb = (page_count * page_size) / (1024 * 1024)

            if current_size_mb <= max_size_mb:
                return {"items_deleted": 0, "bytes_freed": 0, "current_size_mb": round(current_size_mb, 2)}

            # Delete oldest traces until under limit
            while current_size_mb > max_size_mb * 0.9:  # Target 90% of max
                # Delete in batches of 100
                old_trace_ids = conn.execute(
                    "SELECT trace_id FROM traces ORDER BY start_time ASC LIMIT 100"
                ).fetchall()

                if not old_trace_ids:
                    break

                trace_ids = [row[0] for row in old_trace_ids]
                placeholders = ",".join("?" * len(trace_ids))

                cur = conn.execute(
                    f"DELETE FROM spans WHERE trace_id IN ({placeholders})",
                    trace_ids,
                )
                total_deleted += cur.rowcount

                cur = conn.execute(
                    f"DELETE FROM traces WHERE trace_id IN ({placeholders})",
                    trace_ids,
                )
                total_deleted += cur.rowcount

                conn.commit()

                # Re-check size
                page_count = conn.execute("PRAGMA page_count").fetchone()[0]
                current_size_mb = (page_count * page_size) / (1024 * 1024)

            bytes_freed = self._vacuum_and_measure(conn)

            return {
                "items_deleted": total_deleted,
                "bytes_freed": bytes_freed,
                "current_size_mb": round(current_size_mb, 2),
            }
        finally:
            conn.close()

    def _vacuum_and_measure(self, conn: sqlite3.Connection) -> int:
        """Run VACUUM and return approximate bytes freed."""
        try:
            before_pages = conn.execute("PRAGMA page_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            before_size = before_pages * page_size

            conn.execute("VACUUM")

            after_pages = conn.execute("PRAGMA page_count").fetchone()[0]
            after_size = after_pages * page_size

            return max(0, before_size - after_size)
        except Exception as e:
            logger.warning(f"VACUUM failed (may need exclusive access): {e}")
            return 0

    def run_all_enabled(self) -> List[Dict[str, Any]]:
        """Run all enabled retention policies."""
        policies = list_retention_policies(enabled_only=True)
        results = []
        for policy in policies:
            result = self.run_policy(policy)
            results.append(result)
            logger.info(
                "Retention policy '%s' completed: %d items deleted",
                policy["name"], result.get("items_deleted", 0),
            )
        return results

    def get_db_stats(self) -> Dict[str, Any]:
        """Get database size and record counts."""
        conn = sqlite3.connect(self.db_path)
        try:
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            size_bytes = page_count * page_size
            size_mb = size_bytes / (1024 * 1024)

            trace_count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
            span_count = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]

            # Oldest trace
            oldest = conn.execute("SELECT MIN(start_time) FROM traces").fetchone()[0]

            # Newest trace
            newest = conn.execute("SELECT MAX(start_time) FROM traces").fetchone()[0]

            return {
                "size_bytes": size_bytes,
                "size_mb": round(size_mb, 2),
                "trace_count": trace_count,
                "span_count": span_count,
                "oldest_trace_time": oldest,
                "newest_trace_time": newest,
                "page_count": page_count,
                "page_size": page_size,
            }
        finally:
            conn.close()


# ── Policy CRUD ─────────────────────────────────────────


def create_retention_policy(
    name: str,
    retention_type: str,
    enabled: bool = True,
    params: Optional[Dict[str, Any]] = None,
    scope: str = "all",
) -> Dict[str, Any]:
    """Create a new retention policy."""
    _ensure_retention_tables()
    import secrets
    policy_id = secrets.token_hex(8)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT INTO retention_policies
            (policy_id, name, retention_type, enabled, params, scope, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (policy_id, name, retention_type, 1 if enabled else 0,
             json.dumps(params or {}), scope, time.time()),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "policy_id": policy_id,
        "name": name,
        "retention_type": retention_type,
        "enabled": enabled,
        "params": params or {},
        "scope": scope,
    }


def get_retention_policy(policy_id: str) -> Optional[Dict[str, Any]]:
    """Get a retention policy by ID."""
    _ensure_retention_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM retention_policies WHERE policy_id = ?", (policy_id,)
        ).fetchone()
        if not row:
            return None
        policy = dict(row)
        policy["enabled"] = bool(policy["enabled"])
        policy["params"] = json.loads(policy["params"]) if isinstance(policy["params"], str) else policy["params"]
        return policy
    finally:
        conn.close()


def list_retention_policies(enabled_only: bool = False) -> List[Dict[str, Any]]:
    """List all retention policies."""
    _ensure_retention_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if enabled_only:
            rows = conn.execute(
                "SELECT * FROM retention_policies WHERE enabled = 1 ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM retention_policies ORDER BY created_at DESC"
            ).fetchall()
        policies = []
        for row in rows:
            p = dict(row)
            p["enabled"] = bool(p["enabled"])
            p["params"] = json.loads(p["params"]) if isinstance(p["params"], str) else p["params"]
            policies.append(p)
        return policies
    finally:
        conn.close()


def update_retention_policy(policy_id: str, data: Dict[str, Any]) -> bool:
    """Update a retention policy."""
    conn = sqlite3.connect(DB_PATH)
    try:
        sets = []
        params: list = []
        for key in ("name", "retention_type", "enabled", "params", "scope"):
            if key in data:
                val = data[key]
                if key == "enabled":
                    val = 1 if val else 0
                elif key == "params":
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                params.append(val)
        if not sets:
            return True
        params.append(policy_id)
        conn.execute(
            f"UPDATE retention_policies SET {', '.join(sets)} WHERE policy_id = ?",
            params,
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update retention policy: {e}")
        return False
    finally:
        conn.close()


def delete_retention_policy(policy_id: str) -> bool:
    """Delete a retention policy."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM retention_policies WHERE policy_id = ?", (policy_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete retention policy: {e}")
        return False
    finally:
        conn.close()


def list_retention_runs(policy_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """List retention policy execution history."""
    _ensure_retention_tables()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if policy_id:
            rows = conn.execute(
                "SELECT * FROM retention_runs WHERE policy_id = ? ORDER BY started_at DESC LIMIT ?",
                (policy_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM retention_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Global engine instance ──────────────────────────────

_engine: Optional[RetentionEngine] = None


def get_retention_engine() -> RetentionEngine:
    """Get the global retention engine instance."""
    global _engine
    if _engine is None:
        _engine = RetentionEngine()
    return _engine


def set_retention_engine(engine: RetentionEngine):
    """Set the global retention engine instance."""
    global _engine
    _engine = engine
