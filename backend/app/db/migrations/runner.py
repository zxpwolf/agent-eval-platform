"""Lightweight database migration runner.

Manages schema evolution without external dependencies (no Alembic).
On startup, ensures the `schema_migrations` table exists, then applies
any unapplied migration versions in order.
"""

import importlib
import logging
import sqlite3
from pathlib import Path
from typing import List, Set

logger = logging.getLogger(__name__)

MIGRATIONS_PACKAGE = "app.db.migrations.versions"
MIGRATIONS_DIR = Path(__file__).parent / "versions"


def _get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def _applied_versions(conn: sqlite3.Connection) -> Set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row["version"] for row in rows}


def _discover_versions() -> List[str]:
    """Discover migration modules sorted by filename prefix (001_, 002_, ...)."""
    versions = []
    for path in sorted(MIGRATIONS_DIR.glob("[0-9]*.py")):
        if path.name.startswith("_"):
            continue
        versions.append(path.stem)
    return versions


def run_migrations(db_path: str) -> None:
    """Apply all pending migrations to the database at `db_path`."""
    conn = _get_connection(db_path)
    try:
        _ensure_migrations_table(conn)
        applied = _applied_versions(conn)
        pending = [v for v in _discover_versions() if v not in applied]

        if not pending:
            logger.info("Database schema is up to date")
            return

        for version in pending:
            module_name = f"{MIGRATIONS_PACKAGE}.{version}"
            logger.info(f"Applying migration: {version}")
            try:
                module = importlib.import_module(module_name)
                module.upgrade(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)",
                    (version,),
                )
                conn.commit()
                logger.info(f"Migration {version} applied successfully")
            except Exception as e:
                logger.error(f"Failed to apply migration {version}: {e}")
                conn.rollback()
                raise
    finally:
        conn.close()


def rollback_migration(db_path: str, version: str) -> None:
    """Rollback a specific migration version."""
    conn = _get_connection(db_path)
    try:
        module_name = f"{MIGRATIONS_PACKAGE}.{version}"
        logger.info(f"Rolling back migration: {version}")
        try:
            module = importlib.import_module(module_name)
            module.downgrade(conn)
            conn.execute(
                "DELETE FROM schema_migrations WHERE version = ?",
                (version,),
            )
            conn.commit()
            logger.info(f"Migration {version} rolled back successfully")
        except Exception as e:
            logger.error(f"Failed to rollback migration {version}: {e}")
            conn.rollback()
            raise
    finally:
        conn.close()
