"""Custom evaluator wrapper.

Allows users to provide their own Python callable as an evaluator.
"""

import logging
import time
from typing import Any, Callable, Dict, Optional

from .base import EvaluationResult, Evaluator

logger = logging.getLogger(__name__)


class CustomEvaluator(Evaluator):
    """Wraps a user-provided callable as an evaluator.

    Config:
        evaluate_fn (callable): A function with signature
            (input_data, expected_output, actual_output) -> dict
            The returned dict should have keys: score (float), passed (bool),
            reasoning (str). Missing keys get defaults.
        timeout (float): Max seconds for evaluation (default 30).
        name (str): Display name for this evaluator.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._evaluate_fn: Optional[Callable] = config.get("evaluate_fn") if config else None

    def set_evaluate_fn(self, fn: Callable) -> None:
        """Set the evaluation function."""
        self._evaluate_fn = fn

    def validate_config(self) -> bool:
        if self._evaluate_fn is None:
            logger.warning("No evaluate_fn configured.")
            return False
        return True

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        if self._evaluate_fn is None:
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning="No evaluate_fn configured. Call set_evaluate_fn() first.",
            )

        timeout = self.config.get("timeout", 30.0)
        start = time.time()

        try:
            result = self._evaluate_fn(input_data, expected_output, actual_output)
        except Exception as e:
            logger.error(f"Custom evaluator failed: {e}")
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning=f"Custom evaluator error: {e}",
            )

        elapsed = time.time() - start
        if elapsed > timeout:
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning=f"Custom evaluator timed out after {elapsed:.1f}s (limit: {timeout}s)",
            )

        # Normalize result
        if isinstance(result, EvaluationResult):
            return result

        if isinstance(result, dict):
            score = float(result.get("score", 0.0))
            score = max(0.0, min(1.0, score))
            return EvaluationResult(
                score=score,
                passed=bool(result.get("passed", score >= 0.5)),
                reasoning=str(result.get("reasoning", "")),
                metadata={**result.get("metadata", {}), "elapsed_s": elapsed},
            )

        # If result is just a float/bool, wrap it
        if isinstance(result, (int, float)):
            score = max(0.0, min(1.0, float(result)))
            return EvaluationResult(
                score=score,
                passed=score >= 0.5,
                reasoning=f"Score: {score}",
                metadata={"elapsed_s": elapsed},
            )

        if isinstance(result, bool):
            return EvaluationResult(
                score=1.0 if result else 0.0,
                passed=result,
                reasoning=f"Passed: {result}",
                metadata={"elapsed_s": elapsed},
            )

        return EvaluationResult(
            score=0.0,
            passed=False,
            reasoning=f"Unexpected result type: {type(result)}",
        )
