"""Tests for maestro.dispatcher — dispatch decision logic."""

from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

from maestro.config import BudgetConfig, ConcurrencyConfig
from maestro.dispatcher import DispatchDecision, Dispatcher
from maestro.models import Task, TaskStatus
from maestro.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task(**kwargs) -> Task:
    """Create a minimal approved Task with sensible defaults."""
    defaults = dict(
        id=str(uuid.uuid4()),
        type="shell",
        title="Test task",
        instruction="echo hello",
        status=TaskStatus.APPROVED,
        budget_usd=2.0,
        priority=3,
    )
    defaults.update(kwargs)
    return Task(**defaults)


def _dispatcher(
    store: Store,
    max_total_agents: int = 5,
    max_per_goal: int = 2,
    daily_limit_usd: float = 50.0,
    per_task_limit_usd: float = 5.0,
) -> Dispatcher:
    concurrency = ConcurrencyConfig(
        max_total_agents=max_total_agents,
        max_per_goal=max_per_goal,
    )
    budget = BudgetConfig(
        daily_limit_usd=daily_limit_usd,
        per_task_limit_usd=per_task_limit_usd,
    )
    return Dispatcher(store=store, concurrency=concurrency, budget=budget)


# ---------------------------------------------------------------------------
# Dispatch eligible task
# ---------------------------------------------------------------------------


async def test_dispatch_eligible_task(db_path: pathlib.Path) -> None:
    """Approved task with no running agents and budget is dispatched."""
    store = Store(db_path)
    task = _task()
    await store.create_task(task)

    dispatcher = _dispatcher(store)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 1
    assert decisions[0].task_id == task.id


async def test_dispatch_returns_empty_when_no_eligible_tasks(
    db_path: pathlib.Path,
) -> None:
    """No tasks in approved state results in empty decisions."""
    store = Store(db_path)
    pending = _task(status=TaskStatus.PENDING)
    running = _task(status=TaskStatus.RUNNING)
    await store.create_task(pending)
    await store.create_task(running)

    dispatcher = _dispatcher(store)
    decisions = await dispatcher.get_dispatch_decisions()

    assert decisions == []


# ---------------------------------------------------------------------------
# Respects max_total_agents
# ---------------------------------------------------------------------------


async def test_respects_max_total_agents(db_path: pathlib.Path) -> None:
    """Dispatcher never exceeds max_total_agents across all goals."""
    store = Store(db_path)

    # 1 already running
    running = _task(status=TaskStatus.RUNNING)
    await store.create_task(running)

    # 3 approved candidates, limit is 3 total
    for i in range(3):
        t = _task()
        await store.create_task(t)

    dispatcher = _dispatcher(store, max_total_agents=3)
    decisions = await dispatcher.get_dispatch_decisions()

    # Only 2 more can be dispatched (3 total - 1 running = 2 slots)
    assert len(decisions) == 2


async def test_max_total_agents_already_full(db_path: pathlib.Path) -> None:
    """No tasks dispatched when running count already equals max_total_agents."""
    store = Store(db_path)

    # Fill all slots with running tasks
    for _ in range(3):
        await store.create_task(_task(status=TaskStatus.RUNNING))

    # One approved task waiting
    await store.create_task(_task())

    dispatcher = _dispatcher(store, max_total_agents=3)
    decisions = await dispatcher.get_dispatch_decisions()

    assert decisions == []


# ---------------------------------------------------------------------------
# Respects max_per_goal
# ---------------------------------------------------------------------------


async def test_respects_max_per_goal(db_path: pathlib.Path) -> None:
    """Dispatcher does not exceed max_per_goal for any single goal."""
    store = Store(db_path)

    goal_id = "goal-alpha"

    # 1 already running in goal-alpha
    running = _task(goal_id=goal_id, status=TaskStatus.RUNNING)
    await store.create_task(running)

    # 2 approved tasks in the same goal, limit is 1 per goal
    t1 = _task(goal_id=goal_id, priority=1)
    t2 = _task(goal_id=goal_id, priority=2)
    await store.create_task(t1)
    await store.create_task(t2)

    dispatcher = _dispatcher(store, max_total_agents=10, max_per_goal=1)
    decisions = await dispatcher.get_dispatch_decisions()

    # Goal already at capacity; neither should be dispatched
    assert len(decisions) == 0


