"""Base classes for the evaluation framework."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class EvaluationResult:
    """Result of evaluating a single item with a single evaluator."""
    score: float  # 0.0 to 1.0 normalized
    passed: bool
    reasoning: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


class Evaluator(ABC):
    """Abstract base class for all evaluators.

    Subclasses must implement `evaluate()` and optionally `validate_config()`.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    def evaluate(
        self,
        input_data: Any,
        expected_output: Any,
        actual_output: Any,
    ) -> EvaluationResult:
        """Evaluate the actual output against the expected output.

        Args:
            input_data: The original input/prompt.
            expected_output: The ground truth / expected response.
            actual_output: What the agent actually produced.

        Returns:
            EvaluationResult with score, pass/fail, and reasoning.
        """

    def validate_config(self) -> bool:
        """Validate that the evaluator's config is correct.

        Returns True if valid. Subclasses can override to add checks.
        """
        return True

    def _normalize_output(self, output: Any) -> str:
        """Convert output to string for comparison."""
        if output is None:
            return ""
        if isinstance(output, dict):
            import json
            return json.dumps(output, sort_keys=True, ensure_ascii=False)
        return str(output)
