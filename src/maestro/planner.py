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

from maestro.config import MaestroConfig
from maestro.models import Task
from maestro.store import Store

logger = logging.getLogger("maestro.planner")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SignalCollector:
    """Detect gaps between declared goals and current system state."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def collect_signals(self) -> list[dict[str, Any]]:
        """Collect signals from DB. Returns list of signal dicts."""
        goals = await self._store.list_goals(enabled_only=True)
        now = datetime.now(timezone.utc)
        signals: list[dict[str, Any]] = []

        for goal in goals:
            active_tasks = await self._store.list_tasks(workspace=goal["workspace"])
            active_non_terminal = [
                t
                for t in active_tasks
                if t.status.value not in ("completed", "failed", "cancelled")
            ]

            # Guard 1: active task check
            if active_non_terminal:
                continue

            # Guard 2: cooldown check
            if goal.get("last_task_created_at"):
                last_created = datetime.fromisoformat(goal["last_task_created_at"])
                elapsed_hours = (now - last_created).total_seconds() / 3600
                if elapsed_hours < goal["cooldown_hours"]:
                    continue

            signal = self._evaluate_goal(goal)
            if signal:
                signals.append(signal)
        return signals

    def _evaluate_goal(
        self,
        goal: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Evaluate a single goal and return a signal or None."""
        return {
            "goal_id": goal["id"],
            "type": "gap_detected",
            "description": f"Goal gap for {goal['workspace']}",
            "data": {"metrics": goal.get("metrics", "{}")},
        }


class Planner:
    """Creates planning tasks based on goal signals."""

    def __init__(self, store: Store, config: MaestroConfig) -> None:
        self._store = store
        self._config = config
        self._collector = SignalCollector(store)

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
            [{"id": s["goal_id"], "description": s["description"]} for s in signals],
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
