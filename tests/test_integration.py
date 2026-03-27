"""Integration tests for the Maestro task lifecycle.

These tests exercise the full task lifecycle through Daemon, Dispatcher, and
Reconciler components without calling the real Claude CLI.  Scenarios covered:

1. Level 0 auto-approval flow
2. Level 2 task stays PENDING
3. Concurrency limit blocks dispatch
4. Retry flow on timeout
5. Budget limit blocks dispatch
6. Timeout detection via reconciler
"""

from __future__ import annotations

import asyncio
import pathlib
import uuid
from datetime import datetime, timedelta, timezone

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
from maestro.reconciler import Reconciler
from maestro.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    max_total_agents: int = 5,
    daily_limit_usd: float = 50.0,
) -> MaestroConfig:
    return MaestroConfig(
        project=ProjectConfig(name="integration-test"),
        daemon=DaemonConfig(),
        concurrency=ConcurrencyConfig(
            max_total_agents=max_total_agents,
        ),
        budget=BudgetConfig(daily_limit_usd=daily_limit_usd, per_task_limit_usd=10.0),
        agent=AgentConfig(),
        logging=LoggingConfig(),
    )


def _make_task(
    task_id: str | None = None,
    approval_level: int = 0,
    status: TaskStatus = TaskStatus.PENDING,
    budget_usd: float = 1.0,
    attempt: int = 0,
    max_retries: int = 3,
    timeout_at: datetime | None = None,
) -> Task:
    return Task(
        id=task_id or str(uuid.uuid4()),
        type="claude",
        title="Integration test task",
        instruction="Do something",
        status=status,
        approval_level=approval_level,
        budget_usd=budget_usd,
        attempt=attempt,
        max_retries=max_retries,
        timeout_at=timeout_at,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Level 0 auto-approval flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_level0_auto_approval_and_dispatch_claimed(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Level 0 task: PENDING → auto_approve → APPROVED → dispatch_tick → CLAIMED.

    The asyncio task spawned by _dispatch_tick will eventually fail because
    there is no real Claude CLI.  We only
    assert that the task is CLAIMED immediately after _dispatch_tick returns,
    before the background asyncio task has a chance to mark it FAILED.
    """
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="lvl0-dispatch", approval_level=0)
    await store.create_task(task)

    # Step 1: auto-approve
    await daemon._auto_approve_pending()
    updated = await store.get_task("lvl0-dispatch")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED, (
        f"Expected APPROVED after auto_approve, got {updated.status}"
    )

    # Step 2: dispatch tick — transitions the task to CLAIMED synchronously
    await daemon._dispatch_tick()
    updated = await store.get_task("lvl0-dispatch")
    assert updated is not None
    # _dispatch_tick sets status to CLAIMED before handing off to _execute_task
    assert updated.status == TaskStatus.CLAIMED, (
        f"Expected CLAIMED after _dispatch_tick, got {updated.status}"
    )

    # Clean up background asyncio tasks to avoid warnings
    for atask in list(daemon._running_procs.values()):
        atask.cancel()
    if daemon._running_procs:
        await asyncio.gather(*daemon._running_procs.values(), return_exceptions=True)


# ---------------------------------------------------------------------------
# Scenario 2: Level 2 task stays PENDING after auto_approve_pending
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_level2_stays_pending(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A task with approval_level=2 must not be auto-approved."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="lvl2-pending", approval_level=2)
    await store.create_task(task)

    await daemon._auto_approve_pending()

    updated = await store.get_task("lvl2-pending")
    assert updated is not None
    assert updated.status == TaskStatus.PENDING, (
        f"Expected PENDING after auto_approve for level-2 task, got {updated.status}"
    )


# ---------------------------------------------------------------------------
# Scenario 3: Concurrency limit blocks dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrency_limit_blocks_dispatch(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """When max_total_agents RUNNING tasks already exist, no new task is dispatched."""
    store = Store(db_path)
    max_agents = 2
    config = _make_config(max_total_agents=max_agents)
    daemon = Daemon(config, store, tmp_path)

    # Fill all slots with RUNNING tasks
    for i in range(max_agents):
        running_task = _make_task(
            task_id=f"running-{i}",
            status=TaskStatus.PENDING,
        )
        await store.create_task(running_task)
        await store.update_task_status(f"running-{i}", TaskStatus.APPROVED)
        await store.update_task_status(f"running-{i}", TaskStatus.CLAIMED)
        await store.update_task_status(f"running-{i}", TaskStatus.RUNNING)

    # Create one APPROVED task that should not get dispatched
    blocked_task = _make_task(
        task_id="blocked-task",
        status=TaskStatus.PENDING,
    )
    await store.create_task(blocked_task)
    await store.update_task_status("blocked-task", TaskStatus.APPROVED)

    # Dispatch tick should not claim the blocked task
    await daemon._dispatch_tick()

    updated = await store.get_task("blocked-task")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED, (
        f"Expected task to remain APPROVED due to concurrency limit, "
        f"got {updated.status}"
    )


# ---------------------------------------------------------------------------
# Scenario 4: Retry flow via reconciler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_flow_on_timeout(db_path: pathlib.Path) -> None:
    """RUNNING task past timeout becomes RETRY_QUEUED with attempt+1."""
    store = Store(db_path)
    reconciler = Reconciler(store=store, stall_timeout_ms=30_000)

    # Create the task at PENDING and advance through state machine to RUNNING
    task = _make_task(
        task_id="timeout-retry",
        status=TaskStatus.PENDING,
        attempt=0,
        max_retries=3,
        timeout_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    )
    await store.create_task(task)
    await store.update_task_status("timeout-retry", TaskStatus.APPROVED)
    await store.update_task_status("timeout-retry", TaskStatus.CLAIMED)
    await store.update_task_status(
        "timeout-retry",
        TaskStatus.RUNNING,
        timeout_at=(datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(),
    )

    # Run reconciler
    await reconciler.reconcile()

    updated = await store.get_task("timeout-retry")
    assert updated is not None
    assert updated.status == TaskStatus.RETRY_QUEUED, (
        f"Expected RETRY_QUEUED after timeout, got {updated.status}"
    )
    assert updated.attempt == 1, (
        f"Expected attempt=1 after first retry, got {updated.attempt}"
    )
    assert updated.error == "Timed out"


# ---------------------------------------------------------------------------
# Scenario 5: Budget limit blocks dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_budget_limit_blocks_dispatch(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """An APPROVED task is not dispatched when the daily budget is exhausted."""
    store = Store(db_path)
    daily_limit = 10.0
    config = _make_config(daily_limit_usd=daily_limit)
    daemon = Daemon(config, store, tmp_path)

    # Record spend that leaves less than the task's budget
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await store.record_spend(today, 9.5)  # only 0.5 USD remaining

    # Task needs 1.0 USD — exceeds remaining budget
    expensive_task = _make_task(
        task_id="budget-blocked",
        status=TaskStatus.PENDING,
        budget_usd=1.0,
    )
    await store.create_task(expensive_task)
    await store.update_task_status("budget-blocked", TaskStatus.APPROVED)

    await daemon._dispatch_tick()

    updated = await store.get_task("budget-blocked")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED, (
        f"Expected task to remain APPROVED due to budget limit, got {updated.status}"
    )


# ---------------------------------------------------------------------------
# Scenario 6: Timeout detection by reconciler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_detection_retry_or_failed(db_path: pathlib.Path) -> None:
    """Reconciler handles a timed-out RUNNING task: RETRY_QUEUED or FAILED.

    Creates two RUNNING tasks:
    - One with retries remaining → should become RETRY_QUEUED
    - One with retries exhausted → should become FAILED
    """
    store = Store(db_path)
    reconciler = Reconciler(store=store, stall_timeout_ms=30_000)

    past = datetime.now(timezone.utc) - timedelta(minutes=5)

    # Task with retries remaining
    retryable = _make_task(
        task_id="retryable-timeout",
        status=TaskStatus.PENDING,
        attempt=1,
        max_retries=3,
    )
    await store.create_task(retryable)
    await store.update_task_status("retryable-timeout", TaskStatus.APPROVED)
    await store.update_task_status("retryable-timeout", TaskStatus.CLAIMED)
    await store.update_task_status(
        "retryable-timeout",
        TaskStatus.RUNNING,
        timeout_at=past.isoformat(),
    )

    # Task with no retries remaining (attempt == max_retries)
    exhausted = _make_task(
        task_id="exhausted-timeout",
        status=TaskStatus.PENDING,
        attempt=3,
        max_retries=3,
    )
    await store.create_task(exhausted)
    await store.update_task_status("exhausted-timeout", TaskStatus.APPROVED)
    await store.update_task_status("exhausted-timeout", TaskStatus.CLAIMED)
    await store.update_task_status(
        "exhausted-timeout",
        TaskStatus.RUNNING,
        timeout_at=past.isoformat(),
    )

    await reconciler.reconcile()

    retryable_updated = await store.get_task("retryable-timeout")
    assert retryable_updated is not None
    assert retryable_updated.status == TaskStatus.RETRY_QUEUED, (
        f"Expected RETRY_QUEUED for retryable task, got {retryable_updated.status}"
    )
    assert retryable_updated.attempt == 2

    exhausted_updated = await store.get_task("exhausted-timeout")
    assert exhausted_updated is not None
    assert exhausted_updated.status == TaskStatus.FAILED, (
        f"Expected FAILED for exhausted task, got {exhausted_updated.status}"
    )
    assert exhausted_updated.error == "Max retries exhausted"
