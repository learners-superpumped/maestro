"""Maestro CLI entry point."""

from __future__ import annotations

import asyncio
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
def task_list(filter_status, filter_workspace, flat):
    """List tasks."""
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
        ts = None
        if filter_status:
            try:
                ts = TaskStatus(filter_status)
            except ValueError:
                valid = ", ".join(s.value for s in TaskStatus)
                click.echo(f"Invalid status: {filter_status}. Valid: {valid}")
                return

        tasks = await store.list_tasks(status=ts, workspace=filter_workspace)

        if not tasks:
            click.echo("No tasks found.")
            return

        if flat or not any(t.parent_task_id for t in tasks):
            # Flat output
            for t in tasks:
                emoji = _STATUS_EMOJI.get(t.status.value, " ")
                click.echo(
                    f"{emoji} {t.id:<10} {t.status.value:<14}"
                    f" {t.priority:>3} {t.workspace:<20} {t.title}"
                )
        else:
            # Tree output
            task_map = {t.id: t for t in tasks}
            roots = [t for t in tasks
                     if t.parent_task_id is None
                     or t.parent_task_id not in task_map]
            children_map: dict[str, list] = {}
            for t in tasks:
                if t.parent_task_id and t.parent_task_id in task_map:
                    children_map.setdefault(t.parent_task_id, []).append(t)

            def _print_tree(task, indent=""):
                emoji = _STATUS_EMOJI.get(task.status.value, " ")
                click.echo(
                    f"{indent}{emoji} {task.id:<10} {task.status.value:<14}"
                    f" {task.priority:>3} {task.workspace:<20} {task.title}"
                )
                for child in children_map.get(task.id, []):
                    _print_tree(child, indent + "   ")

            for root in roots:
                _print_tree(root)

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
def approve(task_id: str) -> None:
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
        asyncio.run(mgr.approve(task_id))
        click.echo(f"Task {task_id}: Approved (approval {approval['id']})")
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


@asset.command("add")
@click.argument("path")
@click.option("--title", required=True, help="Asset title")
@click.option("--tags", default=None, help="Comma-separated tags")
@click.option(
    "--type", "asset_type", default=None, help="Asset type (auto-detected if omitted)"
)
@click.option("--description", default=None, help="Asset description")
def asset_add(
    path: str,
    title: str,
    tags: str | None,
    asset_type: str | None,
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
    mgr = AssetManager(store, _project_root() / "assets")

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    asset_id = asyncio.run(
        mgr.register_asset(
            path=path,
            title=title,
            asset_type=asset_type,
            tags=tag_list,
            description=description,
        )
    )
    click.echo(f"Asset registered: {asset_id}")
    click.echo(f"  Title: {title}")
    click.echo(f"  Path:  {path}")


@asset.command("list")
@click.option("--type", "asset_type", default=None, help="Filter by type")
@click.option("--tags", default=None, help="Filter by comma-separated tags")
def asset_list(asset_type: str | None, tags: str | None) -> None:
    """List assets."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.assets import AssetManager
    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)
    mgr = AssetManager(store, _project_root() / "assets")

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    assets = asyncio.run(mgr.list_assets(asset_type=asset_type, tags=tag_list))

    if not assets:
        click.echo("No assets found.")
        return

    click.echo(f"{'ID':<14} {'TYPE':<10} {'TITLE':<30} {'TAGS'}")
    click.echo("-" * 70)
    for a in assets:
        tag_str = ", ".join(a.get("tags") or [])
        click.echo(f"{a['id']:<14} {a['type']:<10} {a['title']:<30} {tag_str}")


@asset.command("search")
@click.argument("query")
@click.option("--type", "asset_type", default=None, help="Filter by type")
@click.option("--limit", default=10, type=int, help="Max results")
def asset_search(query: str, asset_type: str | None, limit: int) -> None:
    """Search assets by text query."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    # Simple text search — same logic as mcp_embedding
    async def _search() -> list[dict]:
        all_assets = await store.list_assets(asset_type=asset_type)
        query_lower = query.lower()
        matches = []
        for a in all_assets:
            title = (a.get("title") or "").lower()
            desc = (a.get("description") or "").lower()
            tag_text = " ".join(a.get("tags") or []).lower()
            if query_lower in title or query_lower in desc or query_lower in tag_text:
                matches.append(a)
            if len(matches) >= limit:
                break
        return matches

    results = asyncio.run(_search())

    if not results:
        click.echo(f"No assets matching '{query}'.")
        return

    click.echo(f"{'ID':<14} {'TYPE':<10} {'TITLE':<30} {'TAGS'}")
    click.echo("-" * 70)
    for a in results:
        tag_str = ", ".join(a.get("tags") or [])
        click.echo(f"{a['id']:<14} {a['type']:<10} {a['title']:<30} {tag_str}")


main.add_command(asset)


if __name__ == "__main__":
    main()
