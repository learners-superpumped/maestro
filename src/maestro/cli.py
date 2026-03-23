"""Maestro CLI entry point."""

from __future__ import annotations

import asyncio
import os
import pathlib
import signal
import shutil
import sys
import uuid
from datetime import datetime, timezone

import click

from maestro.models import Task, TaskStatus


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
        click.echo(f"Maestro daemon is running (PID {pid}, permission denied for signal check).")


# ---------------------------------------------------------------------------
# task group
# ---------------------------------------------------------------------------


@main.group()
def task() -> None:
    """Manage tasks."""


@task.command("create")
@click.option("--workspace", required=True, help="Target workspace name")
@click.option("--type", "task_type", required=True, help="Task type (e.g. shell, claude)")
@click.option("--title", required=True, help="Human-readable title")
@click.option("--instruction", required=True, help="Task instruction")
@click.option("--approval-level", default=2, type=int, help="Approval level (0-2, default 2)")
@click.option("--priority", default=3, type=int, help="Priority 1 (urgent) to 5 (low), default 3")
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
@click.option("--status", "status_filter", default=None, help="Filter by status")
def task_list(status_filter: str | None) -> None:
    """List tasks."""
    config_file = _config_path()
    if not config_file.exists():
        click.echo("Error: maestro.yaml not found. Run 'maestro init' first.", err=True)
        sys.exit(1)

    from maestro.config import load_config
    from maestro.store import Store

    cfg = load_config(config_file)
    store = Store(cfg.project.store_path)

    ts = None
    if status_filter:
        try:
            ts = TaskStatus(status_filter)
        except ValueError:
            valid = ", ".join(s.value for s in TaskStatus)
            click.echo(f"Invalid status: {status_filter!r}. Valid: {valid}", err=True)
            sys.exit(1)

    tasks = asyncio.run(store.list_tasks(status=ts))

    if not tasks:
        click.echo("No tasks found.")
        return

    # Table header
    click.echo(f"{'ID':<10} {'STATUS':<14} {'PRI':>3} {'WORKSPACE':<20} {'TITLE'}")
    click.echo("-" * 70)
    for t in tasks:
        click.echo(f"{t.id:<10} {t.status.value:<14} {t.priority:>3} {t.workspace:<20} {t.title}")


@task.command("get")
@click.argument("task_id")
def task_get(task_id: str) -> None:
    """Show task details."""
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

    click.echo(f"ID:             {t.id}")
    click.echo(f"Type:           {t.type}")
    click.echo(f"Workspace:      {t.workspace}")
    click.echo(f"Title:          {t.title}")
    click.echo(f"Instruction:    {t.instruction}")
    click.echo(f"Status:         {t.status.value}")
    click.echo(f"Priority:       {t.priority}")
    click.echo(f"Approval Level: {t.approval_level}")
    click.echo(f"Attempt:        {t.attempt}/{t.max_retries}")
    click.echo(f"Budget:         ${t.budget_usd:.2f}")
    click.echo(f"Cost:           ${t.cost_usd:.2f}")
    click.echo(f"Created:        {t.created_at.isoformat()}")
    click.echo(f"Updated:        {t.updated_at.isoformat()}")
    if t.session_id:
        click.echo(f"Session ID:     {t.session_id}")
    if t.error:
        click.echo(f"Error:          {t.error}")
    if t.result_json:
        click.echo(f"Result:         {t.result_json}")


# ---------------------------------------------------------------------------
# approve / reject / revise
# ---------------------------------------------------------------------------


@main.command()
@click.argument("task_id")
def approve(task_id: str) -> None:
    """Approve a pending task."""
    _update_task_status(task_id, TaskStatus.APPROVED, "Approved")


@main.command()
@click.argument("task_id")
def reject(task_id: str) -> None:
    """Reject a pending task (set to CANCELLED)."""
    _update_task_status(task_id, TaskStatus.CANCELLED, "Rejected")


@main.command()
@click.argument("task_id")
@click.option("--note", required=True, help="Reviewer note for revision")
def revise(task_id: str, note: str) -> None:
    """Revise a task (approve with reviewer note)."""
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

    # Append reviewer note to instruction
    updated_instruction = f"{t.instruction}\n\n[Reviewer note]: {note}"

    async def _revise() -> None:
        async with store._conn() as db:
            await db.execute(
                "UPDATE tasks SET instruction = ?, updated_at = ? WHERE id = ?",
                (updated_instruction, datetime.now(timezone.utc).isoformat(), task_id),
            )
            await db.commit()
        await store.update_task_status(task_id, TaskStatus.APPROVED)

    asyncio.run(_revise())
    click.echo(f"Task {task_id} revised and approved.")
    click.echo(f"  Note: {note}")


def _update_task_status(task_id: str, new_status: TaskStatus, action_label: str) -> None:
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
    click.echo(f"Task {task_id}: {action_label} ({t.status.value} -> {new_status.value})")


# ---------------------------------------------------------------------------
# Register task subgroup
# ---------------------------------------------------------------------------

main.add_command(task)


if __name__ == "__main__":
    main()
