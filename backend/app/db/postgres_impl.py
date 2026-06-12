"""PostgreSQL implementation of TraceRepository and EvaluationRepository.

Uses psycopg2 with connection pooling and JSONB columns.
Tables are auto-created on first connection if they don't exist.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

import psycopg2
import psycopg2.extras
import psycopg2.pool

from .base import EvaluationRepository, TraceRepository

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------


def _parse_database_url(database_url: str) -> Dict[str, Any]:
    """Parse a postgresql:// URL into psycopg2 connection kwargs."""
    parsed = urlparse(database_url)
    kwargs: Dict[str, Any] = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "dbname": parsed.path.lstrip("/") or "agent_eval",
        "user": parsed.username or "postgres",
        "password": parsed.password or "",
    }
    # Pass through any extra query-string params (sslmode, connect_timeout, etc.)
    for key, values in parse_qs(parsed.query).items():
        kwargs[key] = values[0]
    return kwargs


def _create_pool(database_url: str, min_conn: int = 1, max_conn: int = 10) -> psycopg2.pool.SimpleConnectionPool:
    conn_kwargs = _parse_database_url(database_url)
    pool = psycopg2.pool.SimpleConnectionPool(min_conn, max_conn, **conn_kwargs)
    return pool


# ---------------------------------------------------------------------------
# Schema DDL  (idempotent – safe to run on every startup)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id     TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    start_time   DOUBLE PRECISION NOT NULL,
    end_time     DOUBLE PRECISION,
    user_id      TEXT,
    session_id   TEXT,
    metadata     JSONB DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS spans (
    span_id           TEXT PRIMARY KEY,
    trace_id          TEXT NOT NULL REFERENCES traces(trace_id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    span_type         TEXT NOT NULL,
    start_time        DOUBLE PRECISION NOT NULL,
    end_time          DOUBLE PRECISION,
    parent_span_id    TEXT,
    status            TEXT NOT NULL DEFAULT 'ok',
    attributes        JSONB DEFAULT '{}'::jsonb,
    events            JSONB DEFAULT '[]'::jsonb,
    model             TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cost              DOUBLE PRECISION,
    input_data        JSONB,
    output_data       JSONB,
    otel_operation    TEXT
);

CREATE INDEX IF NOT EXISTS idx_traces_user_id      ON traces(user_id);
CREATE INDEX IF NOT EXISTS idx_traces_session_id   ON traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_start_time   ON traces(start_time DESC);
CREATE INDEX IF NOT EXISTS idx_spans_trace_id      ON spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_parent_span   ON spans(parent_span_id);
CREATE INDEX IF NOT EXISTS idx_spans_span_type     ON spans(span_type);
CREATE INDEX IF NOT EXISTS idx_spans_model         ON spans(model);
CREATE INDEX IF NOT EXISTS idx_spans_otel_op       ON spans(otel_operation);

-- Evaluation tables

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id  TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    metadata    JSONB DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset_items (
    item_id         TEXT PRIMARY KEY,
    dataset_id      TEXT NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    input_data      JSONB,
    expected_output JSONB,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dataset_items_dataset_id ON dataset_items(dataset_id);

CREATE TABLE IF NOT EXISTS evaluators (
    evaluator_id   TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    evaluator_type TEXT NOT NULL,
    config         JSONB DEFAULT '{}'::jsonb,
    description    TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id          TEXT PRIMARY KEY,
    dataset_id      TEXT NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,
    evaluator_ids   JSONB DEFAULT '[]'::jsonb,
    trace_id        TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    config          JSONB DEFAULT '{}'::jsonb,
    started_at      DOUBLE PRECISION,
    completed_at    DOUBLE PRECISION,
    results_summary JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_dataset_id ON evaluation_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status     ON evaluation_runs(status);
CREATE INDEX IF NOT EXISTS idx_eval_runs_created_at ON evaluation_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS evaluation_results (
    result_id    TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES evaluation_runs(run_id) ON DELETE CASCADE,
    item_id      TEXT NOT NULL,
    evaluator_id TEXT NOT NULL,
    score        DOUBLE PRECISION,
    passed       BOOLEAN,
    reasoning    TEXT,
    actual_output JSONB,
    metadata     JSONB DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run_id       ON evaluation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_item_id      ON evaluation_results(item_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_evaluator_id ON evaluation_results(evaluator_id);
"""


def _ensure_schema(pool: psycopg2.pool.SimpleConnectionPool) -> None:
    """Create all tables/indexes if they don't already exist."""
    conn = pool.getconn()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL)
        conn.autocommit = False
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _json_dumps(obj: Any) -> Optional[str]:
    if obj is None:
        return None
    return json.dumps(obj)


def _parse_json(val: Any, default: Any = None) -> Any:
    """Parse a JSON value from PostgreSQL (JSONB comes back as Python objects
    when using RealDictCursor with the default json adapter, but we handle
    both string and already-parsed forms for safety)."""
    if val is None:
        return default if default is not None else {}
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else {}
    return val


# =========================================================================
# PostgresTraceRepository
# =========================================================================


class PostgresTraceRepository(TraceRepository):
    """PostgreSQL-backed trace and span storage."""

    def __init__(self, database_url: str, pool: Optional[psycopg2.pool.SimpleConnectionPool] = None):
        self.database_url = database_url
        self._pool = pool or _create_pool(database_url)
        _ensure_schema(self._pool)

    def _conn(self):
        return self._pool.getconn()

    def _putconn(self, conn):
        self._pool.putconn(conn)

    # -- Store ---------------------------------------------------------------

    def store_trace(self, trace_data: Dict[str, Any]) -> bool:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO traces (trace_id, name, start_time, end_time, user_id, session_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (trace_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        start_time = EXCLUDED.start_time,
                        end_time = EXCLUDED.end_time,
                        user_id = EXCLUDED.user_id,
                        session_id = EXCLUDED.session_id,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        trace_data["trace_id"],
                        trace_data.get("name", ""),
                        trace_data["start_time"],
                        trace_data.get("end_time"),
                        trace_data.get("user_id"),
                        trace_data.get("session_id"),
                        _json_dumps(trace_data.get("metadata", {})),
                    ),
                )

                for span in trace_data.get("spans", []):
                    cur.execute(
                        """
                        INSERT INTO spans
                        (span_id, trace_id, name, span_type, start_time, end_time,
                         parent_span_id, status, attributes, events, model,
                         prompt_tokens, completion_tokens, total_tokens, cost,
                         input_data, output_data)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (span_id) DO UPDATE SET
                            trace_id = EXCLUDED.trace_id,
                            name = EXCLUDED.name,
                            span_type = EXCLUDED.span_type,
                            start_time = EXCLUDED.start_time,
                            end_time = EXCLUDED.end_time,
                            parent_span_id = EXCLUDED.parent_span_id,
                            status = EXCLUDED.status,
                            attributes = EXCLUDED.attributes,
                            events = EXCLUDED.events,
                            model = EXCLUDED.model,
                            prompt_tokens = EXCLUDED.prompt_tokens,
                            completion_tokens = EXCLUDED.completion_tokens,
                            total_tokens = EXCLUDED.total_tokens,
                            cost = EXCLUDED.cost,
                            input_data = EXCLUDED.input_data,
                            output_data = EXCLUDED.output_data
                        """,
                        (
                            span["span_id"],
                            span["trace_id"],
                            span["name"],
                            span["span_type"],
                            span["start_time"],
                            span.get("end_time"),
                            span.get("parent_span_id"),
                            span.get("status", "ok"),
                            _json_dumps(span.get("attributes", {})),
                            _json_dumps(span.get("events", [])),
                            span.get("model"),
                            span.get("prompt_tokens"),
                            span.get("completion_tokens"),
                            span.get("total_tokens"),
                            span.get("cost"),
                            _json_dumps(span.get("input_data")),
                            _json_dumps(span.get("output_data")),
                        ),
                    )

            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to store trace: {e}")
            conn.rollback()
            return False
        finally:
            self._putconn(conn)

    # -- Read ----------------------------------------------------------------

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM traces WHERE trace_id = %s", (trace_id,))
                row = cur.fetchone()
                if not row:
                    return None

                trace = dict(row)
                trace["metadata"] = _parse_json(trace.get("metadata"), {})

                cur.execute(
                    "SELECT * FROM spans WHERE trace_id = %s ORDER BY start_time ASC",
                    (trace_id,),
                )
                span_rows = cur.fetchall()

                spans = []
                for sr in span_rows:
                    span = dict(sr)
                    span["attributes"] = _parse_json(span.get("attributes"), {})
                    span["events"] = _parse_json(span.get("events"), [])
                    span["input_data"] = _parse_json(span.get("input_data"), None)
                    span["output_data"] = _parse_json(span.get("output_data"), None)
                    spans.append(span)

                trace["spans"] = spans
                return trace
        except Exception as e:
            logger.error(f"Failed to get trace: {e}")
            return None
        finally:
            self._putconn(conn)

    def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = "SELECT * FROM traces WHERE 1=1"
                params: list = []

                if user_id:
                    query += " AND user_id = %s"
                    params.append(user_id)
                if session_id:
                    query += " AND session_id = %s"
                    params.append(session_id)
                if model:
                    query += " AND trace_id IN (SELECT DISTINCT trace_id FROM spans WHERE model = %s)"
                    params.append(model)

                query += " ORDER BY start_time DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, params)
                rows = cur.fetchall()

                traces = []
                for row in rows:
                    trace = dict(row)
                    trace["metadata"] = _parse_json(trace.get("metadata"), {})
                    cur.execute(
                        """
                        SELECT COUNT(*) as span_count,
                               COALESCE(SUM(total_tokens), 0) as total_tokens,
                               COALESCE(SUM(cost), 0) as total_cost
                        FROM spans WHERE trace_id = %s
                        """,
                        (trace["trace_id"],),
                    )
                    stats = cur.fetchone()
                    trace["span_count"] = stats["span_count"]
                    trace["total_tokens"] = stats["total_tokens"]
                    trace["total_cost"] = stats["total_cost"]
                    traces.append(trace)
                return traces
        except Exception as e:
            logger.error(f"Failed to list traces: {e}")
            return []
        finally:
            self._putconn(conn)

    # -- Delete --------------------------------------------------------------

    def delete_trace(self, trace_id: str) -> bool:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM traces WHERE trace_id = %s", (trace_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete trace: {e}")
            conn.rollback()
            return False
        finally:
            self._putconn(conn)

    # -- Stats ---------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM traces")
                trace_count = cur.fetchone()["cnt"]

                cur.execute("SELECT COUNT(*) as cnt FROM spans")
                span_count = cur.fetchone()["cnt"]

                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                        COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                        COALESCE(SUM(total_tokens), 0) as total_tokens,
                        COALESCE(SUM(cost), 0) as total_cost
                    FROM spans WHERE total_tokens IS NOT NULL
                    """
                )
                token_stats = cur.fetchone()

                cur.execute(
                    """
                    SELECT model, COUNT(*) as call_count,
                           COALESCE(SUM(total_tokens), 0) as tokens
                    FROM spans WHERE model IS NOT NULL
                    GROUP BY model ORDER BY call_count DESC
                    """
                )
                model_stats = cur.fetchall()

                return {
                    "trace_count": trace_count,
                    "span_count": span_count,
                    "total_prompt_tokens": token_stats["total_prompt_tokens"],
                    "total_completion_tokens": token_stats["total_completion_tokens"],
                    "total_tokens": token_stats["total_tokens"],
                    "total_cost": token_stats["total_cost"],
                    "models": [dict(r) for r in model_stats],
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
        finally:
            self._putconn(conn)

    # -- Sessions ------------------------------------------------------------

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT session_id, COUNT(*) as trace_count,
                           MIN(start_time) as first_trace,
                           MAX(start_time) as last_trace
                    FROM traces
                    WHERE session_id IS NOT NULL
                    GROUP BY session_id
                    ORDER BY last_trace DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
        finally:
            self._putconn(conn)

    def get_session_traces(self, session_id: str) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM traces WHERE session_id = %s ORDER BY start_time ASC",
                    (session_id,),
                )
                rows = cur.fetchall()

                traces = []
                for row in rows:
                    trace = dict(row)
                    trace["metadata"] = _parse_json(trace.get("metadata"), {})
                    cur.execute(
                        "SELECT * FROM spans WHERE trace_id = %s ORDER BY start_time ASC",
                        (trace["trace_id"],),
                    )
                    span_rows = cur.fetchall()
                    spans = []
                    for sr in span_rows:
                        span = dict(sr)
                        span["attributes"] = _parse_json(span.get("attributes"), {})
                        span["events"] = _parse_json(span.get("events"), [])
                        span["input_data"] = _parse_json(span.get("input_data"), None)
                        span["output_data"] = _parse_json(span.get("output_data"), None)
                        spans.append(span)
                    trace["spans"] = spans
                    traces.append(trace)
                return traces
        except Exception as e:
            logger.error(f"Failed to get session traces: {e}")
            return []
        finally:
            self._putconn(conn)

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close all connections in the pool."""
        self._pool.closeall()


# =========================================================================
# PostgresEvaluationRepository
# =========================================================================


class PostgresEvaluationRepository(EvaluationRepository):
    """PostgreSQL-backed evaluation storage."""

    def __init__(self, database_url: str, pool: Optional[psycopg2.pool.SimpleConnectionPool] = None):
        self.database_url = database_url
        self._pool = pool or _create_pool(database_url)
        _ensure_schema(self._pool)

    def _conn(self):
        return self._pool.getconn()

    def _putconn(self, conn):
        self._pool.putconn(conn)

    # -- Datasets ------------------------------------------------------------

    def create_dataset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO datasets (dataset_id, name, description, metadata, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                    """,
                    (data["dataset_id"], data["name"], data.get("description", ""),
                     _json_dumps(data.get("metadata", {}))),
                )
            conn.commit()
            return data
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            conn.rollback()
            raise
        finally:
            self._putconn(conn)

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM datasets WHERE dataset_id = %s", (dataset_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                dataset = dict(row)
                dataset["metadata"] = _parse_json(dataset.get("metadata"), {})

                cur.execute(
                    "SELECT * FROM dataset_items WHERE dataset_id = %s ORDER BY created_at ASC",
                    (dataset_id,),
                )
                item_rows = cur.fetchall()
                items = []
                for ir in item_rows:
                    item = dict(ir)
                    item["input_data"] = _parse_json(item.get("input_data"), None)
                    item["expected_output"] = _parse_json(item.get("expected_output"), None)
                    item["metadata"] = _parse_json(item.get("metadata"), {})
                    items.append(item)
                dataset["items"] = items
                return dataset
        except Exception as e:
            logger.error(f"Failed to get dataset: {e}")
            return None
        finally:
            self._putconn(conn)

    def list_datasets(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT d.*, COUNT(di.item_id) as item_count
                    FROM datasets d
                    LEFT JOIN dataset_items di ON d.dataset_id = di.dataset_id
                    GROUP BY d.dataset_id
                    ORDER BY d.created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                rows = cur.fetchall()
                datasets = []
                for row in rows:
                    ds = dict(row)
                    ds["metadata"] = _parse_json(ds.get("metadata"), {})
                    datasets.append(ds)
                return datasets
        except Exception as e:
            logger.error(f"Failed to list datasets: {e}")
            return []
        finally:
            self._putconn(conn)

    def update_dataset(self, dataset_id: str, data: Dict[str, Any]) -> bool:
        conn = self._conn()
        try:
            sets = []
            params: list = []
            if "name" in data:
                sets.append("name = %s")
                params.append(data["name"])
            if "description" in data:
                sets.append("description = %s")
                params.append(data["description"])
            if "metadata" in data:
                sets.append("metadata = %s")
                params.append(_json_dumps(data["metadata"]))
            if not sets:
                return True
            sets.append("updated_at = NOW()")
            params.append(dataset_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE datasets SET {', '.join(sets)} WHERE dataset_id = %s",
                    params,
                )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update dataset: {e}")
            conn.rollback()
            return False
        finally:
            self._putconn(conn)

    def delete_dataset(self, dataset_id: str) -> bool:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM datasets WHERE dataset_id = %s", (dataset_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete dataset: {e}")
            conn.rollback()
            return False
        finally:
            self._putconn(conn)

    # -- Dataset Items -------------------------------------------------------

    def add_dataset_items(self, dataset_id: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                for item in items:
                    cur.execute(
                        """
                        INSERT INTO dataset_items (item_id, dataset_id, input_data, expected_output, metadata, created_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            item["item_id"],
                            dataset_id,
                            _json_dumps(item.get("input_data")),
                            _json_dumps(item.get("expected_output")),
                            _json_dumps(item.get("metadata", {})),
                        ),
                    )
            conn.commit()
            return items
        except Exception as e:
            logger.error(f"Failed to add dataset items: {e}")
            conn.rollback()
            raise
        finally:
            self._putconn(conn)

    def delete_dataset_item(self, dataset_id: str, item_id: str) -> bool:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM dataset_items WHERE dataset_id = %s AND item_id = %s",
                    (dataset_id, item_id),
                )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete dataset item: {e}")
            conn.rollback()
            return False
        finally:
            self._putconn(conn)

    # -- Evaluators ----------------------------------------------------------

    def create_evaluator(self, data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evaluators (evaluator_id, name, evaluator_type, config, description, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        data["evaluator_id"],
                        data["name"],
                        data["evaluator_type"],
                        _json_dumps(data.get("config", {})),
                        data.get("description", ""),
                    ),
                )
            conn.commit()
            return data
        except Exception as e:
            logger.error(f"Failed to create evaluator: {e}")
            conn.rollback()
            raise
        finally:
            self._putconn(conn)

    def get_evaluator(self, evaluator_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM evaluators WHERE evaluator_id = %s", (evaluator_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                ev = dict(row)
                ev["config"] = _parse_json(ev.get("config"), {})
                return ev
        except Exception as e:
            logger.error(f"Failed to get evaluator: {e}")
            return None
        finally:
            self._putconn(conn)

    def list_evaluators(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM evaluators ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                rows = cur.fetchall()
                evaluators = []
                for row in rows:
                    ev = dict(row)
                    ev["config"] = _parse_json(ev.get("config"), {})
                    evaluators.append(ev)
                return evaluators
        except Exception as e:
            logger.error(f"Failed to list evaluators: {e}")
            return []
        finally:
            self._putconn(conn)

    def delete_evaluator(self, evaluator_id: str) -> bool:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM evaluators WHERE evaluator_id = %s", (evaluator_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete evaluator: {e}")
            conn.rollback()
            return False
        finally:
            self._putconn(conn)

    # -- Evaluation Runs -----------------------------------------------------

    def create_evaluation_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO evaluation_runs
                    (run_id, dataset_id, evaluator_ids, trace_id, status, config, started_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        data["run_id"],
                        data["dataset_id"],
                        _json_dumps(data.get("evaluator_ids", [])),
                        data.get("trace_id"),
                        data.get("status", "pending"),
                        _json_dumps(data.get("config", {})),
                        data.get("started_at"),
                    ),
                )
            conn.commit()
            return data
        except Exception as e:
            logger.error(f"Failed to create evaluation run: {e}")
            conn.rollback()
            raise
        finally:
            self._putconn(conn)

    def get_evaluation_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM evaluation_runs WHERE run_id = %s", (run_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                run = dict(row)
                run["evaluator_ids"] = _parse_json(run.get("evaluator_ids"), [])
                run["config"] = _parse_json(run.get("config"), {})
                run["results_summary"] = _parse_json(run.get("results_summary"), {})

                cur.execute(
                    "SELECT * FROM evaluation_results WHERE run_id = %s ORDER BY created_at ASC",
                    (run_id,),
                )
                result_rows = cur.fetchall()
                results = []
                for rr in result_rows:
                    r = dict(rr)
                    r["actual_output"] = _parse_json(r.get("actual_output"), None)
                    r["metadata"] = _parse_json(r.get("metadata"), {})
                    results.append(r)
                run["results"] = results
                return run
        except Exception as e:
            logger.error(f"Failed to get evaluation run: {e}")
            return None
        finally:
            self._putconn(conn)

    def list_evaluation_runs(
        self,
        dataset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                query = "SELECT * FROM evaluation_runs WHERE 1=1"
                params: list = []
                if dataset_id:
                    query += " AND dataset_id = %s"
                    params.append(dataset_id)
                if status:
                    query += " AND status = %s"
                    params.append(status)
                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, params)
                rows = cur.fetchall()
                runs = []
                for row in rows:
                    run = dict(row)
                    run["evaluator_ids"] = _parse_json(run.get("evaluator_ids"), [])
                    run["config"] = _parse_json(run.get("config"), {})
                    run["results_summary"] = _parse_json(run.get("results_summary"), {})
                    runs.append(run)
                return runs
        except Exception as e:
            logger.error(f"Failed to list evaluation runs: {e}")
            return []
        finally:
            self._putconn(conn)

    def update_evaluation_run(self, run_id: str, data: Dict[str, Any]) -> bool:
        conn = self._conn()
        try:
            sets = []
            params: list = []
            for key in ("status", "completed_at", "results_summary"):
                if key in data:
                    val = data[key]
                    if key == "results_summary":
                        val = _json_dumps(val)
                    sets.append(f"{key} = %s")
                    params.append(val)
            if not sets:
                return True
            params.append(run_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE evaluation_runs SET {', '.join(sets)} WHERE run_id = %s",
                    params,
                )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update evaluation run: {e}")
            conn.rollback()
            return False
        finally:
            self._putconn(conn)

    # -- Evaluation Results --------------------------------------------------

    def store_evaluation_results(self, run_id: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                for r in results:
                    cur.execute(
                        """
                        INSERT INTO evaluation_results
                        (result_id, run_id, item_id, evaluator_id, score, passed, reasoning,
                         actual_output, metadata, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            r["result_id"],
                            run_id,
                            r["item_id"],
                            r["evaluator_id"],
                            r.get("score"),
                            r.get("passed"),
                            r.get("reasoning", ""),
                            _json_dumps(r.get("actual_output")),
                            _json_dumps(r.get("metadata", {})),
                        ),
                    )
            conn.commit()
            return results
        except Exception as e:
            logger.error(f"Failed to store evaluation results: {e}")
            conn.rollback()
            raise
        finally:
            self._putconn(conn)

    def get_evaluation_results(self, run_id: str) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM evaluation_results WHERE run_id = %s ORDER BY created_at ASC",
                    (run_id,),
                )
                rows = cur.fetchall()
                results = []
                for rr in rows:
                    r = dict(rr)
                    r["actual_output"] = _parse_json(r.get("actual_output"), None)
                    r["metadata"] = _parse_json(r.get("metadata"), {})
                    results.append(r)
                return results
        except Exception as e:
            logger.error(f"Failed to get evaluation results: {e}")
            return []
        finally:
            self._putconn(conn)

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Close all connections in the pool."""
        self._pool.closeall()
