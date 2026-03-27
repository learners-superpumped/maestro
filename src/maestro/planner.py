"""Maestro Planner — signal collection and planning task creation.

Two stages:
  1. Signal collection (free): DB queries to detect gaps between goals and state
  2. Planning task creation: When signals exist, create a task for the _planner agent
"""

from __future__ import annotations

import json
import logging
import pathlib
import uuid
from datetime import datetime, timezone
from typing import Any

from maestro.config import MaestroConfig
from maestro.models import Task, TaskStatus
from maestro.store import Store

logger = logging.getLogger("maestro.planner")

_PROMPTS_DIR = pathlib.Path(__file__).resolve().parent / "prompts"


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
            active_tasks = await self._store.list_tasks(goal_id=goal["id"])
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
            "description": f"Goal gap for goal {goal['id']}",
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
        return [await self._build_planning_task(signals)]

    async def _build_planning_task(
        self, signals: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Build a planning task spec for the _planner agent."""
        # Enrich signals with goal details from DB
        goals_info = []
        for s in signals:
            goal = await self._store.get_goal(s["goal_id"])
            goals_info.append(
                {
                    "id": s["goal_id"],
                    "description": goal["description"] if goal else s["description"],
                    "metrics": goal.get("metrics", "{}") if goal else "{}",
                }
            )

        # Fetch past completed/failed tasks for each goal
        history_parts = []
        terminal_statuses = [TaskStatus.COMPLETED, TaskStatus.FAILED]
        for s in signals:
            past_tasks = await self._store.list_tasks(
                goal_id=s["goal_id"],
                status=terminal_statuses,
                limit=5,
            )
            if past_tasks:
                for t in past_tasks:
                    result_summary = ""
                    if t.result:
                        result_summary = str(t.result)[:300]
                    history_parts.append(
                        f"- [{t.status.value}] {t.title}: {result_summary}"
                    )

        goals_text = json.dumps(goals_info, ensure_ascii=False)
        signals_text = json.dumps(signals, ensure_ascii=False)

        history_section = ""
        if history_parts:
            header = (_PROMPTS_DIR / "planner_history_header.md").read_text()
            history_section = header + "\n".join(history_parts) + "\n\n"

        template = (_PROMPTS_DIR / "planner_instruction.md").read_text()
        instruction = template.format(
            goals=goals_text,
            history_section=history_section,
            signals=signals_text,
        )

        descriptions = [g["description"] for g in goals_info]
        if len(descriptions) == 1:
            title = f"Plan: {descriptions[0]}"
        else:
            joined = ", ".join(descriptions[:3])
            suffix = f" +{len(descriptions) - 3} more" if len(descriptions) > 3 else ""
            title = f"Plan ({len(descriptions)} goals): {joined}{suffix}"

        return {
            "agent": "planner",
            "type": "planning",
            "title": title,
            "instruction": instruction,
            "priority": 1,
            "approval_level": 0,
        }

    async def create_planned_tasks(self, task_specs: list[dict[str, Any]]) -> list[str]:
        """Create tasks from planner agent output. Returns task IDs."""
        ids: list[str] = []
        id_map: dict[int, str] = {}  # step_index → task_id

        for i, spec in enumerate(task_specs):
            # Convert depends_on_steps (indices) to depends_on (task IDs)
            depends_on = None
            dep_steps = spec.get("depends_on_steps")
            if dep_steps:
                dep_ids = [id_map[s] for s in dep_steps if s in id_map]
                if dep_ids:
                    depends_on = json.dumps(dep_ids)

            task = Task(
                id=str(uuid.uuid4())[:8],
                type=spec.get("type", "general"),
                agent=spec.get("agent", "default"),
                title=spec["title"],
                instruction=spec["instruction"],
                depends_on=depends_on,
                priority=spec.get("priority", 3),
                goal_id=spec.get("goal_id"),
                approval_level=spec.get("approval_level", 2),
            )
            await self._store.create_task(task)
            ids.append(task.id)
            id_map[i] = task.id

        return ids
