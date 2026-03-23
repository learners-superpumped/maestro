"""Tests for maestro.planner — signal collection and task planning."""

from __future__ import annotations

import pathlib
import uuid

import pytest

from maestro.config import (
    BudgetConfig,
    ConcurrencyConfig,
    DaemonConfig,
    GoalEntry,
    MaestroConfig,
    ProjectConfig,
    AgentConfig,
    LoggingConfig,
)
from maestro.models import Task, TaskStatus
from maestro.planner import Planner, SignalCollector
from maestro.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _goal(
    goal_id: str = "g1",
    workspace: str = "/ws/test",
    description: str = "Test goal",
) -> GoalEntry:
    return GoalEntry(id=goal_id, description=description, workspace=workspace)


def _task(workspace: str = "/ws/test", status: TaskStatus = TaskStatus.PENDING, **kw) -> Task:
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


def _config(goals: list[GoalEntry] | None = None) -> MaestroConfig:
    return MaestroConfig(
        project=ProjectConfig(name="test"),
        daemon=DaemonConfig(),
        concurrency=ConcurrencyConfig(),
        budget=BudgetConfig(),
        agent=AgentConfig(),
        logging=LoggingConfig(),
        goals=goals or [],
    )


# ---------------------------------------------------------------------------
# SignalCollector tests
# ---------------------------------------------------------------------------


async def test_signal_when_no_history(db_path: pathlib.Path) -> None:
    """A goal with no action history at all should emit a no_activity signal."""
    store = Store(db_path)
    goal = _goal()
    collector = SignalCollector(store, [goal])

    signals = await collector.collect_signals()

    assert len(signals) == 1
    assert signals[0]["goal_id"] == "g1"
    assert signals[0]["type"] == "no_activity"


async def test_signal_when_no_active_tasks_but_has_history(
    db_path: pathlib.Path,
) -> None:
    """A goal with history but no active tasks should emit gap_detected."""
    store = Store(db_path)
    goal = _goal(workspace="/ws/alpha")

    # Create a completed task + action history
    task = _task(id="t1", workspace="/ws/alpha", status=TaskStatus.COMPLETED)
    await store.create_task(task)
    await store.record_action(
        {
            "id": str(uuid.uuid4()),
            "task_id": "t1",
            "workspace": "/ws/alpha",
            "action_type": "post",
            "platform": "test",
        }
    )

    collector = SignalCollector(store, [goal])
    signals = await collector.collect_signals()

    assert len(signals) == 1
    assert signals[0]["type"] == "gap_detected"
    assert "last_action" in signals[0]["data"]


async def test_no_signals_when_active_tasks_exist(db_path: pathlib.Path) -> None:
    """If a goal workspace has active (non-terminal) tasks, no signal is emitted."""
    store = Store(db_path)
    goal = _goal(workspace="/ws/busy")

    # Create a running task in the workspace
    task = _task(workspace="/ws/busy", status=TaskStatus.RUNNING)
    await store.create_task(task)

    collector = SignalCollector(store, [goal])
    signals = await collector.collect_signals()

    assert len(signals) == 0


async def test_no_signals_when_pending_tasks_exist(db_path: pathlib.Path) -> None:
    """Pending tasks also count as active (non-terminal)."""
    store = Store(db_path)
    goal = _goal(workspace="/ws/queued")

    task = _task(workspace="/ws/queued", status=TaskStatus.PENDING)
    await store.create_task(task)

    collector = SignalCollector(store, [goal])
    signals = await collector.collect_signals()

    assert len(signals) == 0


async def test_multiple_goals_independent_signals(db_path: pathlib.Path) -> None:
    """Each goal is evaluated independently."""
    store = Store(db_path)
    g1 = _goal(goal_id="g1", workspace="/ws/a")
    g2 = _goal(goal_id="g2", workspace="/ws/b")

    # g2 has an active task, g1 does not
    task = _task(workspace="/ws/b", status=TaskStatus.RUNNING)
    await store.create_task(task)

    collector = SignalCollector(store, [g1, g2])
    signals = await collector.collect_signals()

    assert len(signals) == 1
    assert signals[0]["goal_id"] == "g1"


# ---------------------------------------------------------------------------
# Planner tests
# ---------------------------------------------------------------------------


async def test_planner_skips_when_no_signals(db_path: pathlib.Path) -> None:
    """Planner returns empty list when there are no signals."""
    store = Store(db_path)
    goal = _goal(workspace="/ws/busy")

    # Active task means no signals
    task = _task(workspace="/ws/busy", status=TaskStatus.RUNNING)
    await store.create_task(task)

    cfg = _config(goals=[goal])
    collector = SignalCollector(store, [goal])
    planner = Planner(store, cfg, collector)

    specs = await planner.plan()
    assert specs == []


async def test_plan_from_signals_creates_tasks(db_path: pathlib.Path) -> None:
    """Rule-based planner creates task specs from signals (no API key)."""
    store = Store(db_path)
    goal = _goal(goal_id="g1", workspace="/ws/test", description="Post daily content")

    cfg = _config(goals=[goal])
    collector = SignalCollector(store, [goal])
    # Ensure no API key is set for rule-based path
    planner = Planner(store, cfg, collector)
    planner._api_key = None

    specs = await planner.plan()

    assert len(specs) == 1
    assert specs[0]["workspace"] == "/ws/test"
    assert specs[0]["goal_id"] == "g1"
    assert "Post daily content" in specs[0]["instruction"]
    assert specs[0]["priority"] == 3


async def test_create_planned_tasks(db_path: pathlib.Path) -> None:
    """create_planned_tasks persists tasks to the store and returns IDs."""
    store = Store(db_path)
    cfg = _config()
    collector = SignalCollector(store, [])
    planner = Planner(store, cfg, collector)

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
