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
        "asset_usage",
        "action_history",
        "approvals",
        "budget_daily",
        "goals",
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
    assert fetched.agent == task.agent
    assert fetched.no_worktree == task.no_worktree
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


async def test_list_tasks_by_agent(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    t1 = _task(agent="agent-alpha")
    t2 = _task(agent="agent-alpha")
    t3 = _task(agent="agent-beta")

    for t in (t1, t2, t3):
        await store.create_task(t)

    alpha = await store.list_tasks(agent="agent-alpha")
    assert len(alpha) == 2

    beta = await store.list_tasks(agent="agent-beta")
    assert len(beta) == 1


async def test_list_tasks_by_goal_id(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    t1 = _task(goal_id="goal-1")
    t2 = _task(goal_id="goal-1")
    t3 = _task(goal_id="goal-2")

    for t in (t1, t2, t3):
        await store.create_task(t)

    g1 = await store.list_tasks(goal_id="goal-1")
    assert len(g1) == 2

    g2 = await store.list_tasks(goal_id="goal-2")
    assert len(g2) == 1


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


async def test_list_dispatchable_excludes_future_scheduled(
    db_path: pathlib.Path,
) -> None:
    """Tasks with a future scheduled_at must not be dispatched."""
    store = Store(db_path)

    future_ts = "2099-01-01T00:00:00+00:00"
    future_task = _task(
        status=TaskStatus.APPROVED,
        scheduled_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
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

    r1 = _task(goal_id="goal-a", status=TaskStatus.RUNNING)
    r2 = _task(goal_id="goal-a", status=TaskStatus.CLAIMED)
    r3 = _task(goal_id="goal-b", status=TaskStatus.RUNNING)
    pending = _task(goal_id="goal-a", status=TaskStatus.PENDING)

    for t in (r1, r2, r3, pending):
        await store.create_task(t)

    assert await store.count_running() == 3
    assert await store.count_running(goal_id="goal-a") == 2
    assert await store.count_running(goal_id="goal-b") == 1
    assert await store.count_running(goal_id="goal-c") == 0


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


# ---------------------------------------------------------------------------
# Asset CRUD
# ---------------------------------------------------------------------------


def _asset(**kwargs) -> dict:
    """Create a minimal asset dict with sensible defaults."""
    defaults = dict(
        id=str(uuid.uuid4()),
        asset_type="image",
        title="Test Asset",
        description="A test image",
        tags=["test", "image"],
    )
    defaults.update(kwargs)
    return defaults


async def test_create_and_get_asset(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    asset = _asset()

    await store.create_asset(asset)
    fetched = await store.get_asset(asset["id"])

    assert fetched is not None
    assert fetched["id"] == asset["id"]
    assert fetched["title"] == asset["title"]
    assert fetched["asset_type"] == asset["asset_type"]
    assert fetched["created_by"] == "human"
    assert fetched["tags"] == ["test", "image"]


async def test_get_nonexistent_asset_returns_none(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    result = await store.get_asset("does-not-exist")
    assert result is None


async def test_list_assets_by_type(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    img = _asset(asset_type="image", title="Image")
    vid = _asset(asset_type="video", title="Video")
    doc = _asset(asset_type="document", title="Doc")

    for a in (img, vid, doc):
        await store.create_asset(a)

    images = await store.list_assets(asset_type="image")
    assert len(images) == 1
    assert images[0]["title"] == "Image"

    videos = await store.list_assets(asset_type="video")
    assert len(videos) == 1
    assert videos[0]["title"] == "Video"

    all_assets = await store.list_assets()
    assert len(all_assets) == 3


async def test_list_assets_by_tags(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    a1 = _asset(tags=["promo", "summer"], title="Summer Promo")
    a2 = _asset(tags=["promo", "winter"], title="Winter Promo")
    a3 = _asset(tags=["internal"], title="Internal Doc")

    for a in (a1, a2, a3):
        await store.create_asset(a)

    promo = await store.list_assets(tags_contain=["promo"])
    assert len(promo) == 2

    winter = await store.list_assets(tags_contain=["winter"])
    assert len(winter) == 1
    assert winter[0]["title"] == "Winter Promo"

    none_found = await store.list_assets(tags_contain=["nonexistent"])
    assert len(none_found) == 0


async def test_update_asset(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    asset = _asset()
    await store.create_asset(asset)

    await store.update_asset(asset["id"], title="Updated Title", tags=["new"])

    fetched = await store.get_asset(asset["id"])
    assert fetched is not None
    assert fetched["title"] == "Updated Title"
    assert fetched["tags"] == ["new"]


# ---------------------------------------------------------------------------
# Action History
# ---------------------------------------------------------------------------


def _action(**kwargs) -> dict:
    """Create a minimal action dict."""
    defaults = dict(
        id=str(uuid.uuid4()),
        task_id="task-001",
        action_type="post",
        platform="twitter",
    )
    defaults.update(kwargs)
    return defaults


async def test_record_action(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    # Need a task for FK constraint
    task = _task(id="task-001")
    await store.create_task(task)

    action = _action(content="Hello world", asset_ids=["a1", "a2"])
    await store.record_action(action)

    history = await store.search_history()
    assert len(history) == 1
    assert history[0]["action_type"] == "post"
    assert history[0]["platform"] == "twitter"
    assert history[0]["asset_ids"] == ["a1", "a2"]


async def test_search_history(db_path: pathlib.Path) -> None:
    store = Store(db_path)

    # Create tasks for FK
    task_a = _task(id="task-a")
    task_b = _task(id="task-b")
    await store.create_task(task_a)
    await store.create_task(task_b)

    a1 = _action(task_id="task-a", platform="twitter")
    a2 = _action(task_id="task-b", platform="instagram")
    a3 = _action(task_id="task-a", platform="facebook")

    for a in (a1, a2, a3):
        await store.record_action(a)

    # Limit
    limited = await store.search_history(limit=1)
    assert len(limited) == 1

    # All
    all_actions = await store.search_history()
    assert len(all_actions) == 3


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


async def test_get_goal_none(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    result = await store.get_goal("nonexistent")
    assert result is None


async def test_create_goal(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    goal = await store.create_goal(id="g1", description="Test goal", cooldown_hours=12)
    assert goal is not None
    assert goal["id"] == "g1"
    assert goal["description"] == "Test goal"
    assert goal["cooldown_hours"] == 12
    assert goal["enabled"] == 1
    assert goal["created_at"] is not None
    assert goal["updated_at"] is not None


async def test_list_goals(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    await store.create_goal(id="g1")
    await store.create_goal(id="g2", description="Second")

    all_goals = await store.list_goals()
    assert len(all_goals) == 2
    assert all_goals[0]["id"] == "g1"
    assert all_goals[1]["id"] == "g2"


async def test_list_goals_enabled_only(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    await store.create_goal(id="g1")
    await store.create_goal(id="g2")
    await store.update_goal("g2", enabled=False)

    enabled = await store.list_goals(enabled_only=True)
    assert len(enabled) == 1
    assert enabled[0]["id"] == "g1"


async def test_update_goal(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    await store.create_goal(id="g1", description="old")
    await store.update_goal("g1", description="new", current_gap="some gap")

    goal = await store.get_goal("g1")
    assert goal is not None
    assert goal["description"] == "new"
    assert goal["current_gap"] == "some gap"


async def test_delete_goal(db_path: pathlib.Path) -> None:
    store = Store(db_path)
    await store.create_goal(id="g1")
    await store.delete_goal("g1")

    result = await store.get_goal("g1")
    assert result is None


# ---------------------------------------------------------------------------
# Schema Migration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migration_drops_old_assets(tmp_path):
    db_file = str(tmp_path / "test.db")
    store = Store(db_file)
    await store.init_db()
    async with store._conn() as db:
        cursor = await db.execute("PRAGMA table_info(assets)")
        columns = {row[1] for row in await cursor.fetchall()}
        assert "created_by" in columns
        assert "content_json" in columns
        assert "file_path" in columns
        assert "ttl_days" in columns
        assert "archived" in columns
        assert "path" not in columns
        assert "platforms_published" not in columns
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='task_assets'"
        )
        assert await cursor.fetchone() is None
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='asset_usage'"
        )
        assert await cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_assets_vec_table_created(tmp_path):
    import sqlite3

    if not hasattr(sqlite3.connect(":memory:"), "enable_load_extension"):
        pytest.skip("sqlite3 built without extension loading support")

    db_file = str(tmp_path / "test.db")
    store = Store(db_file)
    await store.init_db()
    async with store._conn() as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE name='assets_vec'"
        )
        assert await cursor.fetchone() is not None


@pytest.mark.asyncio
async def test_delete_asset(db_path) -> None:
    store = Store(db_path)
    asset = {
        "id": "del-test-01",
        "asset_type": "document",
        "title": "To Delete",
        "created_by": "test",
    }
    await store.create_asset(asset)
    assert await store.get_asset("del-test-01") is not None
    await store.delete_asset("del-test-01")
    assert await store.get_asset("del-test-01") is None


@pytest.mark.asyncio
async def test_update_task_fields(db_path) -> None:
    store = Store(db_path)
    task = Task(id="utf-01", type="test", title="Original", instruction="do it")
    await store.create_task(task)
    await store.update_task_fields("utf-01", instruction="updated instruction")
    t = await store.get_task("utf-01")
    assert t.instruction == "updated instruction"
