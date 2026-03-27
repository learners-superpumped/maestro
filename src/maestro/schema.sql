-- Maestro SQLite schema
-- Applied via store.py init_db() using aiosqlite executescript().

-- Auto-increment sequence for human-readable task numbers (MAE-1, MAE-2, …)
CREATE TABLE IF NOT EXISTS task_seq (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    next_val INTEGER NOT NULL DEFAULT 1
);
INSERT OR IGNORE INTO task_seq (id, next_val) VALUES (1, 1);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    task_number INTEGER NOT NULL UNIQUE,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    title TEXT NOT NULL,
    instruction TEXT NOT NULL,
    agent TEXT DEFAULT 'default',
    no_worktree INTEGER DEFAULT 0,
    goal_id TEXT,
    parent_task_id TEXT,
    depends_on TEXT,
    priority INTEGER DEFAULT 3,
    approval_level INTEGER DEFAULT 2,
    schedule TEXT,
    deadline TEXT,
    session_id TEXT,
    attempt INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    budget_usd REAL DEFAULT 5.0,
    result TEXT,
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
CREATE INDEX IF NOT EXISTS idx_tasks_goal ON tasks(goal_id);
CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent);
CREATE INDEX IF NOT EXISTS idx_tasks_scheduled ON tasks(scheduled_at);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    task_id TEXT REFERENCES tasks(id),
    created_by TEXT NOT NULL DEFAULT 'human',
    asset_type TEXT NOT NULL,
    media_type TEXT,
    title TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    content_json TEXT,
    file_path TEXT,
    file_size INTEGER,
    drive_file_id   TEXT,
    drive_url       TEXT,
    drive_folder_id TEXT,
    source          TEXT DEFAULT 'local',
    embedding_model TEXT DEFAULT 'gemini-embedding-2-preview',
    embedded_at TEXT,
    ttl_days INTEGER,
    expires_at TEXT,
    archived INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_usage (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id),
    task_id TEXT NOT NULL REFERENCES tasks(id),
    usage_type TEXT DEFAULT 'reference',
    used_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_archived ON assets(archived);
CREATE INDEX IF NOT EXISTS idx_assets_expires ON assets(expires_at);
CREATE INDEX IF NOT EXISTS idx_assets_task ON assets(task_id);
CREATE INDEX IF NOT EXISTS idx_asset_usage_asset ON asset_usage(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_usage_task ON asset_usage(task_id);

CREATE TABLE IF NOT EXISTS action_history (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
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

CREATE TABLE IF NOT EXISTS goals (
    id                   TEXT PRIMARY KEY,
    description          TEXT NOT NULL DEFAULT '',
    no_worktree          INTEGER DEFAULT 0,
    metrics              TEXT NOT NULL DEFAULT '{}',
    cooldown_hours       INTEGER NOT NULL DEFAULT 24,
    enabled              INTEGER NOT NULL DEFAULT 1,
    last_evaluated_at    TEXT,
    current_gap          TEXT,
    last_task_created_at TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS schedules (
    id             TEXT PRIMARY KEY,
    name           TEXT UNIQUE NOT NULL,
    task_type      TEXT NOT NULL,
    agent          TEXT DEFAULT 'default',
    no_worktree    INTEGER DEFAULT 0,
    cron           TEXT,
    interval_ms    INTEGER,
    approval_level INTEGER NOT NULL DEFAULT 0,
    enabled        INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON schedules(enabled);

CREATE TABLE IF NOT EXISTS auto_extract_rules (
    id          TEXT PRIMARY KEY,
    task_type   TEXT NOT NULL UNIQUE,
    asset_type  TEXT NOT NULL,
    title_field TEXT,
    iterate     TEXT,
    tags_from   TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    detail_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id);
CREATE INDEX IF NOT EXISTS idx_task_events_created ON task_events(created_at);

CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id),
    seq INTEGER NOT NULL,
    log_type TEXT NOT NULL,
    tool_name TEXT,
    summary TEXT NOT NULL,
    content TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_task_logs_task ON task_logs(task_id);

-- FTS5 full-text search index for task history
CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
    task_id UNINDEXED,
    title,
    instruction,
    result_summary,
    tokenize='unicode61'
);

-- Conductor conversations
CREATE TABLE IF NOT EXISTS conductor_conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL DEFAULT '',
    session_id TEXT,
    message_count INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Conductor conversation messages
CREATE TABLE IF NOT EXISTS conductor_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conductor_conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    cost_usd REAL DEFAULT 0.0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_conductor_messages_conv ON conductor_messages(conversation_id);

-- Reminders (one-shot only in v1)
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    message TEXT NOT NULL,
    trigger_at TEXT NOT NULL,
    delivered BOOLEAN DEFAULT FALSE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_reminders_trigger ON reminders(trigger_at) WHERE delivered = FALSE;

-- Slack thread ↔ Conductor conversation mapping
CREATE TABLE IF NOT EXISTS slack_thread_map (
    slack_channel_id TEXT NOT NULL,
    slack_thread_ts TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    slack_user_id TEXT NOT NULL,
    progress_msg_ts TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (slack_channel_id, slack_thread_ts)
);
CREATE INDEX IF NOT EXISTS idx_slack_thread_conversation ON slack_thread_map(conversation_id);
