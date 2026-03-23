"""Maestro Planner — signal collection and planning task creation.

Two stages:
  1. Signal collection (free): DB queries to detect gaps between goals and state
  2. Planning task creation: When signals exist, create a task for the _planner agent
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from maestro.config import GoalEntry, MaestroConfig
from maestro.models import Task
from maestro.store import Store

logger = logging.getLogger("maestro.planner")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SignalCollector:
    """Detect gaps between declared goals and current system state."""

    def __init__(self, store: Store, goals: list[GoalEntry]) -> None:
        self._store = store
        self._goals = goals

    async def collect_signals(self) -> list[dict[str, Any]]:
        """Collect signals from DB. Returns list of signal dicts."""
        signals: list[dict[str, Any]] = []
        for goal in self._goals:
            history = await self._store.search_history(
                workspace=goal.workspace, limit=10
            )
            last_action_at: str | None = history[0]["created_at"] if history else None

            active_tasks = await self._store.list_tasks(workspace=goal.workspace)
            active_non_terminal = [
                t
                for t in active_tasks
                if t.status.value not in ("completed", "failed", "cancelled")
            ]

            goal_state = await self._store.get_goal_state(goal.id)

            signal = self._evaluate_goal(
                goal, last_action_at, active_non_terminal, goal_state
            )
            if signal:
                signals.append(signal)
        return signals

    def _evaluate_goal(
        self,
        goal: GoalEntry,
        last_action_at: str | None,
        active_tasks: list[Task],
        goal_state: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if active_tasks:
            return None
        if last_action_at is None:
            return {
                "goal_id": goal.id,
                "type": "no_activity",
                "description": f"No activity ever for {goal.workspace}",
                "data": {},
            }
        return {
            "goal_id": goal.id,
            "type": "gap_detected",
            "description": f"Goal gap for {goal.workspace}",
            "data": {"last_action": last_action_at},
        }


class Planner:
    """Creates planning tasks based on goal signals."""

    def __init__(
        self,
        store: Store,
        config: MaestroConfig,
        signal_collector: SignalCollector,
    ) -> None:
        self._store = store
        self._config = config
        self._collector = signal_collector

    @property
    def collector(self) -> SignalCollector:
        return self._collector

    async def plan(self) -> list[dict[str, Any]]:
        """Collect signals and create a planning task if signals exist."""
        signals = await self._collector.collect_signals()
        if not signals:
            return []
        return [self._build_planning_task(signals)]

    def _build_planning_task(self, signals: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a planning task spec for the _planner workspace agent."""
        goals_text = json.dumps(
            [
                {"id": g.id, "description": g.description, "workspace": g.workspace}
                for g in self._config.goals
            ],
            ensure_ascii=False,
        )
        signals_text = json.dumps(signals, ensure_ascii=False)

        instruction = (
            "다음 목표와 신호를 분석하여 실행 태스크를 생성하라.\n\n"
            f"## Goals\n{goals_text}\n\n"
            f"## Signals\n{signals_text}\n\n"
            "JSON 배열로 반환하라."
        )

        return {
            "workspace": "_planner",
            "type": "planning",
            "title": f"Plan tasks for {len(signals)} signals",
            "instruction": instruction,
            "priority": 1,
            "approval_level": 0,
        }

    async def create_planned_tasks(self, task_specs: list[dict[str, Any]]) -> list[str]:
        """Create tasks from planner agent output. Returns task IDs."""
        ids: list[str] = []
        for spec in task_specs:
            task = Task(
                id=str(uuid.uuid4())[:8],
                type=spec.get("type", "general"),
                workspace=spec["workspace"],
                title=spec["title"],
                instruction=spec["instruction"],
                priority=spec.get("priority", 3),
                goal_id=spec.get("goal_id"),
                approval_level=spec.get("approval_level", 2),
            )
            await self._store.create_task(task)
            ids.append(task.id)
        return ids