async def test_max_per_goal_allows_other_goals(db_path: pathlib.Path) -> None:
    """Tasks in other goals are still dispatched when one goal is full."""
    store = Store(db_path)

    # goal-alpha is at max (1 running, limit=1)
    await store.create_task(_task(goal_id="goal-alpha", status=TaskStatus.RUNNING))
    blocked = _task(goal_id="goal-alpha")
    await store.create_task(blocked)

    # goal-beta has room
    allowed = _task(goal_id="goal-beta")
    await store.create_task(allowed)

    dispatcher = _dispatcher(store, max_total_agents=10, max_per_goal=1)
    decisions = await dispatcher.get_dispatch_decisions()

    ids = [d.task_id for d in decisions]
    assert allowed.id in ids
    assert blocked.id not in ids


async def test_per_goal_slot_consumed_within_dispatch(db_path: pathlib.Path) -> None:
    """When two approved tasks share a goal, only max_per_goal are dispatched."""
    store = Store(db_path)

    goal_id = "goal-shared"
    t1 = _task(goal_id=goal_id, priority=1)
    t2 = _task(goal_id=goal_id, priority=2)
    t3 = _task(goal_id=goal_id, priority=3)
    for t in (t1, t2, t3):
        await store.create_task(t)

    dispatcher = _dispatcher(store, max_total_agents=10, max_per_goal=2)
    decisions = await dispatcher.get_dispatch_decisions()

    # Only 2 out of 3 should be dispatched
    assert len(decisions) == 2
    ids = [d.task_id for d in decisions]
    assert t1.id in ids
    assert t2.id in ids
    assert t3.id not in ids


async def test_standalone_tasks_no_per_goal_limit(db_path: pathlib.Path) -> None:
    """Standalone tasks (no goal_id) are not subject to per-goal concurrency limits."""
    store = Store(db_path)

    # 3 standalone tasks — each gets its own worktree, no shared limit
    t1 = _task(priority=1)
    t2 = _task(priority=2)
    t3 = _task(priority=3)
    for t in (t1, t2, t3):
        await store.create_task(t)

    # max_per_goal=1 should NOT restrict standalone tasks
    dispatcher = _dispatcher(store, max_total_agents=10, max_per_goal=1)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 3
    ids = [d.task_id for d in decisions]
    assert t1.id in ids
    assert t2.id in ids
    assert t3.id in ids


# ---------------------------------------------------------------------------
# Respects budget limit
# ---------------------------------------------------------------------------


async def test_respects_daily_budget_limit(db_path: pathlib.Path) -> None:
    """Tasks are skipped when adding their budget would exceed the daily limit."""
    store = Store(db_path)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Spend most of the budget already
    await store.record_spend(today, 9.0)

    # This task costs 2.0, which would push total to 11.0 > 10.0 limit
    expensive_task = _task(budget_usd=2.0)
    await store.create_task(expensive_task)

    dispatcher = _dispatcher(store, daily_limit_usd=10.0)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 0


async def test_respects_daily_budget_exact_fit(db_path: pathlib.Path) -> None:
    """A task that exactly meets (not exceeds) the remaining budget is dispatched."""
    store = Store(db_path)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await store.record_spend(today, 8.0)

    # Task costs exactly 2.0, total would be 10.0 == limit — allowed
    fitting_task = _task(budget_usd=2.0)
    await store.create_task(fitting_task)

    dispatcher = _dispatcher(store, daily_limit_usd=10.0)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 1
    assert decisions[0].task_id == fitting_task.id


