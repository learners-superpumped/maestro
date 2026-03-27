"""Maestro CLI entry point."""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import signal
import sys
import uuid
from datetime import datetime, timezone

import click

from maestro.models import Task, TaskStatus

_STATUS_EMOJI = {
    "pending": "⏳",
    "approved": "👍",
    "claimed": "🔒",
    "running": "🔄",
    "paused": "⏸️",
    "retry_queued": "🔁",
    "completed": "✅",
    "failed": "❌",
    "cancelled": "🚫",
}

_MAESTRO_YAML_TEMPLATE = """\
project:
  name: "{project_name}"
  store_path: .maestro/store/maestro.db

agent:
  permission_mode: bypass
  # default_max_turns: 0  # 0 = unlimited (budget-only limit)

agents:
  planner:
    role: "Goal을 분석하여 실행 가능한 task로 분해하는 플래너"
    instructions: .maestro/prompts/planner.md
    no_worktree: true
  reviewer:
    role: "Task 결과를 검증하는 리뷰어"
    instructions: .maestro/prompts/reviewer.md
    no_worktree: true
  default: {{}}

concurrency:
  max_total_agents: 2
  max_per_goal: 1

budget:
  daily_limit_usd: 30.0
  per_task_limit_usd: 5.0

logging:
  level: info
  file: .maestro/logs/maestro.log
"""


def _status_str(status_value: str) -> str:
    emoji = _STATUS_EMOJI.get(status_value, "")
    return f"{emoji} {status_value}"


def _short_id() -> str:
    """Generate a short 8-char hex ID."""
    return uuid.uuid4().hex[:8]


def _project_root() -> pathlib.Path:
    """Return the current working directory as project root."""
    return pathlib.Path.cwd()


def _pid_file() -> pathlib.Path:
    return _project_root() / ".maestro" / "maestro.pid"


def _config_path() -> pathlib.Path:
    return _project_root() / "maestro.yaml"


def _load_config():
    """Load config from the default maestro.yaml path, exiting on error."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config

    return load_config(config_file)


# ---------------------------------------------------------------------------
# Top-level group
# ---------------------------------------------------------------------------


@click.group()
def main() -> None:
    """Maestro - task orchestration daemon."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@main.command()
