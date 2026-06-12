"""Database abstraction layer.

Provides repository interfaces and implementations for trace
and evaluation storage. Supports SQLite (default) and PostgreSQL.
"""

from .base import TraceRepository, EvaluationRepository
from .connection import get_database
from .sqlite_impl import SQLiteTraceRepository, SQLiteEvaluationRepository
from .postgres_impl import PostgresTraceRepository, PostgresEvaluationRepository

__all__ = [
    "TraceRepository",
    "EvaluationRepository",
    "SQLiteTraceRepository",
    "SQLiteEvaluationRepository",
    "PostgresTraceRepository",
    "PostgresEvaluationRepository",
    "get_database",
]
