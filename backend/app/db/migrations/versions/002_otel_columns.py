"""Migration 002: Add OTel semantic convention columns.

Adds otel_operation to spans table for OpenTelemetry GenAI
semantic convention compatibility.
"""


def upgrade(conn):
    # Check if column already exists (idempotent)
    cols = conn.execute("PRAGMA table_info(spans)").fetchall()
    col_names = {col["name"] for col in cols}

    if "otel_operation" not in col_names:
        conn.execute("ALTER TABLE spans ADD COLUMN otel_operation TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_spans_otel_operation ON spans(otel_operation)"
        )


def downgrade(conn):
    # SQLite does not support DROP COLUMN before 3.35.0
    # For older versions, this is a no-op; the column simply remains unused.
    try:
        conn.execute("DROP INDEX IF EXISTS idx_spans_otel_operation")
        conn.execute("ALTER TABLE spans DROP COLUMN otel_operation")
    except Exception:
        # Column doesn't exist or SQLite version doesn't support DROP COLUMN
        pass