def init() -> None:
    """Initialize project (create maestro.yaml, .maestro/ dirs, init DB)."""
    root = _project_root()
    config_file = root / "maestro.yaml"
    example_file = root / "maestro.yaml.example"

    # 1. Create maestro.yaml
    if not config_file.exists():
        if example_file.exists():
            shutil.copy2(example_file, config_file)
            click.echo(f"Created {config_file} (copied from example)")
        else:
            # Write template config
            project_name = root.name
            config_file.write_text(
                _MAESTRO_YAML_TEMPLATE.format(project_name=project_name),
                encoding="utf-8",
            )
            click.echo(f"Created {config_file} (minimal)")
    else:
        click.echo(f"{config_file} already exists, skipping")

    # 2. Create .maestro/ directories
    dirs = [
        root / ".maestro" / "store",
        root / ".maestro" / "logs",
        root / ".maestro" / "worktrees",
        root / ".maestro" / "prompts",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"Directory ready: {d}")

    # 3. Init SQLite DB
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)
    asyncio.run(store.init_db())
    click.echo(f"Database initialized: {cfg.project.store_path}")

    # 4. Merge maestro MCP servers into .mcp.json (project root)
    mcp_json_path = root / ".mcp.json"
    if mcp_json_path.exists():
        try:
            mcp_data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            mcp_data = {}
    else:
        mcp_data = {}

    if "mcpServers" not in mcp_data:
        mcp_data["mcpServers"] = {}
    maestro_mcp = {
        "maestro-store": {
            "command": "python",
            "args": ["-m", "maestro.mcp_store"],
        },
        "maestro-embedding": {
            "command": "python",
            "args": ["-m", "maestro.mcp_embedding"],
        },
    }
    # Remove old incorrect "maestro" entry if present
    mcp_data["mcpServers"].pop("maestro", None)
    updated = False
    for name, server in maestro_mcp.items():
        if name not in mcp_data["mcpServers"]:
            mcp_data["mcpServers"][name] = server
            updated = True
    if updated:
        mcp_json_path.write_text(
            json.dumps(mcp_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        click.echo(f"MCP config merged: {mcp_json_path}")
    else:
        click.echo(f"MCP config already has maestro entries: {mcp_json_path}")

    # 5. Add .maestro/ to .gitignore (if git repo)
    is_git = (root / ".git").exists() or (root / ".git").is_file()
    if is_git:
        click.echo("Git repo detected.")
        gitignore = root / ".gitignore"
        marker = ".maestro/"
        needs_add = True
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if marker in content:
                needs_add = False
        if needs_add:
            with open(gitignore, "a", encoding="utf-8") as f:
                f.write(f"\n# Maestro working directory\n{marker}\n")
            click.echo(f"Added {marker} to .gitignore")

    click.echo("Maestro project initialized.")


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


@main.command()
@click.option("--port", default=0, type=int, help="Port for internal API (0 = auto)")
def start(port: int) -> None:
    """Start the Maestro daemon."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.daemon import Daemon
    from maestro.events import EventBus, EventEmittingStore
    from maestro.log import setup_logging

    cfg = load_config(config_file)
    setup_logging(cfg.logging)
    bus = EventBus()
    store = EventEmittingStore(cfg.project.store_path, bus)

    root = _project_root()
    daemon = Daemon(config=cfg, store=store, base_path=root)

    # Handle signals
    def _handle_signal(signum: int, frame: object) -> None:
        click.echo(f"\nReceived signal {signum}, stopping daemon...")
        daemon.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    click.echo(f"Starting Maestro daemon (port={port})...")

    async def _run() -> None:
        await store.init_db()
        await daemon.start(port=port)

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------


@main.command()
def stop() -> None:
    """Stop the Maestro daemon."""
    pid_file = _pid_file()
    if not pid_file.exists():
        click.echo("No PID file found. Daemon is not running.")
        return

    pid_str = pid_file.read_text().strip()
    try:
        pid = int(pid_str)
    except ValueError:
        click.echo(f"Invalid PID file contents: {pid_str!r}", err=True)
        sys.exit(1)

    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent SIGTERM to daemon (PID {pid}).")
    except ProcessLookupError:
        click.echo(f"Process {pid} not found. Removing stale PID file.")
        pid_file.unlink(missing_ok=True)
    except PermissionError:
        click.echo(f"Permission denied sending signal to PID {pid}.", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@main.command()
def status() -> None:
    """Show daemon status."""
    pid_file = _pid_file()
    if not pid_file.exists():
        click.echo("Maestro daemon is not running (no PID file).")
        return

    pid_str = pid_file.read_text().strip()
    try:
        pid = int(pid_str)
    except ValueError:
        click.echo(f"Invalid PID file: {pid_str!r}")
        return

    # Check if the process is alive
    try:
        os.kill(pid, 0)
        port_file = _project_root() / ".maestro" / "maestro.port"
        port_info = ""
        if port_file.exists():
            port_info = f", port {port_file.read_text().strip()}"
        click.echo(f"Maestro daemon is running (PID {pid}{port_info}).")
        if port_info:
            click.echo(f"Dashboard: http://127.0.0.1:{port_file.read_text().strip()}")
    except ProcessLookupError:
        click.echo(f"Maestro daemon is not running (stale PID file, PID {pid}).")
    except PermissionError:
        # Process exists but we can't signal it — still running
        click.echo(
            f"Maestro daemon is running (PID {pid},"
            " permission denied for signal check)."
        )


# ---------------------------------------------------------------------------
# task group
# ---------------------------------------------------------------------------


@main.group()
def task() -> None:
    """Manage tasks."""


@task.command("create")
@click.option(
    "--agent", default="default", help="Agent definition name (default: default)"
)
@click.option(
    "--no-worktree", is_flag=True, help="Run at project root instead of a git worktree"
)
@click.option(
    "--type", "task_type", required=True, help="Task type (e.g. shell, claude)"
)
@click.option("--title", required=True, help="Human-readable title")
@click.option("--instruction", required=True, help="Task instruction")
@click.option(
    "--approval-level", default=2, type=int, help="Approval level (0-2, default 2)"
)
@click.option(
    "--priority", default=3, type=int, help="Priority 1 (urgent) to 5 (low), default 3"
)
def task_create(
    agent: str,
    no_worktree: bool,
    task_type: str,
    title: str,
    instruction: str,
    approval_level: int,
    priority: int,
) -> None:
    """Create a new task."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    task_id = _short_id()
    new_task = Task(
        id=task_id,
        type=task_type,
        agent=agent,
        no_worktree=no_worktree,
        title=title,
        instruction=instruction,
        approval_level=approval_level,
        priority=priority,
    )

    asyncio.run(store.create_task(new_task))
    click.echo(f"Task created: {task_id}")
    click.echo(f"  Title: {title}")
    click.echo(f"  Status: {new_task.status.value}")


@task.command("list")
@click.option("--status", "filter_status", default=None, help="Filter by status")
@click.option("--agent", "filter_agent", default=None, help="Filter by agent")
@click.option("--flat", is_flag=True, help="Flat list without tree indentation")
@click.option(
    "--limit",
    "-L",
    "limit",
    default=20,
    type=int,
    help="Max number of tasks to show (default: 20)",
)
def task_list(filter_status, filter_agent, flat, limit):
    """List tasks."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    if limit <= 0:
        click.echo("Error: --limit must be a positive integer.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    async def _run():
        await store.init_db()
        ts = None
        if filter_status:
            try:
                ts = TaskStatus(filter_status)
            except ValueError:
                valid = ", ".join(s.value for s in TaskStatus)
                click.echo(f"Invalid status: {filter_status}. Valid: {valid}")
                return

        if flat:
            # Flat mode: use SQL LIMIT for efficiency
            tasks = await store.list_tasks(
                status=ts, agent=filter_agent, limit=limit + 1
            )

            if not tasks:
                click.echo("No tasks found.")
                return

            has_more = len(tasks) > limit
            display_tasks = tasks[:limit]

            for t in display_tasks:
                emoji = _STATUS_EMOJI.get(t.status.value, " ")
                click.echo(
                    f"{emoji} {t.id:<10} {t.status.value:<14}"
                    f" {t.priority:>3} {t.agent:<20} {t.title}"
                )

            if has_more:
                status_label = f" {filter_status}" if filter_status else ""
                click.echo(
                    f"\nShowing {limit}{status_label} tasks. Use --limit to show more."
                )
            return

        # Tree auto-detection: fetch all tasks
        all_tasks = await store.list_tasks(status=ts, agent=filter_agent)

        if not all_tasks:
            click.echo("No tasks found.")
            return

        has_tree = any(t.parent_task_id for t in all_tasks)

        if has_tree:
            # Tree mode: limit applies to root tasks
            task_map = {t.id: t for t in all_tasks}
            roots = [
                t
                for t in all_tasks
                if t.parent_task_id is None or t.parent_task_id not in task_map
            ]
            children_map: dict[str, list] = {}
            for t in all_tasks:
                if t.parent_task_id and t.parent_task_id in task_map:
                    children_map.setdefault(t.parent_task_id, []).append(t)

            total_roots = len(roots)
            display_roots = roots[:limit]

            def _effective_status(task):
                """부모가 completed이지만 자식 중 활성 태스크가 있으면 running으로 표시."""
                if task.status.value == "completed":
                    kids = children_map.get(task.id, [])
                    terminal = {"completed", "failed", "cancelled"}
                    if any(c.status.value not in terminal for c in kids):
                        return "running"
                return task.status.value

            def _print_tree(task, indent=""):
                display_status = _effective_status(task)
                emoji = _STATUS_EMOJI.get(display_status, " ")
                click.echo(
                    f"{indent}{emoji} {task.id:<10} {display_status:<14}"
                    f" {task.priority:>3} {task.agent:<20} {task.title}"
                )
                for child in children_map.get(task.id, []):
                    _print_tree(child, indent + "   ")

            for root in display_roots:
                _print_tree(root)

            if total_roots > limit:
                status_label = f" {filter_status}" if filter_status else ""
                click.echo(
                    f"\nShowing {limit} of {total_roots}{status_label} root tasks. Use --limit to show more."
                )
        else:
            # Flat mode: slice already-fetched data
            has_more = len(all_tasks) > limit
            display_tasks = all_tasks[:limit]

            for t in display_tasks:
                emoji = _STATUS_EMOJI.get(t.status.value, " ")
                click.echo(
                    f"{emoji} {t.id:<10} {t.status.value:<14}"
                    f" {t.priority:>3} {t.agent:<20} {t.title}"
                )

            if has_more:
                status_label = f" {filter_status}" if filter_status else ""
                click.echo(
                    f"\nShowing {limit}{status_label} tasks. Use --limit to show more."
                )

    asyncio.run(_run())


@task.command("get")
@click.argument("task_id")
@click.option("--full", is_flag=True, help="Show full result without truncation")
def task_get(task_id: str, full: bool) -> None:
    """Show details of a single task."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    async def _run():
        await store.init_db()
        t = await store.get_task(task_id)
        if t is None:
            click.echo(f"Task not found: {task_id}", err=True)
            raise SystemExit(1)

        click.echo(f"ID:             {t.id}")
        click.echo(f"Type:           {t.type}")
        click.echo(f"Agent:          {t.agent}")
        click.echo(f"No Worktree:    {t.no_worktree}")
        click.echo(f"Title:          {t.title}")
        click.echo(f"Instruction:    {t.instruction}")
        click.echo(f"Status:         {_status_str(t.status.value)}")
        click.echo(f"Priority:       {t.priority}")
        click.echo(f"Approval Level: {t.approval_level}")
        click.echo(f"Attempt:        {t.attempt + 1}/{t.max_retries}")
        if t.depends_on:
            try:
                dep_ids = json.loads(t.depends_on)
                click.echo(f"Depends On:     {', '.join(dep_ids)}")
            except (json.JSONDecodeError, TypeError):
                pass
        click.echo(f"Budget:         ${t.budget_usd:.2f}")
        click.echo(f"Cost:           ${t.cost_usd:.2f}")
        click.echo(f"Created:        {t.created_at}")
        if t.updated_at:
            click.echo(f"Updated:        {t.updated_at}")
        if t.session_id:
            click.echo(f"Session ID:     {t.session_id}")
        if t.error:
            click.echo(f"Error:          {t.error}")

        # Approval history
        approval = await store.get_approval_by_task(t.id)
        if approval:
            click.echo(f"Approval:       {approval['status']}")
            if approval.get("reviewer_note"):
                click.echo(f"Reviewer Note:  {approval['reviewer_note']}")
            if approval.get("reviewed_at"):
                click.echo(f"Reviewed At:    {approval['reviewed_at']}")

        # Review verdicts from children
        review_children = [
            c for c in await store.list_children(t.id) if c.type == "review"
        ]
        if review_children:
            click.echo("Reviews:")
            for rc in review_children:
                if rc.result:
                    from maestro.daemon import Daemon

                    parsed = Daemon._extract_json(rc.result)
                    if isinstance(parsed, dict):
                        verdict = parsed.get("verdict", "?")
                        summary = parsed.get("summary", "")
                        v_emoji = "✅" if verdict == "pass" else "🔄"
                        click.echo(f"  {v_emoji} {verdict}: {summary[:100]}")
                    else:
                        click.echo(f"  {_status_str(rc.status.value)}")

        # Parent
        if t.parent_task_id:
            parent = await store.get_task(t.parent_task_id)
            if parent:
                click.echo(f"Parent:         {parent.id} ({parent.title})")
            else:
                click.echo(f"Parent:         {t.parent_task_id}")

        # Children
        children = await store.list_children(t.id)
        if children:
            click.echo("Children:")
            for child in children:
                click.echo(
                    f"  └─ {child.id}  {_status_str(child.status.value):<20} "
                    f"{child.type:<12} {child.title}"
                )

        # Result
        if t.result is not None:
            result_str = str(t.result)
            if not full and len(result_str) > 500:
                click.echo(f"Result:         {result_str[:500]}...")
                click.echo(
                    "                (truncated, use --full for complete output)"
                )
            else:
                click.echo(f"Result:         {result_str}")

    asyncio.run(_run())


@task.command("tree")
@click.argument("task_id")
def task_tree(task_id: str) -> None:
    """Show full task tree from root."""
    config = _load_config()

    from maestro.store import Store

    store = Store(config.project.store_path)

    async def _run():
        await store.init_db()
        root_id = await store.find_root_task_id(task_id)
        tree_tasks = await store.get_task_tree(root_id)

        if not tree_tasks:
            click.echo(f"Task not found: {task_id}")
            return

        # Build children map
        children_map: dict[str, list] = {}
        for t in tree_tasks:
            if t.parent_task_id:
                children_map.setdefault(t.parent_task_id, []).append(t)

        total_cost = sum(t.cost_usd for t in tree_tasks)

        def _render(t, prefix="", is_last=True, is_root=True):
            connector = "" if is_root else ("└─ " if is_last else "├─ ")
            cost_str = f" (${t.cost_usd:.2f})" if t.cost_usd > 0 else ""
            emoji = _STATUS_EMOJI.get(t.status.value, "")
            click.echo(
                f"{prefix}{connector}{t.id} {emoji} {t.type:<12} {t.title}{cost_str}"
            )
            kids = children_map.get(t.id, [])
            for i, child in enumerate(kids):
                child_prefix = prefix + ("   " if (is_root or is_last) else "│  ")
                _render(child, child_prefix, i == len(kids) - 1, is_root=False)

        root = tree_tasks[0]
        _render(root)
        click.echo(f"\nTotal cost: ${total_cost:.2f}")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# approve / reject / revise
# ---------------------------------------------------------------------------


@main.command()
@click.argument("task_id")
@click.option("--note", default=None, help="Instructions for the agent when resuming")
def approve(task_id: str, note: str | None) -> None:
    """Approve a pending/paused task."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.approval import ApprovalManager
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    t = asyncio.run(store.get_task(task_id))
    if t is None:
        click.echo(f"Task not found: {task_id}", err=True)
        sys.exit(1)

    mgr = ApprovalManager(store)
    approval = asyncio.run(mgr.get_approval(task_id))

    if approval and approval["status"] == "pending":
        # Use ApprovalManager for tasks with approval records
        if note:
            asyncio.run(store.update_approval(approval["id"], reviewer_note=note))
        asyncio.run(mgr.approve(task_id))
        click.echo(f"Task {task_id}: Approved (approval {approval['id']})")
        if note:
            click.echo(f"  Note: {note}")
    else:
        # Direct status update for tasks without approval records (e.g. pending tasks)
        asyncio.run(store.update_task_status(task_id, TaskStatus.APPROVED))
        click.echo(f"Task {task_id}: Approved ({t.status.value} -> approved)")


@main.command()
@click.argument("task_id")
@click.option("--note", default=None, help="Rejection note")
def reject(task_id: str, note: str | None) -> None:
    """Reject a pending/paused task (set to CANCELLED)."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.approval import ApprovalManager
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    t = asyncio.run(store.get_task(task_id))
    if t is None:
        click.echo(f"Task not found: {task_id}", err=True)
        sys.exit(1)

    mgr = ApprovalManager(store)
    approval = asyncio.run(mgr.get_approval(task_id))

    if approval and approval["status"] == "pending":
        asyncio.run(mgr.reject(task_id, note=note))
        click.echo(f"Task {task_id}: Rejected (approval {approval['id']})")
    else:
        asyncio.run(store.update_task_status(task_id, TaskStatus.CANCELLED))
        click.echo(f"Task {task_id}: Rejected ({t.status.value} -> cancelled)")

    if note:
        click.echo(f"  Note: {note}")


@main.command()
@click.argument("task_id")
@click.option("--note", required=True, help="Reviewer note for revision")
@click.option("--content", default=None, help="Revised content to use")
def revise(task_id: str, note: str, content: str | None) -> None:
    """Revise a task (approve with reviewer note)."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.approval import ApprovalManager
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    t = asyncio.run(store.get_task(task_id))
    if t is None:
        click.echo(f"Task not found: {task_id}", err=True)
        sys.exit(1)

    mgr = ApprovalManager(store)
    approval = asyncio.run(mgr.get_approval(task_id))

    if approval and approval["status"] == "pending":
        asyncio.run(mgr.revise(task_id, note=note, revised_content=content))
        click.echo(f"Task {task_id} revised and approved (approval {approval['id']}).")
    else:
        # Fallback: direct update for tasks without approval records
        updated_instruction = f"{t.instruction}\n\n[Reviewer note]: {note}"

        async def _revise() -> None:
            await store.init_db()
            await store.update_task_fields(task_id, instruction=updated_instruction)
            await store.update_task_status(task_id, TaskStatus.APPROVED)

        asyncio.run(_revise())
        click.echo(f"Task {task_id} revised and approved.")

    click.echo(f"  Note: {note}")


@main.command()
def dashboard() -> None:
    """Show system dashboard summary."""
    config = _load_config()

    from maestro.store import Store

    store = Store(config.project.store_path)

    async def _run():
        await store.init_db()
        tasks = await store.list_tasks()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_spend = await store.get_daily_spend(today)
        running_count = await store.count_running()

        # Status counts
        status_counts: dict[str, int] = {}
        agent_stats: dict[str, dict] = {}
        for t in tasks:
            sv = t.status.value
            status_counts[sv] = status_counts.get(sv, 0) + 1
            if t.agent not in agent_stats:
                agent_stats[t.agent] = {"count": 0, "cost": 0.0}
            agent_stats[t.agent]["count"] += 1
            agent_stats[t.agent]["cost"] += t.cost_usd

        click.echo("📊 Maestro Dashboard")
        click.echo("─" * 40)

        # Tasks summary
        parts = []
        for s in [
            "completed",
            "running",
            "paused",
            "pending",
            "approved",
            "claimed",
            "retry_queued",
            "failed",
            "cancelled",
        ]:
            count = status_counts.get(s, 0)
            if count > 0:
                emoji = _STATUS_EMOJI.get(s, "")
                parts.append(f"{count} {emoji} {s}")
        click.echo(f"Tasks:      {', '.join(parts) if parts else 'none'}")

        # Budget
        limit = config.budget.daily_limit_usd
        pct = (daily_spend / limit * 100) if limit > 0 else 0
        click.echo(f"Budget:     ${daily_spend:.2f} / ${limit:.2f} ({pct:.1f}%)")

        # Agents
        max_agents = config.concurrency.max_total_agents
        click.echo(f"Agents:     {running_count}/{max_agents} active")

        # Agent stats
        if agent_stats:
            click.echo("Agents:")
            for ag, stats in sorted(agent_stats.items()):
                click.echo(f"  {ag:<20} {stats['count']} tasks, ${stats['cost']:.2f}")

    asyncio.run(_run())


@main.command()
def approvals() -> None:
    """List pending approvals with drafts."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.approval import ApprovalManager
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)
    mgr = ApprovalManager(store)

    pending = asyncio.run(mgr.get_pending_approvals())

    if not pending:
        click.echo("No pending approvals.")
        return

    click.echo(f"{'APPROVAL':<14} {'TASK':<10} {'STATUS':<10} {'TITLE'}")
    click.echo("-" * 60)
    for a in pending:
        click.echo(
            f"{a['id']:<14} {a['task_id']:<10} "
            f"{a.get('task_status', '?'):<10} {a.get('task_title', '?')}"
        )
        if a.get("draft_json"):
            draft_preview = a["draft_json"][:80]
            click.echo(f"  Draft: {draft_preview}...")


def _update_task_status(
    task_id: str, new_status: TaskStatus, action_label: str
) -> None:
    """Helper to load config, check task exists, and update status."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    t = asyncio.run(store.get_task(task_id))
    if t is None:
        click.echo(f"Task not found: {task_id}", err=True)
        sys.exit(1)

    asyncio.run(store.update_task_status(task_id, new_status))
    click.echo(
        f"Task {task_id}: {action_label} ({t.status.value} -> {new_status.value})"
    )


# ---------------------------------------------------------------------------
# Register task subgroup
# ---------------------------------------------------------------------------

main.add_command(task)


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------


@main.command()
@click.option("--all", "cleanup_all", is_flag=True, help="Force remove all worktrees")
def cleanup(cleanup_all: bool) -> None:
    """Clean up completed goal/task worktrees."""
    from maestro.worktree import WorktreeManager

    root = _project_root()
    wm = WorktreeManager(root)
    if not wm.is_git_repo():
        click.echo("Not a git repo, no worktrees to clean.")
        return
    worktrees = wm.list_worktrees()
    if not worktrees:
        click.echo("No worktrees found.")
        return
    for name in worktrees:
        if cleanup_all or not wm.has_changes(name):
            wm.remove_worktree(name)
            click.echo(f"Removed: {name}")
        else:
            click.echo(f"Skipped (has changes): {name}")


# ---------------------------------------------------------------------------
# asset group
# ---------------------------------------------------------------------------


@main.group()
def asset() -> None:
    """Manage assets."""


@asset.command("register")
@click.option("--title", required=True, help="Asset title")
@click.option(
    "--type",
    "asset_type",
    required=True,
    help="Asset type: post, engage, research, image, video, audio, document",
)
@click.option("--file", "file_path", type=click.Path(exists=True), help="Path to file")
@click.option(
    "--content", "content_json", default=None, help="JSON string for text content"
)
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option("--ttl-days", type=int, default=None, help="TTL in days")
@click.option("--permanent", is_flag=True, help="No expiry (ttl=null)")
@click.option("--description", default=None, help="Asset description")
def asset_register(
    title: str,
    asset_type: str,
    file_path: str | None,
    content_json: str | None,
    tags: str | None,
    ttl_days: int | None,
    permanent: bool,
    description: str | None,
) -> None:
    """Register a new asset."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.assets import AssetManager
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    # Parse content_json if provided
    parsed_content = None
    if content_json:
        try:
            parsed_content = json.loads(content_json)
        except json.JSONDecodeError as exc:
            click.echo(f"Error: invalid JSON in --content: {exc}", err=True)
            sys.exit(1)

    # Parse tags
    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    # permanent overrides ttl
    if permanent:
        ttl_days = None

    async def _run() -> None:
        await store.init_db()
        am = AssetManager(store, None, cfg, pathlib.Path(cfg.project.store_path).parent)
        a = await am.register_asset(
            asset_type=asset_type,
            title=title,
            content_json=parsed_content,
            file_path=file_path,
            tags=tag_list,
            description=description,
            ttl_days=ttl_days,
            created_by="human",
        )
        click.echo(f"Registered asset: {a['id']} — {a['title']}")

    asyncio.run(_run())


@asset.command("list")
@click.option("--type", "asset_type", default=None, help="Filter by asset_type")
@click.option("--tags", default=None, help="Filter by comma-separated tags")
@click.option(
    "--limit",
    "-L",
    "limit",
    default=20,
    type=int,
    help="Max number of assets to show (default: 20)",
)
def asset_list(asset_type: str | None, tags: str | None, limit: int) -> None:
    """List assets."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    if limit <= 0:
        click.echo("Error: --limit must be a positive integer.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    async def _run() -> None:
        await store.init_db()
        assets = await store.list_assets_filtered(
            asset_type=asset_type,
            tags=tag_list,
            limit=limit + 1,
        )
        if not assets:
            click.echo("No assets found.")
            return

        has_more = len(assets) > limit
        display_assets = assets[:limit]

        click.echo(f"{'ID':<14} {'TYPE':<12} {'CREATED_BY':<12} {'TITLE'}")
        click.echo("-" * 60)
        for a in display_assets:
            click.echo(
                f"{a['id']:<14} {a.get('asset_type', ''):<12}"
                f" {a.get('created_by', ''):<12}"
                f" {a.get('title', '')}"
            )

        if has_more:
            click.echo(f"\nShowing {limit} assets. Use --limit to show more.")

    asyncio.run(_run())


@asset.command("search")
@click.argument("query")
@click.option("--type", "asset_type", default=None, help="Filter by asset_type")
@click.option("--limit", "-L", default=10, type=int, help="Max results")
def asset_search_cmd(
    query: str,
    asset_type: str | None,
    limit: int,
) -> None:
    """Search assets semantically."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.assets import AssetManager
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    async def _run() -> None:
        await store.init_db()
        am = AssetManager(store, None, cfg, pathlib.Path(cfg.project.store_path).parent)
        results = await am.search(
            query=query,
            asset_type=asset_type,
            limit=limit,
        )
        if not results:
            click.echo("No assets found.")
            return
        for r in results:
            click.echo(
                f"  {r['id']}  [{r.get('asset_type', '')}]  {r.get('title', '')}"
            )

    asyncio.run(_run())


@asset.command("delete")
@click.argument("asset_id")
def asset_delete(asset_id: str) -> None:
    """Delete an asset permanently."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    async def _run() -> None:
        await store.init_db()
        a = await store.get_asset(asset_id)
        if a is None:
            click.echo(f"Asset not found: {asset_id}", err=True)
            raise SystemExit(1)
        await store.delete_asset(asset_id)
        click.echo(f"Deleted asset: {asset_id}")

    asyncio.run(_run())


@asset.command("archive")
@click.argument("asset_id")
def asset_archive(asset_id: str) -> None:
    """Soft-delete (archive) an asset."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    async def _run() -> None:
        await store.init_db()
        a = await store.get_asset(asset_id)
        if a is None:
            click.echo(f"Asset not found: {asset_id}", err=True)
            raise SystemExit(1)
        await store.update_asset(asset_id, archived=1)
        click.echo(f"Archived asset: {asset_id}")

    asyncio.run(_run())


@asset.command("cleanup")
@click.option(
    "--grace-days",
    default=30,
    type=int,
    help="Grace period before purging archives (default: 30)",
)
def asset_cleanup(grace_days: int) -> None:
    """Archive expired assets and purge old archives."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    async def _run() -> None:
        await store.init_db()
        archived = await store.archive_expired_assets()
        purged = await store.purge_archived_assets(grace_days=grace_days)
        click.echo(f"Archived {archived} expired asset(s).")
        click.echo(f"Purged {purged} old archived asset(s) (grace={grace_days}d).")

    asyncio.run(_run())


main.add_command(asset)


# ---------------------------------------------------------------------------
# schedule
# ---------------------------------------------------------------------------


@main.group()
def schedule():
    """Manage schedules."""
    pass


@schedule.command("add")
@click.option("--name", required=True, help="Unique schedule name")
@click.option(
    "--agent", default="default", help="Agent definition name (default: default)"
)
@click.option(
    "--no-worktree", is_flag=True, help="Run at project root instead of a git worktree"
)
@click.option("--type", "task_type", required=True, help="Task type to create")
@click.option("--cron", default=None, help='Cron expression (e.g. "0 9 * * *")')
@click.option(
    "--interval", "interval_ms", type=int, default=None, help="Interval in ms"
)
@click.option("--approval", "approval_level", type=int, default=0)
def schedule_add(
    name, agent, no_worktree, task_type, cron, interval_ms, approval_level
):
    """Add a new schedule."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.create_schedule(
            name=name,
            agent=agent,
            no_worktree=no_worktree,
            task_type=task_type,
            cron=cron,
            interval_ms=interval_ms,
            approval_level=approval_level,
        )
        click.echo(f"Created schedule: {name}")

    asyncio.run(_run())


