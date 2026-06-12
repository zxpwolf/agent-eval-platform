"""Trace sampling and filtering service.

Supports multiple sampling strategies (rate-based, latency-based,
error-based, cost-based) and advanced trace filtering by span type,
model, status, cost range, latency range, and custom attributes.
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("TRACES_DB_PATH", "traces.db")


# ── Sampling Strategy ──────────────────────────────────


class SamplingStrategy:
    """Available sampling strategy types."""
    ALWAYS = "always"
    NEVER = "never"
    RATE = "rate"
    LATENCY = "latency"
    ERROR = "error"
    COST = "cost"
    ATTRIBUTE = "attribute"


class SamplingRule:
    """A single sampling rule with strategy and parameters."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        strategy: str,
        enabled: bool = True,
        priority: int = 0,
        params: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        created_at: Optional[float] = None,
    ):
        self.rule_id = rule_id
        self.name = name
        self.strategy = strategy
        self.enabled = enabled
        self.priority = priority
        self.params = params or {}
        self.filters = filters or {}
        self.created_at = created_at or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "strategy": self.strategy,
            "enabled": self.enabled,
            "priority": self.priority,
            "params": self.params,
            "filters": self.filters,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SamplingRule":
        return cls(
            rule_id=data["rule_id"],
            name=data["name"],
            strategy=data["strategy"],
            enabled=data.get("enabled", True),
            priority=data.get("priority", 0),
            params=data.get("params", {}),
            filters=data.get("filters", {}),
            created_at=data.get("created_at"),
        )


def _ensure_sampling_table():
    """Create sampling rules table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sampling_rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                strategy TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 0,
                params TEXT NOT NULL DEFAULT '{}',
                filters TEXT NOT NULL DEFAULT '{}',
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sampling_stats (
                rule_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                kept INTEGER NOT NULL DEFAULT 0,
                dropped INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (rule_id, timestamp)
            )
        """)
        conn.commit()
    finally:
        conn.close()


# ── Sampling Engine ─────────────────────────────────────