async def test_budget_accumulates_across_dispatch_decisions(
    db_path: pathlib.Path,
) -> None:
    """Budget consumed by earlier decisions reduces slots for later."""
    store = Store(db_path)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await store.record_spend(today, 6.0)

    # Three tasks each costing 2.0; total budget is 10.0 so only 2 fit
    t1 = _task(budget_usd=2.0, priority=1)
    t2 = _task(budget_usd=2.0, priority=2)
    t3 = _task(budget_usd=2.0, priority=3)
    for t in (t1, t2, t3):
        await store.create_task(t)

    dispatcher = _dispatcher(store, max_total_agents=10, daily_limit_usd=10.0)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 2
    ids = [d.task_id for d in decisions]
    assert t1.id in ids
    assert t2.id in ids
    assert t3.id not in ids


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------


async def test_priority_ordering(db_path: pathlib.Path) -> None:
    """Higher-priority tasks are dispatched first when limited."""
    store = Store(db_path)

    low = _task(priority=5)
    high = _task(priority=1)
    mid = _task(priority=3)

    # Insert in non-priority order
    for t in (low, mid, high):
        await store.create_task(t)

    # Limit to 2 slots — should get the two highest-priority tasks
    dispatcher = _dispatcher(store, max_total_agents=2)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 2
    ids = [d.task_id for d in decisions]
    assert high.id in ids
    assert mid.id in ids
    assert low.id not in ids


# ---------------------------------------------------------------------------
# scheduled_at filtering (handled by store, verified via dispatcher)
# ---------------------------------------------------------------------------


async def test_future_scheduled_at_not_dispatched(db_path: pathlib.Path) -> None:
    """A task with a future scheduled_at must not be returned by the dispatcher."""
    store = Store(db_path)

    future_task = _task(
        scheduled_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
    )
    await store.create_task(future_task)

    dispatcher = _dispatcher(store)
    decisions = await dispatcher.get_dispatch_decisions()

    assert decisions == []


async def test_past_scheduled_at_is_dispatched(db_path: pathlib.Path) -> None:
    """A task with a past scheduled_at is eligible for dispatch."""
    store = Store(db_path)

    past_task = _task(
        scheduled_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    await store.create_task(past_task)

    dispatcher = _dispatcher(store)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 1
    assert decisions[0].task_id == past_task.id


async def test_null_scheduled_at_is_dispatched(db_path: pathlib.Path) -> None:
    """A task with no scheduled_at (NULL) is always eligible for dispatch."""
    store = Store(db_path)

    task = _task(scheduled_at=None)
    await store.create_task(task)

    dispatcher = _dispatcher(store)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 1
    assert decisions[0].task_id == task.id


# ---------------------------------------------------------------------------
# DispatchDecision dataclass
# ---------------------------------------------------------------------------


def test_dispatch_decision_fields() -> None:
    """DispatchDecision must have only a task_id field."""
    d = DispatchDecision(task_id="abc")
    assert d.task_id == "abc"


# ---------------------------------------------------------------------------
# retry_queued backoff
# ---------------------------------------------------------------------------


async def test_retry_queued_dispatched_after_backoff(db_path: pathlib.Path) -> None:
    """A retry_queued task whose backoff period has elapsed is dispatched."""
    store = Store(db_path)
    now = datetime.now(timezone.utc)

    # attempt=1 → backoff=10s; updated_at 30s ago → elapsed > backoff
    task = _task(
        status=TaskStatus.RETRY_QUEUED,
        attempt=1,
        updated_at=now - timedelta(seconds=30),
    )
    await store.create_task(task)

    dispatcher = _dispatcher(store)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 1
    assert decisions[0].task_id == task.id


async def test_retry_queued_skipped_during_backoff(db_path: pathlib.Path) -> None:
    """A retry_queued task whose backoff period has not elapsed is skipped."""
    store = Store(db_path)
    now = datetime.now(timezone.utc)

    # attempt=1 → backoff=10s; updated_at=now → elapsed ≈ 0 < 10s
    task = _task(
        status=TaskStatus.RETRY_QUEUED,
        attempt=1,
        updated_at=now,
    )
    await store.create_task(task)

    dispatcher = _dispatcher(store)
    decisions = await dispatcher.get_dispatch_decisions()

    assert len(decisions) == 0
