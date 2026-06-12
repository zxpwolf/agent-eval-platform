"""Abstract repository interfaces for database operations.

These ABCs define the storage contracts so the backend can swap
between SQLite and PostgreSQL (or any other store) without touching
business logic.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class TraceRepository(ABC):
    """Abstract interface for trace and span storage."""

    @abstractmethod
    def store_trace(self, trace_data: Dict[str, Any]) -> bool:
        """Store a complete trace with all its spans. Returns True on success."""

    @abstractmethod
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get a trace by ID with all its spans."""

    @abstractmethod
    def list_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List traces with optional filtering."""

    @abstractmethod
    def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace and all its spans."""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate database statistics."""

    @abstractmethod
    def list_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List distinct session IDs with metadata."""

    @abstractmethod
    def get_session_traces(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all traces belonging to a session."""


class EvaluationRepository(ABC):
    """Abstract interface for evaluation storage (datasets, evaluators, runs, results)."""

    # ── Datasets ──────────────────────────────

    @abstractmethod
    def create_dataset(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new evaluation dataset."""

    @abstractmethod
    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Get a dataset with its items."""

    @abstractmethod
    def list_datasets(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all datasets."""

    @abstractmethod
    def update_dataset(self, dataset_id: str, data: Dict[str, Any]) -> bool:
        """Update dataset metadata."""

    @abstractmethod
    def delete_dataset(self, dataset_id: str) -> bool:
        """Delete a dataset and its items."""

    # ── Dataset Items ─────────────────────────

    @abstractmethod
    def add_dataset_items(self, dataset_id: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add items to a dataset."""

    @abstractmethod
    def delete_dataset_item(self, dataset_id: str, item_id: str) -> bool:
        """Remove an item from a dataset."""

    # ── Evaluators ────────────────────────────

    @abstractmethod
    def create_evaluator(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new evaluator."""

    @abstractmethod
    def get_evaluator(self, evaluator_id: str) -> Optional[Dict[str, Any]]:
        """Get an evaluator by ID."""

    @abstractmethod
    def list_evaluators(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List all evaluators."""

    @abstractmethod
    def delete_evaluator(self, evaluator_id: str) -> bool:
        """Delete an evaluator."""

    # ── Evaluation Runs ───────────────────────

    @abstractmethod
    def create_evaluation_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new evaluation run record."""

    @abstractmethod
    def get_evaluation_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get an evaluation run with its results."""

    @abstractmethod
    def list_evaluation_runs(
        self,
        dataset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List evaluation runs with optional filtering."""

    @abstractmethod
    def update_evaluation_run(self, run_id: str, data: Dict[str, Any]) -> bool:
        """Update evaluation run status/summary."""

    # ── Evaluation Results ────────────────────

    @abstractmethod
    def store_evaluation_results(self, run_id: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Store evaluation results for a run."""

    @abstractmethod
    def get_evaluation_results(self, run_id: str) -> List[Dict[str, Any]]:
        """Get all results for a given run."""
