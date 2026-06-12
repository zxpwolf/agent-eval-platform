"""Migration 001: Initial schema.

Creates the core traces and spans tables with indexes.
"""


def upgrade(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL,
            user_id TEXT,
            session_id TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS spans (
            span_id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            name TEXT NOT NULL,
            span_type TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL,
            parent_span_id TEXT,
            status TEXT NOT NULL DEFAULT 'ok',
            attributes TEXT,
            events TEXT,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            cost REAL,
            input_data TEXT,
            output_data TEXT,
            FOREIGN KEY (trace_id) REFERENCES traces(trace_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_traces_user_id ON traces(user_id);
        CREATE INDEX IF NOT EXISTS idx_traces_session_id ON traces(session_id);
        CREATE INDEX IF NOT EXISTS idx_traces_start_time ON traces(start_time DESC);
        CREATE INDEX IF NOT EXISTS idx_spans_trace_id ON spans(trace_id);
        CREATE INDEX IF NOT EXISTS idx_spans_parent_span_id ON spans(parent_span_id);
        CREATE INDEX IF NOT EXISTS idx_spans_span_type ON spans(span_type);
        CREATE INDEX IF NOT EXISTS idx_spans_model ON spans(model);
    """)


def downgrade(conn):
    conn.executescript("""
        DROP TABLE IF EXISTS spans;
        DROP TABLE IF EXISTS traces;
    """)
