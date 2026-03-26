# Maestro

[English](README.md) | [한국어](docs/ko/README.md)

Task orchestration daemon for autonomous AI agents. Manages goals, plans tasks, dispatches Claude CLI agents, and tracks results — all running headlessly.

## Quick Start

```bash
pip install -e .
maestro init
maestro start
```

## Daemon

`maestro start` launches the background daemon that runs the full orchestration loop:

```bash
maestro start         # Start daemon (background)
maestro stop          # Stop daemon
maestro status        # Show PID, port, dashboard URL
```

The daemon runs four loops concurrently:

- **Planner** — evaluates goals, creates tasks
- **Dispatcher** — assigns pending tasks to Claude CLI agents
- **Scheduler** — triggers cron-based recurring tasks
- **Reconciler** — detects stalled agents, handles timeouts

All agents run via `claude` CLI with `--dangerously-skip-permissions` by default, giving them full access to all tools (MCP servers, WebFetch, WebSearch, etc.).

## Web Dashboard

The dashboard starts automatically with the daemon on a random available port.

```bash
maestro status        # Shows: http://localhost:<port>
```

From the dashboard you can:

- View and manage tasks, goals, schedules, assets, and rules
- Approve / reject / revise agent outputs
- Watch agent logs in real-time
- Track costs and activity

The dashboard is a React SPA served from `web/dist/` by the daemon's HTTP server.

## Usage

### Initialize a project

```bash
maestro init
```

Creates `maestro.yaml`, `.maestro/` directories, SQLite database, and MCP server config.

### Define a goal

```bash
maestro goal add \
  --id weekly-posts \
  --description "Publish 3 blog posts per week" \
  --cooldown-hours 168
```

### Create a task manually

```bash
maestro task add \
  --title "Write intro post" \
  --instruction "Write a blog post about our new product launch" \
  --priority 2
```

### Schedule recurring tasks

```bash
maestro schedule add \
  --name daily-review \
  --task-type claude \
  --cron "0 9 * * *"
```

### Approve agent work

Tasks with `approval_level: 2` (default) pause after completion for human review:

```bash
maestro task approve <task-id>
maestro task reject <task-id>
maestro task revise <task-id> --note "Change the tone to be more casual"
```

## Configuration

All settings in `maestro.yaml`. See [Configuration Reference](docs/en/CONFIGURATION.md) for full parameter docs.

```yaml
agent:
  permission_mode: bypass    # All tools available (default)

agents:
  planner:
    role: "Plan tasks from goals"
    max_turns: 30
    no_worktree: true
  default:
    max_turns: 50

budget:
  daily_limit_usd: 30.0
  per_task_limit_usd: 5.0
```

## Requirements

- Python 3.11+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) installed

## License

[MIT](LICENSE)
