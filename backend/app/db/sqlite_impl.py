"""SQLite implementation of TraceRepository and EvaluationRepository.

Wraps the existing TraceDatabase logic and adds evaluation table CRUD.
All SQL is standard (TEXT/REAL/INTEGER) to ease future PostgreSQL migration.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import EvaluationRepository, TraceRepository

logger = logging.getLogger(__name__)


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ──────────────────────────────────────────────
# TraceRepository implementation
# ──────────────────────────────────────────────


class SQLiteTraceRepository(TraceRepository):
    """SQLite-backed trace and span storage."""

    def __init__(self, db_path: str = "traces.db"):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return _connect(self.db_path)

    # ── Store ─────────────────────────────────

    def store_trace(self, trace_data: Dict[str, Any]) -> bool:
        conn = self._conn()
        try:
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

            for span in trace_data.get("spans", []):
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
                        span["span_id"],
                        span["trace_id"],
                        span["name"],
                        span["span_type"],
                        span["start_time"],
                        span.get("end_time"),
                        span.get("parent_span_id"),
                        span.get("status", "ok"),
                        json.dumps(span.get("attributes", {})),
                        json.dumps(span.get("events", [])),
                        span.get("model"),
                        span.get("prompt_tokens"),
                        span.get("completion_tokens"),
                        span.get("total_tokens"),
                        span.get("cost"),
                        json.dumps(span.get("input_data")) if span.get("input_data") else None,
                        json.dumps(span.get("output_data")) if span.get("output_data") else None,
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

    # ── Read ──────────────────────────────────

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if not row:
                return None

            trace = dict(row)
            trace["metadata"] = json.loads(trace["metadata"]) if trace["metadata"] else {}

            span_rows = conn.execute(
                "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC",
                (trace_id,),
            ).fetchall()

            spans = []
            for sr in span_rows:
                span = dict(sr)
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
        conn = self._conn()
        try:
            query = "SELECT * FROM traces WHERE 1=1"
            params: list = []

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

    # ── Delete ────────────────────────────────

    def delete_trace(self, trace_id: str) -> bool:
        conn = self._conn()
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

    # ── Stats ─────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        conn = self._conn()
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
                FROM spans WHERE total_tokens IS NOT NULL
                """
            ).fetchone()

            model_stats = conn.execute(
                """
                SELECT model, COUNT(*) as call_count,
                       COALESCE(SUM(total_tokens), 0) as tokens
                FROM spans WHERE model IS NOT NULL
                GROUP BY model ORDER BY call_count DESC
                """
            ).fetchall()

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
            conn.close()

    # ── Sessions ──────────────────────────────

    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT session_id, COUNT(*) as trace_count,
                       MIN(start_time) as first_trace,
                       MAX(start_time) as last_trace
                FROM traces
                WHERE session_id IS NOT NULL
                GROUP BY session_id
                ORDER BY last_trace DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return []
        finally:
            conn.close()

    def get_session_traces(self, session_id: str) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM traces WHERE session_id = ? ORDER BY start_time ASC",
                (session_id,),
            ).fetchall()
            traces = []
            for row in rows:
                trace = dict(row)
                trace["metadata"] = json.loads(trace["metadata"]) if trace["metadata"] else {}
                span_rows = conn.execute(
                    "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time ASC",
                    (trace["trace_id"],),
                ).fetchall()
                spans = []
                for sr in span_rows:
                    span = dict(sr)
                    span["attributes"] = json.loads(span["attributes"]) if span["attributes"] else {}
                    span["events"] = json.loads(span["events"]) if span["events"] else []
                    span["input_data"] = json.loads(span["input_data"]) if span.get("input_data") else None
                    span["output_data"] = json.loads(span["output_data"]) if span.get("output_data") else None
                    spans.append(span)
                trace["spans"] = spans
                traces.append(trace)
            return traces
        except Exception as e:
            logger.error(f"Failed to get session traces: {e}")
            return []
        finally:
            conn.close()


# ──────────────────────────────────────────────
# EvaluationRepository implementation
# ──────────────────────────────────────────────


