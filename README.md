# Maestro

[English](README.md) | [한국어](docs/ko/README.md)

Task orchestration daemon for autonomous AI agents. Manages goals, plans tasks, dispatches Claude CLI agents, and tracks results — all running headlessly.

## Quick Start

```bash
pip install -e .
maestro init
maestro start
```

Open the dashboard at the URL shown in `maestro status`.

## How It Works

```text
Goal -> Planner -> Tasks -> Dispatcher -> Claude Agents -> Results
```

1. **Goals** define what to achieve (with targets and check frequency)
2. **Planner** evaluates goals and creates tasks
3. **Dispatcher** assigns tasks to agents
4. **Agents** execute via Claude CLI with full tool access
5. **Results** are reviewed, approved, or retried

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

### Monitor via CLI

```bash
maestro status        # Daemon status + dashboard URL
maestro task list     # List all tasks
maestro goal list     # List all goals
maestro schedule list # List schedules
```

### Monitor via Dashboard

The web dashboard runs automatically with the daemon. Access it at the URL shown by `maestro status`.

- View and manage tasks, goals, schedules, assets, and rules
- Approve/reject/revise agent outputs
- Track costs and agent activity in real-time

### Approve agent work

Tasks with `approval_level: 2` (default) pause after completion for human review. Approve from the dashboard or CLI:

```bash
maestro task approve <task-id>
maestro task reject <task-id>
maestro task revise <task-id> --note "Change the tone to be more casual"
```

## Configuration

All settings in `maestro.yaml`. See [Configuration Reference](docs/en/maestro-yaml-reference.md) for full parameter docs.

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
