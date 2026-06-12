"""Connection factory for database repositories.

Reads DATABASE_URL from environment to select the appropriate implementation.
Defaults to SQLite.
"""

import os
import logging
from typing import Tuple

from .base import EvaluationRepository, TraceRepository
from .sqlite_impl import SQLiteEvaluationRepository, SQLiteTraceRepository

logger = logging.getLogger(__name__)

# Default database path (used when DATABASE_URL is not set)
DEFAULT_DB_PATH = os.environ.get("TRACES_DB_PATH", "traces.db")


def get_database() -> Tuple[TraceRepository, EvaluationRepository]:
    """Create and return repository instances based on DATABASE_URL.

    Supported schemes:
    - sqlite://<path>  (default)
    - (future) postgresql://<connection_string>

    Returns a (TraceRepository, EvaluationRepository) tuple.
    """
    database_url = os.environ.get("DATABASE_URL", "")

    if database_url.startswith("postgresql://"):
        # Future: import and instantiate PostgreSQL implementations
        raise NotImplementedError(
            "PostgreSQL support is not yet implemented. "
            "Set DATABASE_URL to sqlite://<path> or leave unset."
        )

    # Default: SQLite
    db_path = DEFAULT_DB_PATH
    if database_url.startswith("sqlite://"):
        db_path = database_url[len("sqlite://"):]

    logger.info(f"Using SQLite database at: {db_path}")
    return (
        SQLiteTraceRepository(db_path=db_path),
        SQLiteEvaluationRepository(db_path=db_path),
    )
