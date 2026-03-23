"""Tests for the Maestro Daemon."""

from __future__ import annotations

import pathlib

import pytest

from maestro.config import (
    AgentConfig,
    BudgetConfig,
    ConcurrencyConfig,
    DaemonConfig,
    LoggingConfig,
    MaestroConfig,
    ProjectConfig,
)
from maestro.daemon import Daemon
from maestro.models import Task, TaskResult, TaskStatus
from maestro.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> MaestroConfig:
    return MaestroConfig(
        project=ProjectConfig(name="test"),
        daemon=DaemonConfig(),
        concurrency=ConcurrencyConfig(),
        budget=BudgetConfig(),
        agent=AgentConfig(),
        logging=LoggingConfig(),
    )


def _make_task(
    task_id: str = "t1",
    approval_level: int = 0,
    status: TaskStatus = TaskStatus.PENDING,
) -> Task:
    return Task(
        id=task_id,
        type="claude",
        workspace="ws1",
        title="Test task",
        instruction="Do something",
        status=status,
        approval_level=approval_level,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_approve_level0(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A pending task with approval_level=0 should be auto-approved."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="auto-0", approval_level=0)
    await store.create_task(task)

    await daemon._auto_approve_pending()

    updated = await store.get_task("auto-0")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED


@pytest.mark.asyncio
async def test_auto_approve_level1(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A pending task with approval_level=1 should also be auto-approved."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="auto-1", approval_level=1)
    await store.create_task(task)

    await daemon._auto_approve_pending()

    updated = await store.get_task("auto-1")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED


@pytest.mark.asyncio
async def test_no_auto_approve_level2(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A pending task with approval_level=2 must NOT be auto-approved."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="manual-2", approval_level=2)
    await store.create_task(task)

    await daemon._auto_approve_pending()

    updated = await store.get_task("manual-2")
    assert updated is not None
    assert updated.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_handle_result_success(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A successful TaskResult should transition the task to COMPLETED."""
    from maestro.models import TaskResult

    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="ok-1", status=TaskStatus.RUNNING)
    # Need to insert as PENDING then transition through states in DB
    pending_task = _make_task(task_id="ok-1", status=TaskStatus.PENDING, approval_level=0)
    await store.create_task(pending_task)
    await store.update_task_status("ok-1", TaskStatus.APPROVED)
    await store.update_task_status("ok-1", TaskStatus.CLAIMED)
    await store.update_task_status("ok-1", TaskStatus.RUNNING)

    result = TaskResult(
        task_id="ok-1",
        success=True,
        session_id="sess-abc",
        cost_usd=0.05,
    )

    # Use the in-memory task object with RUNNING status
    task.status = TaskStatus.RUNNING
    await daemon._handle_result(task, result)

    updated = await store.get_task("ok-1")
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.session_id == "sess-abc"
    assert updated.cost_usd == 0.05


@pytest.mark.asyncio
async def test_handle_result_failure_retries(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A failed TaskResult with retries remaining should queue a retry."""
    from maestro.models import TaskResult

    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # Create task with attempt=0, max_retries=3
    pending_task = _make_task(task_id="retry-1", status=TaskStatus.PENDING, approval_level=0)
    await store.create_task(pending_task)
    await store.update_task_status("retry-1", TaskStatus.APPROVED)
    await store.update_task_status("retry-1", TaskStatus.CLAIMED)
    await store.update_task_status("retry-1", TaskStatus.RUNNING)

    task = _make_task(task_id="retry-1", status=TaskStatus.RUNNING)
    task.attempt = 0
    task.max_retries = 3

    result = TaskResult(
        task_id="retry-1",
        success=False,
        error="Something went wrong",
    )

    await daemon._handle_result(task, result)

    updated = await store.get_task("retry-1")
    assert updated is not None
    assert updated.status == TaskStatus.RETRY_QUEUED
    assert updated.attempt == 1
    assert updated.error == "Something went wrong"


@pytest.mark.asyncio
async def test_handle_result_failure_no_retries(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """A failed TaskResult with no retries left should mark FAILED."""
    from maestro.models import TaskResult

    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    pending_task = _make_task(task_id="fail-1", status=TaskStatus.PENDING, approval_level=0)
    await store.create_task(pending_task)
    await store.update_task_status("fail-1", TaskStatus.APPROVED)
    await store.update_task_status("fail-1", TaskStatus.CLAIMED)
    await store.update_task_status("fail-1", TaskStatus.RUNNING)

    task = _make_task(task_id="fail-1", status=TaskStatus.RUNNING)
    task.attempt = 2
    task.max_retries = 3  # attempt + 1 == max_retries → no retry

    result = TaskResult(
        task_id="fail-1",
        success=False,
        error="Permanent failure",
    )

    await daemon._handle_result(task, result)

    updated = await store.get_task("fail-1")
    assert updated is not None
    assert updated.status == TaskStatus.FAILED
    assert updated.error == "Permanent failure"


@pytest.mark.asyncio
async def test_stop_sets_shutdown(tmp_path: pathlib.Path, db_path: pathlib.Path) -> None:
    """Calling stop() should set the shutdown event."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    assert not daemon._shutdown.is_set()
    daemon.stop()
    assert daemon._shutdown.is_set()


@pytest.mark.asyncio
async def test_resume_approved_paused_task(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    """An approved task with session_id should be picked up for resume."""
    store = Store(db_path)
    config = _make_config()

    # Create workspace dir
    ws_dir = tmp_path / "workspaces" / "ws1"
    ws_dir.mkdir(parents=True)

    daemon = Daemon(config, store, tmp_path)

    # Create task in PENDING state, advance to APPROVED, then set session_id
    task = _make_task(task_id="resume-1", approval_level=2, status=TaskStatus.PENDING)
    await store.create_task(task)

    # Simulate: task ran, got paused, then approved with a session_id
    await store.update_task_status("resume-1", TaskStatus.APPROVED)
    await store.update_task_status("resume-1", TaskStatus.CLAIMED)
    await store.update_task_status("resume-1", TaskStatus.RUNNING, session_id="sess-resume-123")
    await store.update_task_status("resume-1", TaskStatus.PAUSED)

    # Create an approval record
    await store.create_approval({
        "id": "appr-resume-1",
        "task_id": "resume-1",
        "status": "pending",
        "draft_json": '{"content": "draft"}',
    })

    # Now approve it
    from maestro.approval import ApprovalManager
    mgr = ApprovalManager(store)
    await mgr.approve("resume-1")

    # Verify task is APPROVED with session_id
    t = await store.get_task("resume-1")
    assert t is not None
    assert t.status == TaskStatus.APPROVED
    assert t.session_id == "sess-resume-123"

    # Call _resume_approved_tasks — it should claim the task and spawn a resume
    # We mock the runner to avoid actually running CLI
    from unittest.mock import AsyncMock
    daemon._runner.resume = AsyncMock(return_value=TaskResult(
        task_id="resume-1",
        success=True,
        session_id="sess-resume-123",
        cost_usd=0.01,
    ))

    await daemon._resume_approved_tasks()

    # Task should be claimed (resume was spawned)
    t = await store.get_task("resume-1")
    assert t is not None
    assert t.status == TaskStatus.CLAIMED

    # Wait for the spawned asyncio task to complete
    if "resume-1" in daemon._running_procs:
        await daemon._running_procs["resume-1"]

    # Now it should be completed
    t = await store.get_task("resume-1")
    assert t is not None
    assert t.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_handle_result_level1_sends_notification(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A completed Level 1 task should create a notification."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # Create a level-1 task
    pending_task = _make_task(task_id="lvl1-1", approval_level=1, status=TaskStatus.PENDING)
    pending_task.title = "Level 1 Task"
    await store.create_task(pending_task)
    await store.update_task_status("lvl1-1", TaskStatus.APPROVED)
    await store.update_task_status("lvl1-1", TaskStatus.CLAIMED)
    await store.update_task_status("lvl1-1", TaskStatus.RUNNING)

    task = _make_task(task_id="lvl1-1", approval_level=1, status=TaskStatus.RUNNING)
    task.title = "Level 1 Task"

    result = TaskResult(
        task_id="lvl1-1",
        success=True,
        cost_usd=0.02,
    )

    await daemon._handle_result(task, result)

    updated = await store.get_task("lvl1-1")
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED

    # Check notification was created
    notifications = await store.list_notifications()
    assert len(notifications) == 1
    assert notifications[0]["type"] == "task_completed"
    assert "Level 1 Task" in notifications[0]["message"]


# ---------------------------------------------------------------------------
# _extract_json tests
# ---------------------------------------------------------------------------


def test_extract_json_raw_list():
    result = Daemon._extract_json([{"a": 1}])
    assert result == [{"a": 1}]


def test_extract_json_string():
    result = Daemon._extract_json('[{"a": 1}]')
    assert result == [{"a": 1}]


def test_extract_json_markdown_wrapped():
    text = '```json\n[{"a": 1}]\n```'
    result = Daemon._extract_json(text)
    assert result == [{"a": 1}]


def test_extract_json_invalid():
    result = Daemon._extract_json("not json")
    assert result is None
