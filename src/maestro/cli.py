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
from maestro.workspace import WorkspaceManager


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
    return _project_root() / "store" / "maestro.pid"


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
    """Initialize project (create maestro.yaml, dirs, init DB)."""
    root = _project_root()
    config_file = root / "maestro.yaml"
    example_file = root / "maestro.yaml.example"

    # 1. Create maestro.yaml
    if not config_file.exists():
        if example_file.exists():
            shutil.copy2(example_file, config_file)
            click.echo(f"Created {config_file} (copied from example)")
        else:
            # Write a minimal config
            config_file.write_text(
                'project:\n  name: "my-project"\n  store_path: ./store/maestro.db\n',
                encoding="utf-8",
            )
            click.echo(f"Created {config_file} (minimal)")
    else:
        click.echo(f"{config_file} already exists, skipping")

    # 2. Create directories
    dirs = [
        root / "store",
        root / "workspaces" / "_base" / "knowledge",
        root / "logs",
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
    from maestro.log import setup_logging
    from maestro.store import Store

    cfg = load_config(config_file)
    setup_logging(cfg.logging)
    store = Store(cfg.project.store_path)

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
        click.echo(f"Maestro daemon is running (PID {pid}).")
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
@click.option("--workspace", required=True, help="Target workspace name")
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
    workspace: str,
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
        workspace=workspace,
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
@click.option("--workspace", "filter_workspace", default=None, help="Filter by workspace")
@click.option("--flat", is_flag=True, help="Flat list without tree indentation")
@click.option("--limit", "-L", "limit", default=20, type=int, help="Max number of tasks to show (default: 20)")
def task_list(filter_status, filter_workspace, flat, limit):
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

        # Fetch limit+1 to detect if there are more results
        tasks = await store.list_tasks(status=ts, workspace=filter_workspace, limit=limit + 1)

        if not tasks:
            click.echo("No tasks found.")
            return

        has_more = len(tasks) > limit
        display_tasks = tasks[:limit]

        for t in display_tasks:
            emoji = _STATUS_EMOJI.get(t.status.value, " ")
            click.echo(
                f"{emoji} {t.id:<10} {t.status.value:<14}"
                f" {t.priority:>3} {t.workspace:<20} {t.title}"
            )

        if has_more:
            status_label = f" {filter_status}" if filter_status else ""
            click.echo(f"\nShowing {limit}{status_label} tasks. Use --limit to show more.")

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
        click.echo(f"Workspace:      {t.workspace}")
        click.echo(f"Title:          {t.title}")
        click.echo(f"Instruction:    {t.instruction}")
        click.echo(f"Status:         {_status_str(t.status.value)}")
        click.echo(f"Priority:       {t.priority}")
        click.echo(f"Approval Level: {t.approval_level}")
        click.echo(f"Attempt:        {t.attempt}/{t.max_retries}")
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
        review_children = [c for c in await store.list_children(t.id) if c.type == "review"]
        if review_children:
            click.echo("Reviews:")
            for rc in review_children:
                if rc.result_json:
                    from maestro.daemon import Daemon
                    parsed = Daemon._extract_json(rc.result_json)
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
        if t.result_json is not None:
            result_str = str(t.result_json)
            if not full and len(result_str) > 500:
                click.echo(f"Result:         {result_str[:500]}...")
                click.echo("                (truncated, use --full for complete output)")
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
                f"{prefix}{connector}{t.id} {emoji} {t.type:<12} "
                f"{t.title}{cost_str}"
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
            async with store._conn() as db:
                await db.execute(
                    "UPDATE tasks SET instruction = ?, updated_at = ? WHERE id = ?",
                    (
                        updated_instruction,
                        datetime.now(timezone.utc).isoformat(),
                        task_id,
                    ),
                )
                await db.commit()
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
        from datetime import datetime, timezone
        tasks = await store.list_tasks()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_spend = await store.get_daily_spend(today)
        running_count = await store.count_running()

        # Status counts
        status_counts: dict[str, int] = {}
        ws_stats: dict[str, dict] = {}
        for t in tasks:
            sv = t.status.value
            status_counts[sv] = status_counts.get(sv, 0) + 1
            if t.workspace not in ws_stats:
                ws_stats[t.workspace] = {"count": 0, "cost": 0.0}
            ws_stats[t.workspace]["count"] += 1
            ws_stats[t.workspace]["cost"] += t.cost_usd

        click.echo("📊 Maestro Dashboard")
        click.echo("─" * 40)

        # Tasks summary
        parts = []
        for s in ["completed", "running", "paused", "pending", "approved",
                   "claimed", "retry_queued", "failed", "cancelled"]:
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

        # Workspaces
        if ws_stats:
            click.echo("Workspaces:")
            for ws, stats in sorted(ws_stats.items()):
                click.echo(f"  {ws:<20} {stats['count']} tasks, ${stats['cost']:.2f}")

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
# workspace group
# ---------------------------------------------------------------------------


@main.group()
def workspace() -> None:
    """Manage workspaces."""


@workspace.command("create")
@click.argument("name")
@click.option(
    "--template",
    default="default",
    type=click.Choice(WorkspaceManager.available_templates(), case_sensitive=False),
    help="Template to use (default: default)",
)
def workspace_create(name: str, template: str) -> None:
    """Create a new workspace."""
    root = _project_root()
    wm = WorkspaceManager(root)
    wm.ensure_base_knowledge()

    try:
        ws_path = wm.create_workspace(name, template=template)
    except FileExistsError:
        click.echo(f"Error: workspace '{name}' already exists.", err=True)
        sys.exit(1)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    click.echo(f"Workspace created: {ws_path}")
    click.echo(f"  Template: {template}")
    warnings = wm.validate_workspace(name)
    if warnings:
        for w in warnings:
            click.echo(f"  Warning: {w}")
    else:
        click.echo("  Status: valid")


@workspace.command("list")
def workspace_list() -> None:
    """List workspaces."""
    root = _project_root()
    wm = WorkspaceManager(root)
    names = wm.list_workspaces()

    if not names:
        click.echo("No workspaces found.")
        return

    click.echo(f"{'WORKSPACE':<30} {'STATUS'}")
    click.echo("-" * 45)
    for name in names:
        warnings = wm.validate_workspace(name)
        status = "valid" if not warnings else f"{len(warnings)} warning(s)"
        click.echo(f"{name:<30} {status}")


@workspace.command("validate")
@click.argument("name")
def workspace_validate(name: str) -> None:
    """Validate a workspace."""
    root = _project_root()
    wm = WorkspaceManager(root)

    if not wm.workspace_exists(name):
        click.echo(f"Error: workspace '{name}' does not exist.", err=True)
        sys.exit(1)

    warnings = wm.validate_workspace(name)
    if warnings:
        click.echo(f"Workspace '{name}' has {len(warnings)} warning(s):")
        for w in warnings:
            click.echo(f"  - {w}")
    else:
        click.echo(f"Workspace '{name}' is valid.")


main.add_command(workspace)


# ---------------------------------------------------------------------------
# asset group
# ---------------------------------------------------------------------------


@main.group()
def asset() -> None:
    """Manage assets."""


@asset.command("register")
@click.option("--title", required=True, help="Asset title")
@click.option(
    "--type", "asset_type", required=True,
    help="Asset type: post, engage, research, image, video, audio, document",
)
@click.option("--file", "file_path", type=click.Path(exists=True), help="Path to file")
@click.option("--content", "content_json", default=None, help="JSON string for text content")
@click.option("--workspace", default=None, help="Workspace (default: _shared)")
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option("--ttl-days", type=int, default=None, help="TTL in days")
@click.option("--permanent", is_flag=True, help="No expiry (ttl=null)")
@click.option("--description", default=None, help="Asset description")
def asset_register(
    title: str,
    asset_type: str,
    file_path: str | None,
    content_json: str | None,
    workspace: str | None,
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

    # workspace default
    if not workspace:
        workspace = "_shared"

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
            workspace=workspace,
            created_by="human",
        )
        click.echo(f"Registered asset: {a['id']} — {a['title']}")

    asyncio.run(_run())


@asset.command("list")
@click.option("--type", "asset_type", default=None, help="Filter by asset_type")
@click.option("--workspace", default=None, help="Filter by workspace")
@click.option("--tags", default=None, help="Filter by comma-separated tags")
def asset_list(asset_type: str | None, workspace: str | None, tags: str | None) -> None:
    """List assets."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
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
            workspace=workspace,
            tags=tag_list,
            limit=200,
        )
        if not assets:
            click.echo("No assets found.")
            return

        click.echo(f"{'ID':<14} {'TYPE':<12} {'WORKSPACE':<16} {'CREATED_BY':<12} {'TITLE'}")
        click.echo("-" * 80)
        for a in assets:
            click.echo(
                f"{a['id']:<14} {a.get('asset_type', ''):<12}"
                f" {a.get('workspace', ''):<16} {a.get('created_by', ''):<12}"
                f" {a.get('title', '')}"
            )

    asyncio.run(_run())


@asset.command("search")
@click.argument("query")
@click.option("--workspace", default=None, help="Filter by workspace")
@click.option("--type", "asset_type", default=None, help="Filter by asset_type")
@click.option("--limit", default=10, type=int, help="Max results")
def asset_search_cmd(
    query: str,
    workspace: str | None,
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
            workspace=workspace,
            asset_type=asset_type,
            limit=limit,
        )
        if not results:
            click.echo("No assets found.")
            return
        for r in results:
            click.echo(f"  {r['id']}  [{r.get('asset_type', '')}]  {r.get('title', '')}")

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
        async with store._conn() as db:
            await db.execute("DELETE FROM assets_vec WHERE asset_id = ?", (asset_id,))
            await db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            await db.commit()
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
@click.option("--grace-days", default=30, type=int, help="Grace period before purging archives (default: 30)")
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
@click.option("--workspace", required=True)
@click.option("--type", "task_type", required=True, help="Task type to create")
@click.option("--cron", default=None, help='Cron expression (e.g. "0 9 * * *")')
@click.option("--interval", "interval_ms", type=int, default=None, help="Interval in ms")
@click.option("--approval", "approval_level", type=int, default=0)
def schedule_add(name, workspace, task_type, cron, interval_ms, approval_level):
    """Add a new schedule."""
    async def _run():
        config = _load_config()
        from maestro.store import Store
        store = Store(config.project.store_path)
        await store.init_db()
        await store.create_schedule(
            name=name, workspace=workspace, task_type=task_type,
            cron=cron, interval_ms=interval_ms, approval_level=approval_level,
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
        click.echo(f"{'NAME':<25} {'TYPE':<15} {'WORKSPACE':<15} {'TRIGGER':<20} {'ENABLED'}")
        click.echo("-" * 85)
        for s in schedules:
            trigger = s["cron"] or f"every {s['interval_ms']}ms"
            enabled = "✓" if s["enabled"] else "✗"
            click.echo(f"{s['name']:<25} {s['task_type']:<15} {s['workspace']:<15} {trigger:<20} {enabled}")
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
# extract-rule
# ---------------------------------------------------------------------------

@main.group("extract-rule")
def extract_rule():
    """Manage auto-extract rules."""
    pass

@extract_rule.command("add")
@click.option("--workspace", required=True)
@click.option("--task-type", required=True)
@click.option("--asset-type", required=True)
@click.option("--title-field", default=None)
@click.option("--iterate", default=None)
@click.option("--tags-from", default=None, help="Comma-separated dot-paths")
def rule_add(workspace, task_type, asset_type, title_field, iterate, tags_from):
    """Add or update an auto-extract rule."""
    async def _run():
        config = _load_config()
        from maestro.store import Store
        store = Store(config.project.store_path)
        await store.init_db()
        tf = [t.strip() for t in tags_from.split(",")] if tags_from else None
        await store.create_extract_rule(
            workspace=workspace, task_type=task_type, asset_type=asset_type,
            title_field=title_field, iterate=iterate, tags_from=tf,
        )
        click.echo(f"Rule set: {workspace}/{task_type} → {asset_type}")
    asyncio.run(_run())

@extract_rule.command("list")
@click.option("--workspace", default=None)
def rule_list(workspace):
    """List auto-extract rules."""
    async def _run():
        config = _load_config()
        from maestro.store import Store
        store = Store(config.project.store_path)
        await store.init_db()
        rules = await store.list_extract_rules(workspace=workspace)
        if not rules:
            click.echo("No rules.")
            return
        click.echo(f"{'WORKSPACE':<20} {'TASK_TYPE':<15} {'ASSET_TYPE':<10} {'TITLE_FIELD':<20}")
        click.echo("-" * 70)
        for r in rules:
            click.echo(f"{r['workspace']:<20} {r['task_type']:<15} {r['asset_type']:<10} {r.get('title_field') or '':<20}")
    asyncio.run(_run())

@extract_rule.command("remove")
@click.option("--workspace", required=True)
@click.option("--task-type", required=True)
def rule_remove(workspace, task_type):
    """Remove an auto-extract rule."""
    async def _run():
        config = _load_config()
        from maestro.store import Store
        store = Store(config.project.store_path)
        await store.init_db()
        await store.delete_extract_rule(workspace, task_type)
        click.echo(f"Removed rule: {workspace}/{task_type}")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
