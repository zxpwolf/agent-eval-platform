"""Heuristic evaluators - rule-based, deterministic evaluation."""

import json
import re
from typing import Any, Dict, List, Optional

from .base import EvaluationResult, Evaluator


class RegexMatchEvaluator(Evaluator):
    """Evaluates whether actual output matches a regex pattern.

    Config:
        pattern (str): The regex pattern to match against.
        flags (int, optional): Regex flags (e.g., re.IGNORECASE).
    """

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        pattern = self.config.get("pattern", "")
        flags = self.config.get("flags", 0)
        text = self._normalize_output(actual_output)

        try:
            match = re.search(pattern, text, flags)
            passed = match is not None
            return EvaluationResult(
                score=1.0 if passed else 0.0,
                passed=passed,
                reasoning=f"Pattern '{pattern}' {'matched' if passed else 'did not match'} the output",
            )
        except re.error as e:
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning=f"Invalid regex pattern: {e}",
            )


class ContainsEvaluator(Evaluator):
    """Evaluates whether actual output contains expected string(s).

    Config:
        terms (list[str]): Strings that must be present.
        case_sensitive (bool): Whether matching is case-sensitive (default True).
        mode (str): 'all' (all terms must be present) or 'any' (at least one).
    """

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        terms = self.config.get("terms", [])
        case_sensitive = self.config.get("case_sensitive", True)
        mode = self.config.get("mode", "all")
        text = self._normalize_output(actual_output)

        if not case_sensitive:
            text = text.lower()
            terms = [t.lower() for t in terms]

        found = [t for t in terms if t in text]

        if mode == "any":
            passed = len(found) > 0
        else:
            passed = len(found) == len(terms)

        score = len(found) / len(terms) if terms else 1.0
        missing = [t for t in terms if t not in found]

        reasoning = f"Found {len(found)}/{len(terms)} terms"
        if missing:
            reasoning += f". Missing: {missing}"

        return EvaluationResult(
            score=score,
            passed=passed,
            reasoning=reasoning,
            metadata={"found": found, "missing": missing},
        )


class JsonValidEvaluator(Evaluator):
    """Evaluates whether actual output is valid JSON.

    Config:
        required_keys (list[str], optional): Keys that must be present in the JSON.
    """

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        text = self._normalize_output(actual_output)
        required_keys = self.config.get("required_keys", [])

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError) as e:
            return EvaluationResult(
                score=0.0,
                passed=False,
                reasoning=f"Invalid JSON: {e}",
            )

        if required_keys:
            if isinstance(parsed, dict):
                missing = [k for k in required_keys if k not in parsed]
                if missing:
                    return EvaluationResult(
                        score=0.5,
                        passed=False,
                        reasoning=f"JSON valid but missing keys: {missing}",
                        metadata={"missing_keys": missing},
                    )
            else:
                return EvaluationResult(
                    score=0.5,
                    passed=False,
                    reasoning="JSON is valid but not an object (required_keys check needs object)",
                )

        return EvaluationResult(
            score=1.0,
            passed=True,
            reasoning="Valid JSON" + (f" with all required keys: {required_keys}" if required_keys else ""),
        )


class ExactMatchEvaluator(Evaluator):
    """Evaluates whether actual output exactly matches expected output.

    Config:
        ignore_case (bool): Ignore case differences (default False).
        ignore_whitespace (bool): Normalize whitespace (default False).
    """

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        ignore_case = self.config.get("ignore_case", False)
        ignore_whitespace = self.config.get("ignore_whitespace", False)

        expected = self._normalize_output(expected_output)
        actual = self._normalize_output(actual_output)

        if ignore_case:
            expected = expected.lower()
            actual = actual.lower()
        if ignore_whitespace:
            expected = " ".join(expected.split())
            actual = " ".join(actual.split())

        passed = expected == actual
        return EvaluationResult(
            score=1.0 if passed else 0.0,
            passed=passed,
            reasoning="Exact match" if passed else "Output does not match expected",
        )


class LengthEvaluator(Evaluator):
    """Evaluates whether actual output length is within bounds.

    Config:
        min_length (int, optional): Minimum character count.
        max_length (int, optional): Maximum character count.
    """

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        text = self._normalize_output(actual_output)
        min_len = self.config.get("min_length", 0)
        max_len = self.config.get("max_length", float("inf"))
        length = len(text)

        passed = min_len <= length <= max_len
        if passed:
            reasoning = f"Length {length} is within bounds [{min_len}, {max_len}]"
            score = 1.0
        else:
            reasoning = f"Length {length} is outside bounds [{min_len}, {max_len}]"
            # Partial score based on how close to bounds
            if length < min_len:
                score = max(0.0, length / min_len) if min_len > 0 else 0.0
            else:
                score = max(0.0, 1.0 - (length - max_len) / max_len) if max_len < float("inf") else 0.0

        return EvaluationResult(
            score=score,
            passed=passed,
            reasoning=reasoning,
            metadata={"length": length, "min": min_len, "max": max_len},
        )


class KeywordEvaluator(Evaluator):
    """Evaluates presence of required keywords and absence of forbidden ones.

    Config:
        required (list[str]): Keywords that must appear.
        forbidden (list[str]): Keywords that must not appear.
        case_sensitive (bool): Case sensitivity (default False).
    """

    def evaluate(self, input_data: Any, expected_output: Any, actual_output: Any) -> EvaluationResult:
        required = self.config.get("required", [])
        forbidden = self.config.get("forbidden", [])
        case_sensitive = self.config.get("case_sensitive", False)
        text = self._normalize_output(actual_output)

        if not case_sensitive:
            text = text.lower()
            required = [k.lower() for k in required]
            forbidden = [k.lower() for k in forbidden]

        missing_required = [k for k in required if k not in text]
        found_forbidden = [k for k in forbidden if k in text]

        total_checks = len(required) + len(forbidden)
        if total_checks == 0:
            return EvaluationResult(score=1.0, passed=True, reasoning="No keywords configured")

        passed_checks = total_checks - len(missing_required) - len(found_forbidden)
        score = passed_checks / total_checks
        passed = len(missing_required) == 0 and len(found_forbidden) == 0

        parts = []
        if missing_required:
            parts.append(f"Missing required: {missing_required}")
        if found_forbidden:
            parts.append(f"Found forbidden: {found_forbidden}")
        if not parts:
            parts.append("All keyword checks passed")

        return EvaluationResult(
            score=score,
            passed=passed,
            reasoning="; ".join(parts),
            metadata={"missing_required": missing_required, "found_forbidden": found_forbidden},
        )
