"""Tests for maestro.store — SQLite persistence layer."""

from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timezone

import aiosqlite
import pytest

from maestro.models import Task, TaskStatus
from maestro.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> Task:
    """Create a minimal Task with sensible defaults."""
    defaults = dict(
        id=str(uuid.uuid4()),
        type="shell",
        workspace="/tmp/ws",
        title="Test task",
        instruction="echo hello",
    )
    defaults.update(kwargs)
    return Task(**defaults)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

async def test_schema_applies_cleanly(db_path: pathlib.Path) -> None:
    """All expected tables must exist after init_db()."""
    expected_tables = {
        "tasks",
        "assets",
        "task_assets",
        "action_history",
        "approvals",
        "budget_daily",
        "goal_state",
        "notifications",
    }
    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        rows = await cursor.fetchall()
    found = {row[0] for row in rows}
    assert expected_tables <= found, f"Missing tables: {expected_tables - found}"


# ---------------------------------------------------------------------------
# create_task / get_task
# ---------------------------------------------------------------------------

async def test_create_and_get_task(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    task = _task(title="Create test", instruction="ls -la")

    await store.create_task(task)
    fetched = await store.get_task(task.id)

    assert fetched is not None
    assert fetched.id == task.id
    assert fetched.title == task.title
    assert fetched.instruction == task.instruction
    assert fetched.status == TaskStatus.PENDING
    assert fetched.workspace == task.workspace
    assert fetched.type == task.type


async def test_get_nonexistent_returns_none(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    result = await store.get_task("does-not-exist")
    assert result is None


# ---------------------------------------------------------------------------
# update_task_status
# ---------------------------------------------------------------------------

async def test_update_task_status(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    task = _task()
    await store.create_task(task)

    await store.update_task_status(task.id, TaskStatus.APPROVED)

    fetched = await store.get_task(task.id)
    assert fetched is not None
    assert fetched.status == TaskStatus.APPROVED


async def test_update_task_status_with_extra_fields(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    task = _task()
    await store.create_task(task)

    now_str = datetime.now(timezone.utc).isoformat()
    await store.update_task_status(
        task.id,
        TaskStatus.RUNNING,
        started_at=now_str,
        session_id="sess-abc",
    )

    fetched = await store.get_task(task.id)
    assert fetched is not None
    assert fetched.status == TaskStatus.RUNNING
    assert fetched.session_id == "sess-abc"
    assert fetched.started_at is not None


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

async def test_list_tasks_by_status(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    pending1 = _task(title="Pending 1")
    pending2 = _task(title="Pending 2")
    approved = _task(title="Approved", status=TaskStatus.APPROVED)

    for t in (pending1, pending2, approved):
        await store.create_task(t)

    pending_list = await store.list_tasks(status=TaskStatus.PENDING)
    assert len(pending_list) == 2
    ids = {t.id for t in pending_list}
    assert pending1.id in ids
    assert pending2.id in ids

    approved_list = await store.list_tasks(status=TaskStatus.APPROVED)
    assert len(approved_list) == 1
    assert approved_list[0].id == approved.id


async def test_list_tasks_by_workspace(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    t1 = _task(workspace="/ws/alpha")
    t2 = _task(workspace="/ws/alpha")
    t3 = _task(workspace="/ws/beta")

    for t in (t1, t2, t3):
        await store.create_task(t)

    alpha = await store.list_tasks(workspace="/ws/alpha")
    assert len(alpha) == 2

    beta = await store.list_tasks(workspace="/ws/beta")
    assert len(beta) == 1


async def test_list_tasks_no_filter(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    for _ in range(3):
        await store.create_task(_task())
    all_tasks = await store.list_tasks()
    assert len(all_tasks) == 3


# ---------------------------------------------------------------------------
# list_dispatchable_tasks
# ---------------------------------------------------------------------------

async def test_list_dispatchable_tasks_priority_order(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    low = _task(title="Low priority", status=TaskStatus.APPROVED, priority=5)
    high = _task(title="High priority", status=TaskStatus.APPROVED, priority=1)
    mid = _task(title="Mid priority", status=TaskStatus.APPROVED, priority=3)
    pending = _task(title="Still pending", status=TaskStatus.PENDING, priority=1)

    for t in (low, high, mid, pending):
        await store.create_task(t)

    dispatchable = await store.list_dispatchable_tasks()

    # Pending task must not appear
    ids = [t.id for t in dispatchable]
    assert pending.id not in ids

    # All three approved tasks present
    assert len(dispatchable) == 3

    # Ordered by priority ASC (1 first, 5 last)
    assert dispatchable[0].id == high.id
    assert dispatchable[1].id == mid.id
    assert dispatchable[2].id == low.id


async def test_list_dispatchable_excludes_future_scheduled(db_path: pathlib.Path) -> None:
    """Tasks with a future scheduled_at must not be dispatched."""
    store = Store(db_path)

    future_ts = "2099-01-01T00:00:00+00:00"
    future_task = _task(status=TaskStatus.APPROVED, scheduled_at=datetime(2099, 1, 1, tzinfo=timezone.utc))
    now_task = _task(status=TaskStatus.APPROVED)

    for t in (future_task, now_task):
        await store.create_task(t)

    dispatchable = await store.list_dispatchable_tasks()
    ids = [t.id for t in dispatchable]
    assert now_task.id in ids
    assert future_task.id not in ids


# ---------------------------------------------------------------------------
# count_running
# ---------------------------------------------------------------------------

async def test_count_running(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    r1 = _task(workspace="/ws/a", status=TaskStatus.RUNNING)
    r2 = _task(workspace="/ws/a", status=TaskStatus.CLAIMED)
    r3 = _task(workspace="/ws/b", status=TaskStatus.RUNNING)
    pending = _task(workspace="/ws/a", status=TaskStatus.PENDING)

    for t in (r1, r2, r3, pending):
        await store.create_task(t)

    assert await store.count_running() == 3
    assert await store.count_running(workspace="/ws/a") == 2
    assert await store.count_running(workspace="/ws/b") == 1
    assert await store.count_running(workspace="/ws/c") == 0


# ---------------------------------------------------------------------------
# budget_daily
# ---------------------------------------------------------------------------

async def test_get_daily_spend_empty(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    spend = await store.get_daily_spend("2026-03-23")
    assert spend == 0.0


async def test_record_spend_accumulation(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    date = "2026-03-23"

    await store.record_spend(date, 1.50)
    assert await store.get_daily_spend(date) == pytest.approx(1.50)

    await store.record_spend(date, 2.25)
    assert await store.get_daily_spend(date) == pytest.approx(3.75)

    # Different date is independent
    await store.record_spend("2026-03-24", 0.10)
    assert await store.get_daily_spend(date) == pytest.approx(3.75)
    assert await store.get_daily_spend("2026-03-24") == pytest.approx(0.10)
