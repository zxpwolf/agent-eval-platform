"""Background evaluation runner service.

Manages asynchronous evaluation pipeline execution, integrating
the SDK's EvaluationPipeline with the database layer.
"""

import logging
import os
import sys
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

# Ensure agent_trace SDK is importable
_sdk_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "sdk", "python")
if _sdk_path not in sys.path:
    sys.path.insert(0, _sdk_path)

from agent_trace.eval.base import Evaluator
from agent_trace.eval.heuristic import (
    ContainsEvaluator,
    ExactMatchEvaluator,
    JsonValidEvaluator,
    KeywordEvaluator,
    LengthEvaluator,
    RegexMatchEvaluator,
)
from agent_trace.eval.llm_judge import LLMJudgeEvaluator
from agent_trace.eval.custom import CustomEvaluator
from agent_trace.eval.pipeline import EvaluationPipeline, PipelineProgress

from ..db.base import EvaluationRepository

logger = logging.getLogger(__name__)

# In-memory registry of running evaluations
_running_evals: Dict[str, Dict[str, Any]] = {}

# Built-in evaluator type -> class mapping
BUILTIN_EVALUATORS = {
    "regex_match": RegexMatchEvaluator,
    "contains": ContainsEvaluator,
    "exact_match": ExactMatchEvaluator,
    "json_valid": JsonValidEvaluator,
    "length": LengthEvaluator,
    "keyword": KeywordEvaluator,
}


def create_evaluator_instance(evaluator_data: Dict[str, Any]) -> Optional[Evaluator]:
    """Create an evaluator instance from stored evaluator data.

    Args:
        evaluator_data: Dict with evaluator_type, config, etc.

    Returns:
        An Evaluator instance, or None if type is unknown.
    """
    eval_type = evaluator_data.get("evaluator_type", "")
    config = evaluator_data.get("config", {})

    if eval_type == "heuristic":
        heuristic_type = config.get("type", "exact_match")
        cls = BUILTIN_EVALUATORS.get(heuristic_type)
        if cls:
            return cls(config)
        logger.warning(f"Unknown heuristic type: {heuristic_type}")
        return None

    elif eval_type == "llm_judge":
        return LLMJudgeEvaluator(config)

    elif eval_type == "custom":
        return CustomEvaluator(config)

    logger.warning(f"Unknown evaluator type: {eval_type}")
    return None


def run_evaluation(
    repo: EvaluationRepository,
    run_id: str,
    dataset_id: str,
    evaluator_ids: List[str],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute an evaluation run synchronously.

    This is typically called from a background task. It:
    1. Loads the dataset and evaluators
    2. Runs the pipeline
    3. Stores results in the database

    Args:
        repo: EvaluationRepository for data access.
        run_id: The evaluation run ID.
        dataset_id: The dataset to evaluate against.
        evaluator_ids: List of evaluator IDs to use.
        trace_id: Optional trace ID for offline mode.

    Returns:
        The run summary dict.
    """
    # Update status to running
    repo.update_evaluation_run(run_id, {"status": "running", "started_at": time.time()})
    _running_evals[run_id] = {"status": "running", "progress": 0.0}

    try:
        # Load dataset
        dataset = repo.get_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")

        items = dataset.get("items", [])
        if not items:
            raise ValueError(f"Dataset {dataset_id} has no items")

        # Load evaluators
        evaluators = []
        for eid in evaluator_ids:
            ev_data = repo.get_evaluator(eid)
            if not ev_data:
                logger.warning(f"Evaluator {eid} not found, skipping")
                continue
            instance = create_evaluator_instance(ev_data)
            if instance:
                instance.evaluator_id = eid  # type: ignore
                evaluators.append(instance)

        if not evaluators:
            raise ValueError("No valid evaluators found")

        # Progress callback
        def on_progress(progress: PipelineProgress):
            _running_evals[run_id] = {
                "status": progress.status,
                "progress": progress.percentage,
                "current_item": progress.current_item,
            }

        # Run pipeline
        pipeline = EvaluationPipeline(evaluators=evaluators, progress_callback=on_progress)
        result = pipeline.run(items)

        # Store results
        repo.store_evaluation_results(run_id, result.results)

        # Update run with summary
        repo.update_evaluation_run(run_id, {
            "status": "completed",
            "completed_at": time.time(),
            "results_summary": result.summary,
        })

        _running_evals[run_id] = {"status": "completed", "progress": 100.0}
        return result.summary

    except Exception as e:
        logger.error(f"Evaluation run {run_id} failed: {e}")
        repo.update_evaluation_run(run_id, {
            "status": "failed",
            "completed_at": time.time(),
            "results_summary": {"error": str(e)},
        })
        _running_evals[run_id] = {"status": "failed", "error": str(e)}
        raise


def get_running_eval_status(run_id: str) -> Optional[Dict[str, Any]]:
    """Get the status of a running evaluation."""
    return _running_evals.get(run_id)
