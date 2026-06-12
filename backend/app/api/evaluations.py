"""API endpoints for the evaluation framework.

Provides CRUD for datasets, evaluators, evaluation runs, and results.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from ..db.base import EvaluationRepository
from ..errors import NotFoundError, ValidationError
from ..services.evaluation_runner import run_evaluation, get_running_eval_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])

# Global repository instance (set during app startup)
repo: Optional[EvaluationRepository] = None


def set_repository(repository: EvaluationRepository):
    """Set the evaluation repository instance."""
    global repo
    repo = repository


def _get_repo() -> EvaluationRepository:
    if repo is None:
        raise HTTPException(status_code=500, detail="Evaluation repository not initialized")
    return repo


# ── Datasets ────────────────────────────────────────────────


@router.post("/datasets", status_code=201)
async def create_dataset(body: Dict[str, Any]):
    """Create a new evaluation dataset."""
    r = _get_repo()
    name = body.get("name")
    if not name:
        raise ValidationError("'name' is required")

    data = {
        "dataset_id": str(uuid.uuid4()),
        "name": name,
        "description": body.get("description", ""),
        "metadata": body.get("metadata", {}),
    }
    result = r.create_dataset(data)
    return result


@router.get("/datasets")
async def list_datasets(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List all evaluation datasets."""
    r = _get_repo()
    datasets = r.list_datasets(limit=limit, offset=offset)
    return {"datasets": datasets, "total": len(datasets)}


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    """Get a dataset with its items."""
    r = _get_repo()
    dataset = r.get_dataset(dataset_id)
    if not dataset:
        raise NotFoundError("Dataset", dataset_id)
    return dataset