class SamplingEngine:
    """Evaluates traces against sampling rules to decide keep/drop."""

    def __init__(self):
        self._rules: List[SamplingRule] = []
        self._stats: Dict[str, Dict[str, int]] = {}
        self._load_rules()

    def _load_rules(self):
        """Load rules from database."""
        _ensure_sampling_table()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM sampling_rules ORDER BY priority DESC"
            ).fetchall()
            self._rules = [SamplingRule.from_dict(dict(r)) for r in rows]
            # Parse JSON fields
            for rule in self._rules:
                if isinstance(rule.params, str):
                    rule.params = json.loads(rule.params)
                if isinstance(rule.filters, str):
                    rule.filters = json.loads(rule.filters)
        finally:
            conn.close()

    def reload_rules(self):
        """Reload rules from database."""
        self._load_rules()

    def should_sample(self, trace_data: Dict[str, Any]) -> bool:
        """Decide whether a trace should be kept or dropped.

        Returns True if the trace should be kept, False to drop.
        Evaluation order: highest-priority enabled rule that matches wins.
        If no rules match, the default is to keep the trace.
        """
        matching_rule = None
        for rule in self._rules:
            if not rule.enabled:
                continue
            if self._matches_filters(trace_data, rule.filters):
                matching_rule = rule
                break

        if matching_rule is None:
            return True  # Default: keep if no rule matches

        decision = self._evaluate_strategy(trace_data, matching_rule)
        self._record_stat(matching_rule.rule_id, decision)
        return decision

    def _matches_filters(self, trace_data: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if a trace matches the rule's filter criteria."""
        if not filters:
            return True

        # Filter by name pattern
        name_pattern = filters.get("name_pattern")
        if name_pattern:
            trace_name = trace_data.get("name", "")
            if name_pattern.lower() not in trace_name.lower():
                return False

        # Filter by user_id
        user_ids = filters.get("user_ids")
        if user_ids:
            if trace_data.get("user_id") not in user_ids:
                return False

        # Filter by session_id
        session_ids = filters.get("session_ids")
        if session_ids:
            if trace_data.get("session_id") not in session_ids:
                return False

        # Filter by model (check spans)
        models = filters.get("models")
        if models:
            span_models = {s.get("model") for s in trace_data.get("spans", []) if s.get("model")}
            if not span_models.intersection(set(models)):
                return False

        # Filter by span types
        span_types = filters.get("span_types")
        if span_types:
            types = {s.get("span_type") for s in trace_data.get("spans", [])}
            if not types.intersection(set(span_types)):
                return False

        return True

    def _evaluate_strategy(self, trace_data: Dict[str, Any], rule: SamplingRule) -> bool:
        """Evaluate a single sampling strategy against trace data."""
        strategy = rule.strategy
        params = rule.params

        if strategy == SamplingStrategy.ALWAYS:
            return True

        if strategy == SamplingStrategy.NEVER:
            return False

        if strategy == SamplingStrategy.RATE:
            rate = params.get("rate", 1.0)
            # Deterministic sampling based on trace_id hash
            trace_id = trace_data.get("trace_id", "")
            hash_val = int(hashlib.md5(trace_id.encode()).hexdigest(), 16)
            return (hash_val % 10000) / 10000.0 < rate

        if strategy == SamplingStrategy.LATENCY:
            threshold_ms = params.get("threshold_ms", 5000)
            start = trace_data.get("start_time", 0)
            end = trace_data.get("end_time", 0)
            if start and end:
                duration_ms = (end - start) * 1000
                return duration_ms >= threshold_ms
            return True  # Keep if timing is incomplete

        if strategy == SamplingStrategy.ERROR:
            spans = trace_data.get("spans", [])
            has_error = any(s.get("status") == "error" for s in spans)
            keep_errors = params.get("keep_errors", True)
            return has_error if keep_errors else not has_error

        if strategy == SamplingStrategy.COST:
            threshold = params.get("threshold", 0.01)
            total_cost = trace_data.get("total_cost", 0)
            if total_cost == 0:
                # Calculate from spans
                for s in trace_data.get("spans", []):
                    total_cost += s.get("cost", 0)
            return total_cost >= threshold

        if strategy == SamplingStrategy.ATTRIBUTE:
            key = params.get("key", "")
            value = params.get("value")
            metadata = trace_data.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            return metadata.get(key) == value

        return True

    def _record_stat(self, rule_id: str, kept: bool):
        """Record sampling statistics."""
        if rule_id not in self._stats:
            self._stats[rule_id] = {"kept": 0, "dropped": 0}
        if kept:
            self._stats[rule_id]["kept"] += 1
        else:
            self._stats[rule_id]["dropped"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get sampling statistics."""
        total_kept = sum(s["kept"] for s in self._stats.values())
        total_dropped = sum(s["dropped"] for s in self._stats.values())
        return {
            "total_kept": total_kept,
            "total_dropped": total_dropped,
            "total_evaluated": total_kept + total_dropped,
            "sample_rate": total_kept / max(total_kept + total_dropped, 1),
            "rules": {
                rule_id: stats for rule_id, stats in self._stats.items()
            },
        }


# ── Advanced Trace Filtering ────────────────────────────


class TraceFilter:
    """Advanced filtering for trace queries."""

    @staticmethod
    def build_where_clause(
        name_pattern: Optional[str] = None,
        user_ids: Optional[List[str]] = None,
        session_ids: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        span_types: Optional[List[str]] = None,
        status: Optional[str] = None,
        min_cost: Optional[float] = None,
        max_cost: Optional[float] = None,
        min_latency_ms: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        start_time_from: Optional[float] = None,
        start_time_to: Optional[float] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """Build SQL WHERE clause and params for advanced trace filtering.

        Returns (where_clause, params) tuple.
        """
        conditions = []
        params: list = []

        if name_pattern:
            conditions.append("t.name LIKE ?")
            params.append(f"%{name_pattern}%")

        if user_ids:
            placeholders = ",".join("?" * len(user_ids))
            conditions.append(f"t.user_id IN ({placeholders})")
            params.extend(user_ids)

        if session_ids:
            placeholders = ",".join("?" * len(session_ids))
            conditions.append(f"t.session_id IN ({placeholders})")
            params.extend(session_ids)

        if start_time_from is not None:
            conditions.append("t.start_time >= ?")
            params.append(start_time_from)

        if start_time_to is not None:
            conditions.append("t.start_time <= ?")
            params.append(start_time_to)

        # Span-level filters require a subquery
        if models or span_types or status:
            sub_conditions = []
            if models:
                placeholders = ",".join("?" * len(models))
                sub_conditions.append(f"s.model IN ({placeholders})")
                params.extend(models)
            if span_types:
                placeholders = ",".join("?" * len(span_types))
                sub_conditions.append(f"s.span_type IN ({placeholders})")
                params.extend(span_types)
            if status:
                sub_conditions.append("s.status = ?")
                params.append(status)

            sub_where = " AND ".join(sub_conditions)
            conditions.append(
                f"t.trace_id IN (SELECT DISTINCT trace_id FROM spans s WHERE {sub_where})"
            )

        # Cost-based filtering (from spans)
        if min_cost is not None or max_cost is not None:
            cost_conditions = []
            if min_cost is not None:
                cost_conditions.append("SUM(s.cost) >= ?")
                params.append(min_cost)
            if max_cost is not None:
                cost_conditions.append("SUM(s.cost) <= ?")
                params.append(max_cost)
            cost_where = " AND ".join(cost_conditions)
            conditions.append(
                f"t.trace_id IN (SELECT trace_id FROM spans s GROUP BY trace_id HAVING {cost_where})"
            )

        # Latency-based filtering
        if min_latency_ms is not None or max_latency_ms is not None:
            if min_latency_ms is not None:
                conditions.append("((t.end_time - t.start_time) * 1000) >= ?")
                params.append(min_latency_ms)
            if max_latency_ms is not None:
                conditions.append("((t.end_time - t.start_time) * 1000) <= ?")
                params.append(max_latency_ms)

        # Attribute-based filtering (metadata JSON)
        if attributes:
            for key, value in attributes.items():
                conditions.append("t.metadata LIKE ?")
                params.append(f'%"{key}"%{json.dumps(value)}%')

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params

    @staticmethod
    def filter_traces(
        db_path: str,
        name_pattern: Optional[str] = None,
        user_ids: Optional[List[str]] = None,
        session_ids: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        span_types: Optional[List[str]] = None,
        status: Optional[str] = None,
        min_cost: Optional[float] = None,
        max_cost: Optional[float] = None,
        min_latency_ms: Optional[float] = None,
        max_latency_ms: Optional[float] = None,
        start_time_from: Optional[float] = None,
        start_time_to: Optional[float] = None,
        attributes: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "start_time",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """Execute an advanced filtered trace query."""
        where_clause, params = TraceFilter.build_where_clause(
            name_pattern=name_pattern,
            user_ids=user_ids,
            session_ids=session_ids,
            models=models,
            span_types=span_types,
            status=status,
            min_cost=min_cost,
            max_cost=max_cost,
            min_latency_ms=min_latency_ms,
            max_latency_ms=max_latency_ms,
            start_time_from=start_time_from,
            start_time_to=start_time_to,
            attributes=attributes,
        )

        valid_sort = {"start_time", "end_time", "name", "trace_id"}
        if sort_by not in valid_sort:
            sort_by = "start_time"
        if sort_order.lower() not in ("asc", "desc"):
            sort_order = "desc"

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Count total matching
            count_sql = f"SELECT COUNT(*) FROM traces t WHERE {where_clause}"
            total = conn.execute(count_sql, params).fetchone()[0]

            # Fetch traces
            query_sql = f"""
                SELECT t.*,
                       (SELECT COUNT(*) FROM spans s WHERE s.trace_id = t.trace_id) as span_count,
                       (SELECT COALESCE(SUM(s.total_tokens), 0) FROM spans s WHERE s.trace_id = t.trace_id) as total_tokens,
                       (SELECT COALESCE(SUM(s.cost), 0) FROM spans s WHERE s.trace_id = t.trace_id) as total_cost
                FROM traces t
                WHERE {where_clause}
                ORDER BY t.{sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(query_sql, params + [limit, offset]).fetchall()

            traces = []
            for row in rows:
                t = dict(row)
                duration_ms = 0.0
                if t.get("end_time") and t.get("start_time"):
                    duration_ms = (t["end_time"] - t["start_time"]) * 1000
                t["duration_ms"] = duration_ms
                traces.append(t)

            return {
                "traces": traces,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        finally:
            conn.close()


# ── CRUD for sampling rules ────────────────────────────


def create_sampling_rule(
    name: str,
    strategy: str,
    enabled: bool = True,
    priority: int = 0,
    params: Optional[Dict[str, Any]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new sampling rule."""
    _ensure_sampling_table()
    import secrets
    rule_id = secrets.token_hex(8)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """INSERT INTO sampling_rules
            (rule_id, name, strategy, enabled, priority, params, filters, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (rule_id, name, strategy, 1 if enabled else 0, priority,
             json.dumps(params or {}), json.dumps(filters or {}), time.time()),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "rule_id": rule_id,
        "name": name,
        "strategy": strategy,
        "enabled": enabled,
        "priority": priority,
        "params": params or {},
        "filters": filters or {},
    }


def get_sampling_rule(rule_id: str) -> Optional[Dict[str, Any]]:
    """Get a sampling rule by ID."""
    _ensure_sampling_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM sampling_rules WHERE rule_id = ?", (rule_id,)
        ).fetchone()
        if not row:
            return None
        rule = dict(row)
        rule["enabled"] = bool(rule["enabled"])
        rule["params"] = json.loads(rule["params"]) if isinstance(rule["params"], str) else rule["params"]
        rule["filters"] = json.loads(rule["filters"]) if isinstance(rule["filters"], str) else rule["filters"]
        return rule
    finally:
        conn.close()


def list_sampling_rules(enabled_only: bool = False) -> List[Dict[str, Any]]:
    """List all sampling rules."""
    _ensure_sampling_table()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        if enabled_only:
            rows = conn.execute(
                "SELECT * FROM sampling_rules WHERE enabled = 1 ORDER BY priority DESC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sampling_rules ORDER BY priority DESC"
            ).fetchall()
        rules = []
        for row in rows:
            r = dict(row)
            r["enabled"] = bool(r["enabled"])
            r["params"] = json.loads(r["params"]) if isinstance(r["params"], str) else r["params"]
            r["filters"] = json.loads(r["filters"]) if isinstance(r["filters"], str) else r["filters"]
            rules.append(r)
        return rules
    finally:
        conn.close()


def update_sampling_rule(rule_id: str, data: Dict[str, Any]) -> bool:
    """Update a sampling rule."""
    conn = sqlite3.connect(DB_PATH)
    try:
        sets = []
        params: list = []
        for key in ("name", "strategy", "enabled", "priority", "params", "filters"):
            if key in data:
                val = data[key]
                if key == "enabled":
                    val = 1 if val else 0
                elif key in ("params", "filters"):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                params.append(val)
        if not sets:
            return True
        params.append(rule_id)
        conn.execute(
            f"UPDATE sampling_rules SET {', '.join(sets)} WHERE rule_id = ?",
            params,
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update sampling rule: {e}")
        return False
    finally:
        conn.close()


def delete_sampling_rule(rule_id: str) -> bool:
    """Delete a sampling rule."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM sampling_rules WHERE rule_id = ?", (rule_id,))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to delete sampling rule: {e}")
        return False
    finally:
        conn.close()


# ── Global engine instance ──────────────────────────────

_engine: Optional[SamplingEngine] = None


def get_sampling_engine() -> SamplingEngine:
    """Get the global sampling engine instance."""
    global _engine
    if _engine is None:
        _engine = SamplingEngine()
    return _engine


def set_sampling_engine(engine: SamplingEngine):
    """Set the global sampling engine instance."""
    global _engine
    _engine = engine
