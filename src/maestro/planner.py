"""
Maestro Planner — signal collection and task planning.

Two stages:
  1. Signal collection (free): DB queries to detect gaps between goals and state
  2. LLM planning (optional): When signals exist, call Claude API for structured tasks
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from maestro.config import GoalEntry, MaestroConfig
from maestro.models import Task
from maestro.store import Store

logger = logging.getLogger("maestro.planner")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Signal Collector
# ---------------------------------------------------------------------------


class SignalCollector:
    """Detect gaps between declared goals and current system state."""

    def __init__(self, store: Store, goals: list[GoalEntry]) -> None:
        self._store = store
        self._goals = goals

    async def collect_signals(self) -> list[dict[str, Any]]:
        """Collect signals from DB.  Returns list of signal dicts.

        Each signal: {"goal_id": str, "type": str, "description": str, "data": dict}
        """
        signals: list[dict[str, Any]] = []
        for goal in self._goals:
            # Check action_history for last activity in this workspace
            history = await self._store.search_history(
                workspace=goal.workspace, limit=10
            )
            last_action_at: str | None = history[0]["created_at"] if history else None

            # Check pending/running tasks for this workspace (avoid duplicates)
            active_tasks = await self._store.list_tasks(workspace=goal.workspace)
            active_non_terminal = [
                t
                for t in active_tasks
                if t.status.value not in ("completed", "failed", "cancelled")
            ]

            # Check goal_state for last evaluation
            goal_state = await self._store.get_goal_state(goal.id)

            # Determine if there's a gap
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
        """Evaluate a single goal.  Return signal dict or None."""
        # If there are already active tasks for this workspace, skip
        if active_tasks:
            return None

        # If no history at all, definitely a signal
        if last_action_at is None:
            return {
                "goal_id": goal.id,
                "type": "no_activity",
                "description": f"No activity ever for {goal.workspace}",
                "data": {},
            }

        # Otherwise, gap detected — could add time-based heuristics here
        return {
            "goal_id": goal.id,
            "type": "gap_detected",
            "description": f"Goal gap for {goal.workspace}",
            "data": {"last_action": last_action_at},
        }


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class Planner:
    """Creates tasks based on goal signals, optionally using LLM planning."""

    def __init__(
        self,
        store: Store,
        config: MaestroConfig,
        signal_collector: SignalCollector,
    ) -> None:
        self._store = store
        self._config = config
        self._collector = signal_collector
        self._api_key = os.environ.get("ANTHROPIC_API_KEY")

    @property
    def collector(self) -> SignalCollector:
        """Expose the signal collector for daemon use."""
        return self._collector

    async def plan(self) -> list[dict[str, Any]]:
        """Run planner: collect signals, optionally call LLM, return task specs."""
        signals = await self._collector.collect_signals()
        if not signals:
            return []

        if self._api_key:
            return await self._plan_with_llm(signals)
        else:
            return self._plan_from_signals(signals)

    def _plan_from_signals(self, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Simple rule-based planning (no LLM).  Creates basic tasks from signals."""
        tasks: list[dict[str, Any]] = []
        for signal in signals:
            goal = next(
                (g for g in self._config.goals if g.id == signal["goal_id"]),
                None,
            )
            if goal:
                tasks.append(
                    {
                        "workspace": goal.workspace,
                        "type": "general",
                        "title": f"Address: {signal['description']}",
                        "instruction": (
                            f"Goal: {goal.description}. "
                            f"Signal: {signal['description']}. "
                            f"Please take appropriate action."
                        ),
                        "priority": 3,
                        "goal_id": goal.id,
                    }
                )
        return tasks

    async def _plan_with_llm(
        self, signals: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Call Claude API (Sonnet) to create structured tasks from signals.

        Falls back to rule-based planning on any error.
        """
        try:
            import anthropic  # noqa: F811
        except ImportError:
            logger.warning(
                "anthropic package not installed; falling back to rule-based planning"
            )
            return self._plan_from_signals(signals)

        try:
            client = anthropic.AsyncAnthropic(api_key=self._api_key)

            # Build the prompt
            goals_text = "\n".join(
                f"- [{g.id}] {g.description} (workspace: {g.workspace})"
                for g in self._config.goals
            )
            signals_text = "\n".join(
                f"- [{s['goal_id']}] {s['type']}: {s['description']}" for s in signals
            )

            prompt = (
                "You are a task planner for an autonomous operations system.\n\n"
                f"## Goals\n{goals_text}\n\n"
                f"## Detected Signals\n{signals_text}\n\n"
                "Create tasks to address these signals."
                " Return a JSON array of task objects, "
                "each with: workspace, type, title, instruction,"
                " priority (1-5), goal_id.\n"
                "Return ONLY the JSON array, no markdown."
            )

            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response
            text = response.content[0].text  # type: ignore[union-attr]
            task_specs = json.loads(text)
            if isinstance(task_specs, list):
                return task_specs

            logger.warning("LLM returned non-list; falling back to rule-based")
            return self._plan_from_signals(signals)

        except Exception:
            logger.exception("LLM planning failed; falling back to rule-based")
            return self._plan_from_signals(signals)

    async def create_planned_tasks(self, task_specs: list[dict[str, Any]]) -> list[str]:
        """Create tasks from planner output.  Returns task IDs."""
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