@router.put("/datasets/{dataset_id}")
async def update_dataset(dataset_id: str, body: Dict[str, Any]):
    """Update dataset metadata."""
    r = _get_repo()
    existing = r.get_dataset(dataset_id)
    if not existing:
        raise NotFoundError("Dataset", dataset_id)

    success = r.update_dataset(dataset_id, body)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update dataset")
    return r.get_dataset(dataset_id)


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """Delete a dataset and its items."""
    r = _get_repo()
    existing = r.get_dataset(dataset_id)
    if not existing:
        raise NotFoundError("Dataset", dataset_id)

    success = r.delete_dataset(dataset_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete dataset")
    return {"message": "Dataset deleted"}


# ── Dataset Items ───────────────────────────────────────────


@router.post("/datasets/{dataset_id}/items", status_code=201)
async def add_dataset_items(dataset_id: str, body: Dict[str, Any]):
    """Add one or more items to a dataset.

    Body: {"items": [{"input_data": ..., "expected_output": ..., "metadata": ...}, ...]}
    """
    r = _get_repo()
    dataset = r.get_dataset(dataset_id)
    if not dataset:
        raise NotFoundError("Dataset", dataset_id)

    raw_items = body.get("items", [])
    if not raw_items:
        raise ValidationError("'items' array is required and must not be empty")

    items = []
    for raw in raw_items:
        items.append({
            "item_id": str(uuid.uuid4()),
            "input_data": raw.get("input_data"),
            "expected_output": raw.get("expected_output"),
            "metadata": raw.get("metadata", {}),
        })

    r.add_dataset_items(dataset_id, items)
    return {"added": len(items), "items": items}


@router.delete("/datasets/{dataset_id}/items/{item_id}")
async def delete_dataset_item(dataset_id: str, item_id: str):
    """Remove an item from a dataset."""
    r = _get_repo()
    success = r.delete_dataset_item(dataset_id, item_id)
    if not success:
        raise NotFoundError("DatasetItem", item_id)
    return {"message": "Item deleted"}


# ── Evaluators ──────────────────────────────────────────────


@router.post("/evaluators", status_code=201)
async def create_evaluator(body: Dict[str, Any]):
    """Create a new evaluator.

    Body: {"name": "...", "evaluator_type": "heuristic|llm_judge|custom",
           "config": {...}, "description": "..."}
    """
    r = _get_repo()
    name = body.get("name")
    evaluator_type = body.get("evaluator_type")
    if not name:
        raise ValidationError("'name' is required")
    if not evaluator_type:
        raise ValidationError("'evaluator_type' is required")
    if evaluator_type not in ("heuristic", "llm_judge", "custom"):
        raise ValidationError("evaluator_type must be 'heuristic', 'llm_judge', or 'custom'")

    data = {
        "evaluator_id": str(uuid.uuid4()),
        "name": name,
        "evaluator_type": evaluator_type,
        "config": body.get("config", {}),
        "description": body.get("description", ""),
    }
    result = r.create_evaluator(data)
    return result


@router.get("/evaluators")
async def list_evaluators(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List all evaluators."""
    r = _get_repo()
    evaluators = r.list_evaluators(limit=limit, offset=offset)
    return {"evaluators": evaluators, "total": len(evaluators)}


@router.get("/evaluators/{evaluator_id}")
async def get_evaluator(evaluator_id: str):
    """Get an evaluator by ID."""
    r = _get_repo()
    ev = r.get_evaluator(evaluator_id)
    if not ev:
        raise NotFoundError("Evaluator", evaluator_id)
    return ev


@router.delete("/evaluators/{evaluator_id}")
async def delete_evaluator(evaluator_id: str):
    """Delete an evaluator."""
    r = _get_repo()
    ev = r.get_evaluator(evaluator_id)
    if not ev:
        raise NotFoundError("Evaluator", evaluator_id)

    success = r.delete_evaluator(evaluator_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete evaluator")
    return {"message": "Evaluator deleted"}


# ── Evaluation Runs ─────────────────────────────────────────


@router.post("/runs", status_code=201)
async def start_evaluation_run(
    body: Dict[str, Any],
    background_tasks: BackgroundTasks,
):
    """Start an evaluation run.

    Body: {"dataset_id": "...", "evaluator_ids": [...], "trace_id": "...(optional)"}

    The evaluation runs in the background. Poll GET /runs/{id} for status.
    """
    r = _get_repo()
    dataset_id = body.get("dataset_id")
    evaluator_ids = body.get("evaluator_ids", [])

    if not dataset_id:
        raise ValidationError("'dataset_id' is required")
    if not evaluator_ids:
        raise ValidationError("'evaluator_ids' must be a non-empty list")

    # Verify dataset exists
    dataset = r.get_dataset(dataset_id)
    if not dataset:
        raise NotFoundError("Dataset", dataset_id)

    # Verify evaluators exist
    for eid in evaluator_ids:
        ev = r.get_evaluator(eid)
        if not ev:
            raise NotFoundError("Evaluator", eid)

    run_id = str(uuid.uuid4())
    run_data = {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "evaluator_ids": evaluator_ids,
        "trace_id": body.get("trace_id"),
        "status": "pending",
        "config": body.get("config", {}),
        "started_at": time.time(),
    }
    r.create_evaluation_run(run_data)

    # Run evaluation in background
    background_tasks.add_task(
        run_evaluation,
        repo=r,
        run_id=run_id,
        dataset_id=dataset_id,
        evaluator_ids=evaluator_ids,
        trace_id=body.get("trace_id"),
    )

    return {"run_id": run_id, "status": "pending"}


@router.get("/runs")
async def list_evaluation_runs(
    dataset_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List evaluation runs with optional filtering."""
    r = _get_repo()
    runs = r.list_evaluation_runs(
        dataset_id=dataset_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"runs": runs, "total": len(runs)}


@router.get("/runs/{run_id}")
async def get_evaluation_run(run_id: str):
    """Get an evaluation run with all its results."""
    r = _get_repo()
    run = r.get_evaluation_run(run_id)
    if not run:
        raise NotFoundError("EvaluationRun", run_id)

    # Attach live progress if running
    live_status = get_running_eval_status(run_id)
    if live_status:
        run["live_status"] = live_status

    return run


@router.get("/runs/{run_id}/results")
async def get_evaluation_results(run_id: str):
    """Get results for a specific evaluation run."""
    r = _get_repo()
    run = r.get_evaluation_run(run_id)
    if not run:
        raise NotFoundError("EvaluationRun", run_id)

    results = r.get_evaluation_results(run_id)
    return {"run_id": run_id, "results": results}


@router.post("/runs/{run_id}/cancel")
async def cancel_evaluation_run(run_id: str):
    """Cancel a running evaluation."""
    r = _get_repo()
    run = r.get_evaluation_run(run_id)
    if not run:
        raise NotFoundError("EvaluationRun", run_id)

    if run.get("status") not in ("pending", "running"):
        raise ValidationError(f"Cannot cancel run in status '{run.get('status')}'")

    r.update_evaluation_run(run_id, {
        "status": "cancelled",
        "completed_at": time.time(),
    })
    return {"run_id": run_id, "status": "cancelled"}


# ── Comparison ──────────────────────────────────────────────


@router.post("/compare")
async def compare_runs(body: Dict[str, Any]):
    """Compare two evaluation runs side-by-side.

    Body: {"run_id_1": "...", "run_id_2": "..."}
    """
    r = _get_repo()
    run_id_1 = body.get("run_id_1")
    run_id_2 = body.get("run_id_2")

    if not run_id_1 or not run_id_2:
        raise ValidationError("Both 'run_id_1' and 'run_id_2' are required")

    run1 = r.get_evaluation_run(run_id_1)
    run2 = r.get_evaluation_run(run_id_2)

    if not run1:
        raise NotFoundError("EvaluationRun", run_id_1)
    if not run2:
        raise NotFoundError("EvaluationRun", run_id_2)

    # Build per-item comparison
    results1 = {r["item_id"]: r for r in run1.get("results", [])}
    results2 = {r["item_id"]: r for r in run2.get("results", [])}
    all_item_ids = sorted(set(results1.keys()) | set(results2.keys()))

    comparison = []
    for item_id in all_item_ids:
        r1 = results1.get(item_id, {})
        r2 = results2.get(item_id, {})
        comparison.append({
            "item_id": item_id,
            "run_1": {
                "score": r1.get("score"),
                "passed": r1.get("passed"),
                "reasoning": r1.get("reasoning", ""),
            },
            "run_2": {
                "score": r2.get("score"),
                "passed": r2.get("passed"),
                "reasoning": r2.get("reasoning", ""),
            },
            "delta": (r1.get("score", 0) or 0) - (r2.get("score", 0) or 0),
        })

    return {
        "run_id_1": run_id_1,
        "run_id_2": run_id_2,
        "summary_1": run1.get("results_summary", {}),
        "summary_2": run2.get("results_summary", {}),
        "comparison": comparison,
    }
