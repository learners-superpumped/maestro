"""Tests for maestro.planner — signal collection and task planning."""

from __future__ import annotations

import pathlib
import uuid
from datetime import datetime, timedelta, timezone

from maestro.config import (
    AgentConfig,
    BudgetConfig,
    ConcurrencyConfig,
    DaemonConfig,
    LoggingConfig,
    MaestroConfig,
    ProjectConfig,
)
from maestro.models import Task, TaskStatus
from maestro.planner import Planner, SignalCollector
from maestro.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_goal_in_db(
    store: Store, goal_id: str = "g1", workspace: str = "/ws/test", **kw
):
    """Helper to create a goal directly in the DB."""
    defaults = dict(id=goal_id, workspace=workspace, description="Test goal")
    defaults.update(kw)
    return await store.create_goal(**defaults)


def _task(
    workspace: str = "/ws/test", status: TaskStatus = TaskStatus.PENDING, **kw
) -> Task:
    defaults = dict(
        id=str(uuid.uuid4()),
        type="shell",
        workspace=workspace,
        title="Test task",
        instruction="echo hello",
        status=status,
    )
    defaults.update(kw)
    return Task(**defaults)


def _config() -> MaestroConfig:
    return MaestroConfig(
        project=ProjectConfig(name="test"),
        daemon=DaemonConfig(),
        concurrency=ConcurrencyConfig(),
        budget=BudgetConfig(),
        agent=AgentConfig(),
        logging=LoggingConfig(),
    )


# ---------------------------------------------------------------------------
# SignalCollector tests
# ---------------------------------------------------------------------------


async def test_signal_when_no_active_tasks(db_path: pathlib.Path) -> None:
    """A goal with no active tasks should emit a gap_detected signal."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/test")

    collector = SignalCollector(store)
    signals = await collector.collect_signals()

    assert len(signals) == 1
    assert signals[0]["goal_id"] == "g1"
    assert signals[0]["type"] == "gap_detected"


async def test_no_signals_when_active_tasks_exist(db_path: pathlib.Path) -> None:
    """If a goal workspace has active (non-terminal) tasks, no signal is emitted."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/busy")

    # Create a running task in the workspace
    task = _task(workspace="/ws/busy", status=TaskStatus.RUNNING)
    await store.create_task(task)

    collector = SignalCollector(store)
    signals = await collector.collect_signals()

    assert len(signals) == 0


async def test_no_signals_when_pending_tasks_exist(db_path: pathlib.Path) -> None:
    """Pending tasks also count as active (non-terminal)."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/queued")

    task = _task(workspace="/ws/queued", status=TaskStatus.PENDING)
    await store.create_task(task)

    collector = SignalCollector(store)
    signals = await collector.collect_signals()

    assert len(signals) == 0


async def test_multiple_goals_independent_signals(db_path: pathlib.Path) -> None:
    """Each goal is evaluated independently."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/a")
    await _create_goal_in_db(store, "g2", "/ws/b")

    # g2 has an active task, g1 does not
    task = _task(workspace="/ws/b", status=TaskStatus.RUNNING)
    await store.create_task(task)

    collector = SignalCollector(store)
    signals = await collector.collect_signals()

    assert len(signals) == 1
    assert signals[0]["goal_id"] == "g1"


async def test_cooldown_skips_goal(db_path: pathlib.Path) -> None:
    """Goal within cooldown period should not emit signals."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/test", cooldown_hours=24)

    # Set last_task_created_at to 1 hour ago (within 24h cooldown)
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await store.update_goal("g1", last_task_created_at=recent)

    collector = SignalCollector(store)
    signals = await collector.collect_signals()

    assert len(signals) == 0


async def test_cooldown_expired_emits_signal(db_path: pathlib.Path) -> None:
    """Goal past cooldown period should emit signals."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/test", cooldown_hours=24)

    # Set last_task_created_at to 25 hours ago (past 24h cooldown)
    old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    await store.update_goal("g1", last_task_created_at=old)

    collector = SignalCollector(store)
    signals = await collector.collect_signals()

    assert len(signals) == 1
    assert signals[0]["goal_id"] == "g1"


async def test_disabled_goals_skipped(db_path: pathlib.Path) -> None:
    """Disabled goals should not be evaluated."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/test")
    await store.update_goal("g1", enabled=False)

    collector = SignalCollector(store)
    signals = await collector.collect_signals()

    assert len(signals) == 0


# ---------------------------------------------------------------------------
# Planner tests
# ---------------------------------------------------------------------------


async def test_planner_skips_when_no_signals(db_path: pathlib.Path) -> None:
    """Planner returns empty list when there are no signals."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "/ws/busy")

    # Active task means no signals
    task = _task(workspace="/ws/busy", status=TaskStatus.RUNNING)
    await store.create_task(task)

    cfg = _config()
    planner = Planner(store, cfg)

    specs = await planner.plan()
    assert specs == []


async def test_plan_creates_planning_task(db_path: pathlib.Path) -> None:
    """When signals exist, plan() returns a planning task spec for _planner workspace."""
    store = Store(db_path)
    await _create_goal_in_db(store, "g1", "ws1", description="Test goal")

    cfg = _config()
    planner = Planner(store, cfg)

    result = await planner.plan()

    assert len(result) == 1
    task_spec = result[0]
    assert task_spec["workspace"] == "_planner"
    assert task_spec["type"] == "planning"
    assert task_spec["approval_level"] == 0
    assert "g1" in task_spec["instruction"]


async def test_create_planned_tasks(db_path: pathlib.Path) -> None:
    """create_planned_tasks persists tasks to the store and returns IDs."""
    store = Store(db_path)
    cfg = _config()
    planner = Planner(store, cfg)

    specs = [
        {
            "workspace": "/ws/alpha",
            "type": "general",
            "title": "Do something",
            "instruction": "Please do it",
            "priority": 2,
            "goal_id": "g1",
        },
        {
            "workspace": "/ws/beta",
            "type": "shell",
            "title": "Run script",
            "instruction": "bash run.sh",
        },
    ]

    ids = await planner.create_planned_tasks(specs)
    assert len(ids) == 2

    # Verify tasks are in the store
    for task_id in ids:
        task = await store.get_task(task_id)
        assert task is not None
        assert task.status == TaskStatus.PENDING
        assert task.approval_level == 2  # default for planner tasks

    # Check first task details
    t1 = await store.get_task(ids[0])
    assert t1 is not None
    assert t1.priority == 2
    assert t1.goal_id == "g1"