@schedule.command("list")
def schedule_list():
    """List all schedules."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        schedules = await store.list_schedules()
        if not schedules:
            click.echo("No schedules.")
            return
        click.echo(
            f"{'NAME':<25} {'TYPE':<15} {'AGENT':<15} {'TRIGGER':<20} {'ENABLED'}"
        )
        click.echo("-" * 85)
        for s in schedules:
            trigger = s["cron"] or f"every {s['interval_ms']}ms"
            enabled = "✓" if s["enabled"] else "✗"
            click.echo(
                f"{s['name']:<25} {s['task_type']:<15} {s.get('agent', 'default'):<15} {trigger:<20} {enabled}"
            )

    asyncio.run(_run())


@schedule.command("remove")
@click.argument("name")
def schedule_remove(name):
    """Remove a schedule."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.delete_schedule(name)
        click.echo(f"Removed schedule: {name}")

    asyncio.run(_run())


@schedule.command("enable")
@click.argument("name")
def schedule_enable(name):
    """Enable a schedule."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.update_schedule(name, enabled=True)
        click.echo(f"Enabled: {name}")

    asyncio.run(_run())


@schedule.command("disable")
@click.argument("name")
def schedule_disable(name):
    """Disable a schedule."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.update_schedule(name, enabled=False)
        click.echo(f"Disabled: {name}")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# goal
