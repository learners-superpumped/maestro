# maestro.yaml Configuration Reference

[English](maestro-yaml-reference.md) | [한국어](../ko/maestro-yaml-reference.md)

Complete reference for all `maestro.yaml` configuration parameters.

---

## `project` (required)

| Parameter    | Type   | Default              | Description                        |
| ------------ | ------ | -------------------- | ---------------------------------- |
| `name`       | string | —                    | Project name identifier (required) |
| `store_path` | string | `./store/maestro.db` | Path to SQLite database file       |

## `daemon`

| Parameter                | Type | Default  | Description                                             |
| ------------------------ | ---- | -------- | ------------------------------------------------------- |
| `planner_interval_ms`    | int  | `300000` | How often the planner evaluates goals (ms)              |
| `dispatcher_interval_ms` | int  | `10000`  | How often the dispatcher picks up pending tasks (ms)    |
| `reconcile_interval_ms`  | int  | `30000`  | How often the reconciler checks for stalled agents (ms) |
| `scheduler_interval_ms`  | int  | `10000`  | How often the scheduler checks cron schedules (ms)      |

## `concurrency`

| Parameter          | Type | Default | Description                                |
| ------------------ | ---- | ------- | ------------------------------------------ |
| `max_total_agents` | int  | `5`     | Maximum concurrent agents across all goals |
| `max_per_goal`     | int  | `1`     | Maximum concurrent agents per goal         |

## `budget`

| Parameter             | Type  | Default | Description                                     |
| --------------------- | ----- | ------- | ----------------------------------------------- |
| `daily_limit_usd`     | float | `30.0`  | 24-hour rolling spend ceiling (USD)             |
| `per_task_limit_usd`  | float | `5.0`   | Per-task spend limit; exceeding aborts the task |
| `alert_threshold_pct` | int   | `80`    | Alert when daily spend reaches this % of limit  |

## `agent`

Global defaults for all agents.

| Parameter               | Type   | Default               | Description                                                                                                             |
| ----------------------- | ------ | --------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `permission_mode`       | string | `"bypass"`            | `"bypass"` = all tools, no prompts (`--dangerously-skip-permissions`). `"restricted"` = whitelist via `--allowedTools`. |
| `default_allowed_tools` | list   | `[Read, Write, Bash]` | Tool whitelist when `permission_mode: restricted`. Ignored in bypass mode.                                              |
| `default_max_turns`     | int    | `20`                  | Max agent turns before forced stop                                                                                      |
| `stall_timeout_ms`      | int    | `300000`              | No-output timeout before agent is marked stalled (ms)                                                                   |
| `turn_timeout_ms`       | int    | `3600000`             | Hard wall-clock time limit per agent turn (ms)                                                                          |
| `max_review_rounds`     | int    | `3`                   | Max review iterations for review tasks                                                                                  |

## `agents`

Named agent definitions. Each key is an agent name.

| Parameter         | Type   | Default               | Description                                                                    |
| ----------------- | ------ | --------------------- | ------------------------------------------------------------------------------ |
| `role`            | string | `""`                  | Agent role description (included in system prompt)                             |
| `instructions`    | string | `""`                  | Path to prompt file (relative to project root)                                 |
| `tools`           | list   | `[Read, Write, Bash]` | Tool whitelist (only used when `permission_mode: restricted`)                  |
| `max_turns`       | int    | `50`                  | Max turns for this agent                                                       |
| `no_worktree`     | bool   | `false`               | Run at project root instead of a git worktree                                  |
| `permission_mode` | string | `""`                  | Override global permission_mode. Empty = inherit from `agent.permission_mode`. |

### Permission Mode Resolution

1. `agents.<name>.permission_mode` (if non-empty)
2. `agent.permission_mode` (global)
3. `"bypass"` (hard default)

## `resources`

Named resource pools for concurrency control.

```yaml
resources:
  chrome-profiles:
    threads:
      max_concurrent: 1
      path: ./chrome-profiles/threads
```

| Parameter        | Type   | Default | Description                               |
| ---------------- | ------ | ------- | ----------------------------------------- |
| `max_concurrent` | int    | `1`     | Max concurrent consumers of this resource |
| `path`           | string | `""`    | Filesystem path for this resource profile |

## `assets`

Asset pipeline configuration.

| Parameter             | Type   | Default    | Description                                          |
| --------------------- | ------ | ---------- | ---------------------------------------------------- |
| `default_ttl`         | dict   | see below  | TTL in days per asset type (`null` = no expiry)      |
| `cleanup_interval_ms` | int    | `86400000` | Cleanup job interval (ms)                            |
| `archive_grace_days`  | int    | `30`       | Days before archived assets are purged               |
| `gemini_api_key`      | string | `""`       | Gemini API key for embeddings (or `$GEMINI_API_KEY`) |

Default TTLs: `post: null, engage: 30, research: 7, image: null, video: null, audio: null, document: null`

## `integrations`

### `integrations.slack`

| Parameter     | Type   | Default | Description                |
| ------------- | ------ | ------- | -------------------------- |
| `webhook_url` | string | `null`  | Slack incoming webhook URL |

### `integrations.linear`

| Parameter      | Type   | Default | Description         |
| -------------- | ------ | ------- | ------------------- |
| `api_key`      | string | `null`  | Linear API key      |
| `project_slug` | string | `null`  | Linear project slug |

## `logging`

| Parameter | Type   | Default                | Description                                    |
| --------- | ------ | ---------------------- | ---------------------------------------------- |
| `level`   | string | `"info"`               | Log level: `debug`, `info`, `warning`, `error` |
| `file`    | string | `"./logs/maestro.log"` | Log file path                                  |

---

## Environment Variables

All string values support `$VAR_NAME` substitution:

```yaml
budget:
  daily_limit_usd: $MAESTRO_DAILY_BUDGET
integrations:
  slack:
    webhook_url: $SLACK_WEBHOOK_URL
```

Undefined variables are left as-is (literal `$VAR_NAME`).
