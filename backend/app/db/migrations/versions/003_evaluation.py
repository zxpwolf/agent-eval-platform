"""Migration 003: Evaluation framework tables.

Creates datasets, dataset_items, evaluators, evaluation_runs,
and evaluation_results tables.
"""


def upgrade(conn):
    conn.executescript("""
        -- Datasets
        CREATE TABLE IF NOT EXISTS datasets (
            dataset_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Dataset items (input/expected pairs for evaluation)
        CREATE TABLE IF NOT EXISTS dataset_items (
            item_id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            input_data TEXT,
            expected_output TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dataset_items_dataset_id ON dataset_items(dataset_id);

        -- Evaluators (heuristic, llm_judge, custom)
        CREATE TABLE IF NOT EXISTS evaluators (
            evaluator_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            evaluator_type TEXT NOT NULL,
            config TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Evaluation runs
        CREATE TABLE IF NOT EXISTS evaluation_runs (
            run_id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            evaluator_ids TEXT,
            trace_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            config TEXT,
            started_at REAL,
            completed_at REAL,
            results_summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_eval_runs_dataset_id ON evaluation_runs(dataset_id);
        CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON evaluation_runs(status);
        CREATE INDEX IF NOT EXISTS idx_eval_runs_created_at ON evaluation_runs(created_at DESC);

        -- Evaluation results (one row per item x evaluator)
        CREATE TABLE IF NOT EXISTS evaluation_results (
            result_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            evaluator_id TEXT NOT NULL,
            score REAL,
            passed INTEGER,
            reasoning TEXT,
            actual_output TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES evaluation_runs(run_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_eval_results_run_id ON evaluation_results(run_id);
        CREATE INDEX IF NOT EXISTS idx_eval_results_item_id ON evaluation_results(item_id);
        CREATE INDEX IF NOT EXISTS idx_eval_results_evaluator_id ON evaluation_results(evaluator_id);
    """)


def downgrade(conn):
    conn.executescript("""
        DROP TABLE IF EXISTS evaluation_results;
        DROP TABLE IF EXISTS evaluation_runs;
        DROP TABLE IF EXISTS evaluators;
        DROP TABLE IF EXISTS dataset_items;
        DROP TABLE IF EXISTS datasets;
    """)