# ---------------------------------------------------------------------------


@main.group()
def goal():
    """Manage goals."""
    pass


@goal.command("add")
@click.option("--id", "goal_id", required=True, help="Unique goal ID")
@click.option(
    "--no-worktree", is_flag=True, help="Run at project root instead of a git worktree"
)
@click.option("--description", default="", help="Goal description")
@click.option("--metrics", default="{}", help="Metrics JSON")
@click.option(
    "--cooldown", "cooldown_hours", type=int, default=24, help="Cooldown hours"
)
def goal_add(goal_id, no_worktree, description, metrics, cooldown_hours):
    """Add a new goal."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.create_goal(
            id=goal_id,
            no_worktree=no_worktree,
            description=description,
            metrics=metrics,
            cooldown_hours=cooldown_hours,
        )
        click.echo(f"Created goal: {goal_id}")

    asyncio.run(_run())


@goal.command("list")
def goal_list():
    """List all goals."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        goals = await store.list_goals()
        if not goals:
            click.echo("No goals.")
            return
        click.echo(f"{'ID':<25} {'COOLDOWN':<10} {'ENABLED':<9} {'LAST EVALUATED'}")
        click.echo("-" * 70)
        for g in goals:
            enabled = "✓" if g["enabled"] else "✗"
            last_eval = g.get("last_evaluated_at") or "—"
            if last_eval != "—":
                last_eval = last_eval[:19]
            click.echo(
                f"{g['id']:<25} {g['cooldown_hours']:<10} {enabled:<9} {last_eval}"
            )

    asyncio.run(_run())


