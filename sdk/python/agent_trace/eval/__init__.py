"""Evaluation framework for agent traces.

Provides evaluators (heuristic, LLM-as-judge, custom) and a scoring
pipeline for running evaluations against datasets.
"""

from .base import Evaluator, EvaluationResult
from .heuristic import (
    RegexMatchEvaluator,
    ContainsEvaluator,
    JsonValidEvaluator,
    ExactMatchEvaluator,
    LengthEvaluator,
    KeywordEvaluator,
)
from .llm_judge import LLMJudgeEvaluator
from .custom import CustomEvaluator
from .pipeline import EvaluationPipeline

__all__ = [
    "Evaluator",
    "EvaluationResult",
    "RegexMatchEvaluator",
    "ContainsEvaluator",
    "JsonValidEvaluator",
    "ExactMatchEvaluator",
    "LengthEvaluator",
    "KeywordEvaluator",
    "LLMJudgeEvaluator",
    "CustomEvaluator",
    "EvaluationPipeline",
]
