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
from maestro.models import Task, TaskStatus
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
