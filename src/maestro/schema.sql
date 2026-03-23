-- Maestro SQLite schema
-- Applied via store.py init_db() using aiosqlite executescript().

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    workspace TEXT NOT NULL,
    title TEXT NOT NULL,
    instruction TEXT NOT NULL,
    goal_id TEXT,
    parent_task_id TEXT,
    priority INTEGER DEFAULT 3,
    approval_level INTEGER DEFAULT 2,
    schedule TEXT,
    deadline TEXT,
    session_id TEXT,
    attempt INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    budget_usd REAL DEFAULT 5.0,
    result_json TEXT,
    error TEXT,
    cost_usd REAL DEFAULT 0.0,
    review_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    scheduled_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    timeout_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace ON tasks(workspace);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled ON tasks(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    path TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    embedding_model TEXT,
    embedded_at TEXT,
    platforms_published TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_assets (
    task_id TEXT NOT NULL REFERENCES tasks(id),
    asset_id TEXT NOT NULL REFERENCES assets(id),
    role TEXT DEFAULT 'reference',
    PRIMARY KEY (task_id, asset_id)
);

CREATE TABLE IF NOT EXISTS action_history (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    workspace TEXT NOT NULL,
    action_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    content TEXT,
    target_url TEXT,
    asset_ids TEXT,
    result_url TEXT,
    metrics TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    status TEXT NOT NULL DEFAULT 'pending',
    draft_json TEXT NOT NULL,
    reviewer_note TEXT,
    revised_content TEXT,
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS budget_daily (
    date TEXT PRIMARY KEY,
    total_cost_usd REAL DEFAULT 0.0,
    task_count INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goal_state (
    goal_id TEXT PRIMARY KEY,
    last_evaluated_at TEXT,
    current_gap TEXT,
    last_task_created_at TEXT,
    updated_at TEXT NOT NULL
);

-- Schedule execution history
CREATE TABLE IF NOT EXISTS schedule_runs (
    name        TEXT PRIMARY KEY,
    last_run_at TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Scheduler state (last tick time etc.)
CREATE TABLE IF NOT EXISTS scheduler_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    task_id TEXT,
    message TEXT NOT NULL,
    delivered INTEGER DEFAULT 0,
    channel TEXT DEFAULT 'log',
    created_at TEXT NOT NULL
);