@goal.command("show")
@click.argument("goal_id")
def goal_show(goal_id):
    """Show goal details including state."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        g = await store.get_goal(goal_id)
        if not g:
            click.echo(f"Goal not found: {goal_id}")
            return
        click.echo(f"ID:                 {g['id']}")
        click.echo(f"Description:        {g['description']}")
        click.echo(f"No Worktree:        {g.get('no_worktree', False)}")
        click.echo(f"Metrics:            {g['metrics']}")
        click.echo(f"Cooldown:           {g['cooldown_hours']}h")
        click.echo(f"Enabled:            {'✓' if g['enabled'] else '✗'}")
        click.echo(f"Last Evaluated:     {g.get('last_evaluated_at') or '—'}")
        click.echo(f"Current Gap:        {g.get('current_gap') or '—'}")
        click.echo(f"Last Task Created:  {g.get('last_task_created_at') or '—'}")

    asyncio.run(_run())


@goal.command("enable")
@click.argument("goal_id")
def goal_enable(goal_id):
    """Enable a goal."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.update_goal(goal_id, enabled=True)
        click.echo(f"Enabled: {goal_id}")

    asyncio.run(_run())


@goal.command("disable")
@click.argument("goal_id")
def goal_disable(goal_id):
    """Disable a goal."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.update_goal(goal_id, enabled=False)
        click.echo(f"Disabled: {goal_id}")

    asyncio.run(_run())


@goal.command("edit")
@click.argument("goal_id")
@click.option("--description", default=None, help="New description")
@click.option("--metrics", default=None, help="New metrics JSON")
@click.option(
    "--cooldown", "cooldown_hours", type=int, default=None, help="New cooldown hours"
)
def goal_edit(goal_id, description, metrics, cooldown_hours):
    """Edit an existing goal."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        g = await store.get_goal(goal_id)
        if not g:
            click.echo(f"Goal not found: {goal_id}", err=True)
            raise SystemExit(1)
        fields = {}
        if description is not None:
            fields["description"] = description
        if metrics is not None:
            fields["metrics"] = metrics
        if cooldown_hours is not None:
            fields["cooldown_hours"] = cooldown_hours
        if not fields:
            click.echo(
                "Nothing to update. Use --description, --metrics, or --cooldown."
            )
            return
        await store.update_goal(goal_id, **fields)
        click.echo(f"Updated goal: {goal_id}")

    asyncio.run(_run())


