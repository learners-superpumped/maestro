"""Tests for maestro.reconciler."""

from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from maestro.models import Task, TaskStatus
from maestro.reconciler import Reconciler
from maestro.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _task(**kwargs) -> Task:
    """Create a minimal RUNNING Task with sensible defaults."""
    defaults = dict(
        id=str(uuid.uuid4()),
        type="shell",
        workspace="/tmp/ws",
        title="Test task",
        instruction="echo hello",
        status=TaskStatus.RUNNING,
        attempt=0,
        max_retries=3,
    )
    defaults.update(kwargs)
    return Task(**defaults)


def _reconciler(tasks: list[Task] | None = None) -> tuple[Reconciler, AsyncMock]:
    """Return a Reconciler with a mocked Store pre-loaded with *tasks*."""
    store = MagicMock(spec=Store)
    store.list_tasks = AsyncMock(return_value=tasks or [])
    store.update_task_status = AsyncMock()
    rec = Reconciler(store=store, stall_timeout_ms=30_000)
    return rec, store


# ---------------------------------------------------------------------------
# find_timed_out_tasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_timed_out_tasks_returns_expired_task() -> None:
    """A RUNNING task whose timeout_at is in the past should be detected."""
    expired = _task(timeout_at=_now() - timedelta(seconds=10))
    rec, _ = _reconciler(tasks=[expired])

    result = await rec.find_timed_out_tasks()

    assert len(result) == 1
    assert result[0].id == expired.id


@pytest.mark.asyncio
async def test_find_timed_out_tasks_ignores_future_timeout() -> None:
    """A RUNNING task whose timeout_at is in the future must NOT be returned."""
    active = _task(timeout_at=_now() + timedelta(seconds=60))
    rec, _ = _reconciler(tasks=[active])

    result = await rec.find_timed_out_tasks()

    assert result == []


@pytest.mark.asyncio
async def test_find_timed_out_tasks_ignores_task_without_timeout() -> None:
    """A RUNNING task with no timeout_at set must NOT be returned."""
    no_timeout = _task(timeout_at=None)
    rec, _ = _reconciler(tasks=[no_timeout])

    result = await rec.find_timed_out_tasks()

    assert result == []


@pytest.mark.asyncio
async def test_find_timed_out_tasks_mixed_list() -> None:
    """Only the expired task among a mixed list should be returned."""
    expired = _task(timeout_at=_now() - timedelta(seconds=5))
    active = _task(timeout_at=_now() + timedelta(seconds=120))
    no_timeout = _task(timeout_at=None)
    rec, _ = _reconciler(tasks=[expired, active, no_timeout])

    result = await rec.find_timed_out_tasks()

    assert len(result) == 1
    assert result[0].id == expired.id


# ---------------------------------------------------------------------------
# should_retry
# ---------------------------------------------------------------------------

def test_should_retry_when_attempts_remaining() -> None:
    """should_retry returns True when attempt < max_retries."""
    task = _task(attempt=1, max_retries=3)
    rec, _ = _reconciler()

    assert rec.should_retry(task) is True


def test_should_retry_first_attempt() -> None:
    """should_retry returns True on the very first failure (attempt=0)."""
    task = _task(attempt=0, max_retries=3)
    rec, _ = _reconciler()

    assert rec.should_retry(task) is True


def test_should_not_retry_when_exhausted() -> None:
    """should_retry returns False when attempt >= max_retries."""
    task = _task(attempt=3, max_retries=3)
    rec, _ = _reconciler()

    assert rec.should_retry(task) is False


def test_should_not_retry_when_over_limit() -> None:
    """should_retry returns False when attempt exceeds max_retries."""
    task = _task(attempt=5, max_retries=3)
    rec, _ = _reconciler()

    assert rec.should_retry(task) is False


def test_should_not_retry_when_max_retries_zero() -> None:
    """should_retry returns False when max_retries=0."""
    task = _task(attempt=0, max_retries=0)
    rec, _ = _reconciler()

    assert rec.should_retry(task) is False


# ---------------------------------------------------------------------------
# handle_timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_handle_timeout_requeues_when_retries_remain() -> None:
    """handle_timeout transitions to RETRY_QUEUED and increments attempt."""
    task = _task(attempt=1, max_retries=3)
    rec, store = _reconciler()

    await rec.handle_timeout(task)

    store.update_task_status.assert_awaited_once_with(
        task.id,
        TaskStatus.RETRY_QUEUED,
        attempt=2,
        error="Timed out",
    )


@pytest.mark.asyncio
async def test_handle_timeout_fails_when_retries_exhausted() -> None:
    """handle_timeout transitions to FAILED when no retries remain."""
    task = _task(attempt=3, max_retries=3)
    rec, store = _reconciler()

    await rec.handle_timeout(task)

    store.update_task_status.assert_awaited_once_with(
        task.id,
        TaskStatus.FAILED,
        error="Max retries exhausted",
    )


# ---------------------------------------------------------------------------
# reconcile (integration of find + handle)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reconcile_handles_all_timed_out_tasks() -> None:
    """reconcile() should call handle_timeout for every timed-out task."""
    expired1 = _task(attempt=0, max_retries=3, timeout_at=_now() - timedelta(seconds=5))
    expired2 = _task(attempt=3, max_retries=3, timeout_at=_now() - timedelta(seconds=1))
    active = _task(attempt=0, max_retries=3, timeout_at=_now() + timedelta(seconds=60))
    rec, store = _reconciler(tasks=[expired1, expired2, active])

    await rec.reconcile()

    assert store.update_task_status.await_count == 2
    calls = {call.args[0]: call.args[1] for call in store.update_task_status.await_args_list}
    assert calls[expired1.id] == TaskStatus.RETRY_QUEUED
    assert calls[expired2.id] == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_reconcile_does_nothing_when_no_timeouts() -> None:
    """reconcile() should not call update_task_status if no tasks timed out."""
    active = _task(timeout_at=_now() + timedelta(seconds=300))
    rec, store = _reconciler(tasks=[active])

    await rec.reconcile()

    store.update_task_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_with_real_store(db_path: pathlib.Path) -> None:
    """End-to-end: reconcile() via a real Store updates DB rows correctly."""
    store = Store(db_path)
    rec = Reconciler(store=store, stall_timeout_ms=30_000)

    expired = _task(attempt=1, max_retries=3, timeout_at=_now() - timedelta(seconds=5))
    await store.create_task(expired)

    await rec.reconcile()

    updated = await store.get_task(expired.id)
    assert updated is not None
    assert updated.status == TaskStatus.RETRY_QUEUED
    assert updated.attempt == 2
    assert updated.error == "Timed out"
