"""LLM-as-judge evaluator.

Uses a configurable LLM to evaluate agent outputs against expected results.
The judge model scores outputs based on a rubric/prompt template.
"""

import json
import logging
from typing import Any, Callable, Dict, Optional

from .base import EvaluationResult, Evaluator

logger = logging.getLogger(__name__)

DEFAULT_JUDGE_PROMPT = """You are an expert evaluator. Your task is to evaluate the quality of an AI agent's response.

## Input
{input_data}

## Expected Output
{expected_output}

## Actual Output
{actual_output}

## Evaluation Criteria
{rubric}

## Instructions
Evaluate the actual output against the expected output based on the criteria above.
Respond with a JSON object containing exactly these fields:
- "score": a float from 0.0 to 1.0 representing the quality score
- "passed": a boolean indicating if the output meets the minimum threshold
- "reasoning": a string explaining your evaluation

Respond ONLY with the JSON object, no additional text."""


class LLMJudgeEvaluator(Evaluator):
    """Evaluates outputs using an LLM as a judge.

    Config:
        judge_fn (callable): A function that takes a prompt string and returns
            a string response. This decouples the evaluator from any specific
            LLM provider.
        rubric (str): Evaluation criteria / rubric text.
        prompt_template (str, optional): Custom prompt template. Use
            {input_data}, {expected_output}, {actual_output}, {rubric} placeholders.
        pass_threshold (float): Minimum score to pass (default 0.6).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._judge_fn: Optional[Callable[[str], str]] = config.get("judge_fn") if config else None

    def set_judge_fn(self, fn: Callable[[str], str]) -> None:
        """Set the judge function (callable that takes prompt, returns response text)."""
        self._judge_fn = fn

    def validate_config(self) -> bool:
        if self._judge_fn is None:
            logger.warning("No judge_fn configured. Call set_judge_fn() or include 'judge_fn' in config.")
            return False
        return True

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        if self._judge_fn is None:
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning="No judge_fn configured. Call set_judge_fn() first.",
            )

        rubric = self.config.get("rubric", "Evaluate accuracy, completeness, and relevance.")
        template = self.config.get("prompt_template", DEFAULT_JUDGE_PROMPT)
        pass_threshold = self.config.get("pass_threshold", 0.6)

        prompt = template.format(
            input_data=self._normalize_output(input_data),
            expected_output=self._normalize_output(expected_output),
            actual_output=self._normalize_output(actual_output),
            rubric=rubric,
        )

        try:
            response = self._judge_fn(prompt)
            return self._parse_judge_response(response, pass_threshold)
        except Exception as e:
            logger.error(f"Judge function failed: {e}")
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning=f"Judge function error: {e}",
            )

    def _parse_judge_response(self, response: str, pass_threshold: float) -> EvaluationResult:
        """Parse the LLM judge's response into an EvaluationResult."""
        # Try to extract JSON from the response
        text = response.strip()

        # Handle markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(text)
            score = float(data.get("score", 0.0))
            score = max(0.0, min(1.0, score))  # clamp to [0, 1]
            passed = data.get("passed", score >= pass_threshold)
            reasoning = data.get("reasoning", "")

            return EvaluationResult(
                score=score,
                passed=bool(passed),
                reasoning=str(reasoning),
                metadata={"raw_response": response},
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(f"Failed to parse judge response as JSON: {e}")
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning=f"Failed to parse judge response: {e}. Raw: {response[:200]}",
            )