@goal.command("remove")
@click.argument("goal_id")
def goal_remove(goal_id):
    """Remove a goal."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.delete_goal(goal_id)
        click.echo(f"Removed goal: {goal_id}")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# extract-rule
# ---------------------------------------------------------------------------


@main.group("extract-rule")
def extract_rule():
    """Manage auto-extract rules."""
    pass


@extract_rule.command("add")
@click.option("--task-type", required=True)
@click.option("--asset-type", required=True)
@click.option("--title-field", default=None)
@click.option("--iterate", default=None)
@click.option("--tags-from", default=None, help="Comma-separated dot-paths")
def rule_add(task_type, asset_type, title_field, iterate, tags_from):
    """Add or update an auto-extract rule."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        tf = [t.strip() for t in tags_from.split(",")] if tags_from else None
        await store.create_extract_rule(
            task_type=task_type,
            asset_type=asset_type,
            title_field=title_field,
            iterate=iterate,
            tags_from=tf,
        )
        click.echo(f"Rule set: {task_type} -> {asset_type}")

    asyncio.run(_run())


@extract_rule.command("list")
def rule_list():
    """List auto-extract rules."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        rules = await store.list_extract_rules()
        if not rules:
            click.echo("No rules.")
            return
        click.echo(f"{'TASK_TYPE':<15} {'ASSET_TYPE':<10} {'TITLE_FIELD':<20}")
        click.echo("-" * 50)
        for r in rules:
            click.echo(
                f"{r['task_type']:<15} {r['asset_type']:<10} {r.get('title_field') or '':<20}"
            )

    asyncio.run(_run())


@extract_rule.command("remove")
@click.option("--task-type", required=True)
def rule_remove(task_type):
    """Remove an auto-extract rule."""

    async def _run():
        config = _load_config()
        from maestro.store import Store

        store = Store(config.project.store_path)
        await store.init_db()
        await store.delete_extract_rule(task_type)
        click.echo(f"Removed rule: {task_type}")

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# slack group
# ---------------------------------------------------------------------------


@main.group()
def slack() -> None:
    """Configure Slack integration."""


@slack.command("setup")
def slack_setup() -> None:
    """Interactive Slack setup wizard."""
    root = _project_root()
    project_name = root.name

    # 1. Show Slack App Manifest JSON
    manifest = {
        "display_information": {
            "name": f"Maestro ({project_name})",
            "description": "AI orchestration assistant",
            "background_color": "#1a1a2e",
        },
        "features": {
            "bot_user": {
                "display_name": f"Maestro ({project_name})",
                "always_online": True,
            }
        },
        "oauth_config": {
            "scopes": {
                "bot": [
                    "app_mentions:read",
                    "chat:write",
                    "im:history",
                    "im:read",
                    "im:write",
                    "reactions:read",
                    "reactions:write",
                    "channels:history",
                    "groups:history",
                    "users:read",
                ]
            }
        },
        "settings": {
            "event_subscriptions": {"bot_events": ["app_mention", "message.im"]},
            "interactivity": {"is_enabled": True},
            "socket_mode_enabled": True,
        },
    }

    click.echo("=== Slack App Manifest ===")
    click.echo(json.dumps(manifest, indent=2, ensure_ascii=False))
    click.echo("")
    click.echo(
        "1. Go to https://api.slack.com/apps and create a new app 'From an app manifest'."
    )
    click.echo("2. Paste the manifest above, then install the app to your workspace.")
    click.echo("")

    # 2. Prompt for Bot Token
    bot_token = click.prompt("Bot Token (xoxb-...)", hide_input=True)
    if not bot_token.startswith("xoxb-"):
        click.echo("Error: Bot Token must start with 'xoxb-'.", err=True)
        sys.exit(1)

    # Prompt for App Token
    app_token = click.prompt("App Token (xapp-...)", hide_input=True)
    if not app_token.startswith("xapp-"):
        click.echo("Error: App Token must start with 'xapp-'.", err=True)
        sys.exit(1)

    # 3. Prompt for channel
    channel = click.prompt("Slack channel", default="#maestro-ops")

    # 4. Save tokens to .maestro/secrets.yaml
    secrets_dir = root / ".maestro"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    secrets_path = secrets_dir / "secrets.yaml"

    secrets_content = (
        f'slack:\n  bot_token: "{bot_token}"\n  app_token: "{app_token}"\n'
    )
    secrets_path.write_text(secrets_content, encoding="utf-8")
    click.echo(f"  Tokens saved to {secrets_path}")

    # 5. Update maestro.yaml integrations.slack section
    config_file = _config_path()
    if config_file.exists():
        content = config_file.read_text(encoding="utf-8")
        slack_block = (
            f'\nintegrations:\n  slack:\n    enabled: true\n    channel: "{channel}"\n'
        )
        if "integrations:" in content:
            # Replace existing integrations.slack block if present
            import re

            # Update or insert slack sub-section under integrations
            if "slack:" in content:
                # Replace the enabled and channel lines under slack:
                content = re.sub(
                    r"(integrations:\s*\n(?:[ \t]+\S[^\n]*\n)*?[ \t]+slack:\s*\n)"
                    r"((?:[ \t]+[^\n]+\n)*)",
                    lambda m: (
                        m.group(1) + f'    enabled: true\n    channel: "{channel}"\n'
                    ),
                    content,
                )
            else:
                # Append slack section under integrations:
                content = re.sub(
                    r"(integrations:\s*\n)",
                    r"\1" + f'  slack:\n    enabled: true\n    channel: "{channel}"\n',
                    content,
                )
        else:
            content += slack_block
        config_file.write_text(content, encoding="utf-8")
        click.echo("  maestro.yaml updated with Slack integration settings")
    else:
        click.echo(
            "  Warning: maestro.yaml not found. Run 'maestro init' to create it."
        )

    # 6. Ensure .gitignore has .maestro/secrets.yaml
    gitignore = root / ".gitignore"
    secrets_marker = ".maestro/secrets.yaml"
    needs_add = True
    if gitignore.exists():
        gi_content = gitignore.read_text(encoding="utf-8")
        if secrets_marker in gi_content:
            needs_add = False
    if needs_add:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write(f"\n# Maestro secrets\n{secrets_marker}\n")
        click.echo(f"  Added {secrets_marker} to .gitignore")

    # 7. Connection test
    click.echo("\nTesting Slack connection...")
    try:
        from slack_sdk.web.async_client import AsyncWebClient

        async def _test():
            client = AsyncWebClient(token=bot_token)
            await client.chat_postMessage(
                channel=channel,
                text=f"👋 Maestro ({project_name}) Slack 연동 완료!",
            )

        asyncio.run(_test())
        click.echo(f"  ✅ 연결 성공 — {channel}에 테스트 메시지를 확인하세요")
    except ImportError:
        click.echo("  ⚠️  slack-sdk가 설치되지 않았습니다. pip install 'maestro[slack]'")
    except Exception as exc:
        click.echo(f"  ❌ 연결 실패: {exc}", err=True)

    click.echo("\nSlack setup complete.")


@slack.command("status")
def slack_status() -> None:
    """Show current Slack integration status."""
    root = _project_root()
    config_file = _config_path()

    # Load maestro.yaml to get integration settings
    enabled = False
    channel = None
    if config_file.exists():
        try:
            import re

            content = config_file.read_text(encoding="utf-8")
            enabled_match = re.search(
                r"integrations:\s*\n(?:[ \t]+\S[^\n]*\n)*?[ \t]+slack:\s*\n"
                r"(?:[ \t]+[^\n]*\n)*?[ \t]+enabled:\s*(true|false)",
                content,
            )
            if enabled_match:
                enabled = enabled_match.group(1).lower() == "true"
            channel_match = re.search(
                r"integrations:\s*\n(?:[ \t]+\S[^\n]*\n)*?[ \t]+slack:\s*\n"
                r"(?:[ \t]+[^\n]*\n)*?[ \t]+channel:\s*[\"']?([^\s\"'\n]+)[\"']?",
                content,
            )
            if channel_match:
                channel = channel_match.group(1)
        except OSError:
            pass

    # Check token presence in secrets.yaml
    secrets_path = root / ".maestro" / "secrets.yaml"
    bot_token_configured = False
    app_token_configured = False
    if secrets_path.exists():
        try:
            secrets_content = secrets_path.read_text(encoding="utf-8")
            bot_token_configured = (
                "bot_token:" in secrets_content and "xoxb-" in secrets_content
            )
            app_token_configured = (
                "app_token:" in secrets_content and "xapp-" in secrets_content
            )
        except OSError:
            pass

    click.echo("=== Slack Integration Status ===")
    click.echo(f"Enabled:   {'yes' if enabled else 'no'}")
    click.echo(f"Bot Token: {'configured' if bot_token_configured else 'missing'}")
    click.echo(f"App Token: {'configured' if app_token_configured else 'missing'}")
    click.echo(f"Channel:   {channel if channel else '(not set)'}")


if __name__ == "__main__":
    main()
