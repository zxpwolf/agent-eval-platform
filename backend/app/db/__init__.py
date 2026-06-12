"""Database abstraction layer.

Provides repository interfaces and SQLite implementation for trace
and evaluation storage. Designed for easy migration to PostgreSQL.
"""

from .base import TraceRepository, EvaluationRepository
from .connection import get_database
from .sqlite_impl import SQLiteTraceRepository, SQLiteEvaluationRepository

__all__ = [
    "TraceRepository",
    "EvaluationRepository",
    "SQLiteTraceRepository",
    "SQLiteEvaluationRepository",
    "get_database",
]
