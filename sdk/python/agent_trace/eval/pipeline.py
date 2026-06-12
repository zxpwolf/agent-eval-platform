"""Evaluation pipeline orchestrator.

Coordinates running evaluations across datasets, evaluators, and
agent outputs. Supports both offline (stored trace) and live
(agent callable) modes.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .base import EvaluationResult, Evaluator

logger = logging.getLogger(__name__)


@dataclass
class PipelineProgress:
    """Progress information for a running pipeline."""
    total_items: int = 0
    completed_items: int = 0
    current_item: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    error: Optional[str] = None

    @property
    def percentage(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "current_item": self.current_item,
            "status": self.status,
            "error": self.error,
            "percentage": self.percentage,
        }


@dataclass
class PipelineResult:
    """Complete result from a pipeline run."""
    run_id: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    elapsed_s: float = 0.0


class EvaluationPipeline:
    """Orchestrates running evaluations across datasets and evaluators.

    Supports two modes:
    - Offline: Evaluate against stored actual outputs
    - Live: Generate outputs by calling an agent callable per item
    """

    def __init__(
        self,
        evaluators: List[Evaluator],
        progress_callback: Optional[Callable[[PipelineProgress], None]] = None,
    ):
        self.evaluators = evaluators
        self.progress_callback = progress_callback
        self._progress = PipelineProgress()

    def _report_progress(self, **kwargs: Any) -> None:
        """Update progress and notify callback."""
        for key, value in kwargs.items():
            if hasattr(self._progress, key):
                setattr(self._progress, key, value)
        if self.progress_callback:
            try:
                self.progress_callback(self._progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def run(
        self,
        dataset_items: List[Dict[str, Any]],
        actual_outputs: Optional[List[Any]] = None,
        agent_fn: Optional[Callable[[Any], Any]] = None,
    ) -> PipelineResult:
        """Run the evaluation pipeline.

        Args:
            dataset_items: List of dataset items, each with 'item_id',
                'input_data', and 'expected_output'.
            actual_outputs: Pre-computed actual outputs (one per item).
                Mutually exclusive with agent_fn.
            agent_fn: A callable that generates actual output from input_data.
                Mutually exclusive with actual_outputs.

        Returns:
            PipelineResult with all results and summary statistics.
        """
        run_id = str(uuid.uuid4())
        start_time = time.time()
        self._progress = PipelineProgress(total_items=len(dataset_items), status="running")
        self._report_progress()

        results: List[Dict[str, Any]] = []
        all_scores: List[float] = []

        for i, item in enumerate(dataset_items):
            item_id = item.get("item_id", f"item_{i}")
            input_data = item.get("input_data")
            expected_output = item.get("expected_output")

            self._report_progress(current_item=item_id)

            # Get actual output
            if actual_outputs is not None:
                actual_output = actual_outputs[i] if i < len(actual_outputs) else None
            elif agent_fn is not None:
                try:
                    actual_output = agent_fn(input_data)
                except Exception as e:
                    logger.error(f"Agent function failed for item {item_id}: {e}")
                    actual_output = None
            else:
                actual_output = item.get("actual_output")

            # Run each evaluator
            for evaluator in self.evaluators:
                eval_name = evaluator.__class__.__name__
                try:
                    result = evaluator.evaluate(input_data, expected_output, actual_output)
                except Exception as e:
                    logger.error(f"Evaluator {eval_name} failed on item {item_id}: {e}")
                    result = EvaluationResult(
                        score=0.0,
                        passed=False,
                        reasoning=f"Evaluator error: {e}",
                    )

                results.append({
                    "result_id": str(uuid.uuid4()),
                    "item_id": item_id,
                    "evaluator_name": eval_name,
                    "evaluator_id": getattr(evaluator, "evaluator_id", eval_name),
                    **result.to_dict(),
                    "actual_output": actual_output,
                })
                all_scores.append(result.score)

            self._report_progress(completed_items=i + 1)

        # Compute summary
        summary = self._compute_summary(all_scores, results)

        elapsed = time.time() - start_time
        self._report_progress(status="completed")

        return PipelineResult(
            run_id=run_id,
            results=results,
            summary=summary,
            elapsed_s=elapsed,
        )

    def _compute_summary(
        self, scores: List[float], results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute aggregate summary statistics."""
        if not scores:
            return {"total": 0, "average_score": 0.0, "pass_rate": 0.0}

        passed_count = sum(1 for r in results if r.get("passed"))
        total = len(results)

        # Per-evaluator breakdown
        by_evaluator: Dict[str, List[float]] = {}
        for r in results:
            name = r.get("evaluator_name", "unknown")
            by_evaluator.setdefault(name, []).append(r.get("score", 0.0))

        evaluator_summaries = {}
        for name, eval_scores in by_evaluator.items():
            evaluator_summaries[name] = {
                "average_score": sum(eval_scores) / len(eval_scores) if eval_scores else 0.0,
                "min_score": min(eval_scores) if eval_scores else 0.0,
                "max_score": max(eval_scores) if eval_scores else 0.0,
                "count": len(eval_scores),
            }

        return {
            "total": total,
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "pass_rate": passed_count / total if total > 0 else 0.0,
            "passed_count": passed_count,
            "failed_count": total - passed_count,
            "by_evaluator": evaluator_summaries,
        }