class SQLiteEvaluationRepository(EvaluationRepository):
    """SQLite-backed evaluation storage."""

    def __init__(self, db_path: str = "traces.db"):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return _connect(self.db_path)

    # ── Datasets ──────────────────────────────

    def create_dataset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO datasets (dataset_id, name, description, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (data["dataset_id"], data["name"], data.get("description", ""),
                 json.dumps(data.get("metadata", {}))),
            )
            conn.commit()
            return data
        except Exception as e:
            logger.error(f"Failed to create dataset: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if not row:
                return None
            dataset = dict(row)
            dataset["metadata"] = json.loads(dataset["metadata"]) if dataset["metadata"] else {}

            item_rows = conn.execute(
                "SELECT * FROM dataset_items WHERE dataset_id = ? ORDER BY created_at ASC",
                (dataset_id,),
            ).fetchall()
            items = []
            for ir in item_rows:
                item = dict(ir)
                item["input_data"] = json.loads(item["input_data"]) if item.get("input_data") else None
                item["expected_output"] = json.loads(item["expected_output"]) if item.get("expected_output") else None
                item["metadata"] = json.loads(item["metadata"]) if item.get("metadata") else {}
                items.append(item)
            dataset["items"] = items
            return dataset
        except Exception as e:
            logger.error(f"Failed to get dataset: {e}")
            return None
        finally:
            conn.close()

    def list_datasets(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT d.*, COUNT(di.item_id) as item_count
                FROM datasets d
                LEFT JOIN dataset_items di ON d.dataset_id = di.dataset_id
                GROUP BY d.dataset_id
                ORDER BY d.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            datasets = []
            for row in rows:
                ds = dict(row)
                ds["metadata"] = json.loads(ds["metadata"]) if ds["metadata"] else {}
                datasets.append(ds)
            return datasets
        except Exception as e:
            logger.error(f"Failed to list datasets: {e}")
            return []
        finally:
            conn.close()

    def update_dataset(self, dataset_id: str, data: Dict[str, Any]) -> bool:
        conn = self._conn()
        try:
            sets = []
            params: list = []
            if "name" in data:
                sets.append("name = ?")
                params.append(data["name"])
            if "description" in data:
                sets.append("description = ?")
                params.append(data["description"])
            if "metadata" in data:
                sets.append("metadata = ?")
                params.append(json.dumps(data["metadata"]))
            if not sets:
                return True
            sets.append("updated_at = CURRENT_TIMESTAMP")
            params.append(dataset_id)
            conn.execute(
                f"UPDATE datasets SET {', '.join(sets)} WHERE dataset_id = ?",
                params,
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update dataset: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def delete_dataset(self, dataset_id: str) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete dataset: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ── Dataset Items ─────────────────────────

    def add_dataset_items(self, dataset_id: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            for item in items:
                conn.execute(
                    """
                    INSERT INTO dataset_items (item_id, dataset_id, input_data, expected_output, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        item["item_id"],
                        dataset_id,
                        json.dumps(item.get("input_data")),
                        json.dumps(item.get("expected_output")),
                        json.dumps(item.get("metadata", {})),
                    ),
                )
            conn.commit()
            return items
        except Exception as e:
            logger.error(f"Failed to add dataset items: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def delete_dataset_item(self, dataset_id: str, item_id: str) -> bool:
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM dataset_items WHERE dataset_id = ? AND item_id = ?",
                (dataset_id, item_id),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete dataset item: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ── Evaluators ────────────────────────────

    def create_evaluator(self, data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO evaluators (evaluator_id, name, evaluator_type, config, description, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    data["evaluator_id"],
                    data["name"],
                    data["evaluator_type"],
                    json.dumps(data.get("config", {})),
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
            conn.close()

    def get_evaluator(self, evaluator_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM evaluators WHERE evaluator_id = ?", (evaluator_id,)
            ).fetchone()
            if not row:
                return None
            ev = dict(row)
            ev["config"] = json.loads(ev["config"]) if ev["config"] else {}
            return ev
        except Exception as e:
            logger.error(f"Failed to get evaluator: {e}")
            return None
        finally:
            conn.close()

    def list_evaluators(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM evaluators ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            evaluators = []
            for row in rows:
                ev = dict(row)
                ev["config"] = json.loads(ev["config"]) if ev["config"] else {}
                evaluators.append(ev)
            return evaluators
        except Exception as e:
            logger.error(f"Failed to list evaluators: {e}")
            return []
        finally:
            conn.close()

    def delete_evaluator(self, evaluator_id: str) -> bool:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM evaluators WHERE evaluator_id = ?", (evaluator_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete evaluator: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ── Evaluation Runs ───────────────────────

    def create_evaluation_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT INTO evaluation_runs
                (run_id, dataset_id, evaluator_ids, trace_id, status, config, started_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    data["run_id"],
                    data["dataset_id"],
                    json.dumps(data.get("evaluator_ids", [])),
                    data.get("trace_id"),
                    data.get("status", "pending"),
                    json.dumps(data.get("config", {})),
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
            conn.close()

    def get_evaluation_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM evaluation_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if not row:
                return None
            run = dict(row)
            run["evaluator_ids"] = json.loads(run["evaluator_ids"]) if run["evaluator_ids"] else []
            run["config"] = json.loads(run["config"]) if run["config"] else {}
            run["results_summary"] = json.loads(run["results_summary"]) if run.get("results_summary") else {}

            result_rows = conn.execute(
                "SELECT * FROM evaluation_results WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
            results = []
            for rr in result_rows:
                r = dict(rr)
                r["actual_output"] = json.loads(r["actual_output"]) if r.get("actual_output") else None
                r["metadata"] = json.loads(r["metadata"]) if r.get("metadata") else {}
                results.append(r)
            run["results"] = results
            return run
        except Exception as e:
            logger.error(f"Failed to get evaluation run: {e}")
            return None
        finally:
            conn.close()

    def list_evaluation_runs(
        self,
        dataset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            query = "SELECT * FROM evaluation_runs WHERE 1=1"
            params: list = []
            if dataset_id:
                query += " AND dataset_id = ?"
                params.append(dataset_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(query, params).fetchall()
            runs = []
            for row in rows:
                run = dict(row)
                run["evaluator_ids"] = json.loads(run["evaluator_ids"]) if run["evaluator_ids"] else []
                run["config"] = json.loads(run["config"]) if run["config"] else {}
                run["results_summary"] = json.loads(run["results_summary"]) if run.get("results_summary") else {}
                runs.append(run)
            return runs
        except Exception as e:
            logger.error(f"Failed to list evaluation runs: {e}")
            return []
        finally:
            conn.close()

    def update_evaluation_run(self, run_id: str, data: Dict[str, Any]) -> bool:
        conn = self._conn()
        try:
            sets = []
            params: list = []
            for key in ("status", "completed_at", "results_summary"):
                if key in data:
                    val = data[key]
                    if key == "results_summary":
                        val = json.dumps(val)
                    sets.append(f"{key} = ?")
                    params.append(val)
            if not sets:
                return True
            params.append(run_id)
            conn.execute(
                f"UPDATE evaluation_runs SET {', '.join(sets)} WHERE run_id = ?",
                params,
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to update evaluation run: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # ── Evaluation Results ────────────────────

    def store_evaluation_results(self, run_id: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            for r in results:
                conn.execute(
                    """
                    INSERT INTO evaluation_results
                    (result_id, run_id, item_id, evaluator_id, score, passed, reasoning,
                     actual_output, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        r["result_id"],
                        run_id,
                        r["item_id"],
                        r["evaluator_id"],
                        r.get("score"),
                        r.get("passed"),
                        r.get("reasoning", ""),
                        json.dumps(r.get("actual_output")),
                        json.dumps(r.get("metadata", {})),
                    ),
                )
            conn.commit()
            return results
        except Exception as e:
            logger.error(f"Failed to store evaluation results: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_evaluation_results(self, run_id: str) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM evaluation_results WHERE run_id = ? ORDER BY created_at ASC",
                (run_id,),
            ).fetchall()
            results = []
            for rr in rows:
                r = dict(rr)
                r["actual_output"] = json.loads(r["actual_output"]) if r.get("actual_output") else None
                r["metadata"] = json.loads(r["metadata"]) if r.get("metadata") else {}
                results.append(r)
            return results
        except Exception as e:
            logger.error(f"Failed to get evaluation results: {e}")
            return []
        finally:
            conn.close()
