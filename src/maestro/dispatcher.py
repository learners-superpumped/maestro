"""
Maestro Dispatcher — selects approved tasks eligible for immediate execution.

The Dispatcher evaluates all approved tasks against three constraints:
  1. Global concurrency  (max_total_agents)
  2. Per-goal concurrency (max_per_goal)
  3. Daily budget (daily_limit_usd)

Tasks are evaluated in priority order (as returned by
``Store.list_dispatchable_tasks``).  The scheduled_at filter is applied in
SQL — tasks with a future scheduled_at are never returned by the store.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from maestro.config import BudgetConfig, ConcurrencyConfig
from maestro.models import TaskStatus
from maestro.resources import ResourceManager
from maestro.store import Store

# ---------------------------------------------------------------------------
# AgentLogProcessor
# ---------------------------------------------------------------------------


class AgentLogProcessor:
    """Processes raw Claude CLI stream events into stored logs and WebSocket summaries.

    Args:
        store: The Maestro persistence layer.
        bus:   The EventBus for emitting real-time updates.
    """

    def __init__(self, store, bus) -> None:
        self._store = store
        self._bus = bus
        self._last_emit: dict[str, float] = {}
        self._throttle_s = 0.5

    def _tool_summary(self, tool_name: str, tool_input: dict) -> str:
        if tool_name in ("Read", "Write"):
            return tool_input.get("file_path", tool_name)
        elif tool_name == "Edit":
            fp = tool_input.get("file_path", "")
            old = (tool_input.get("old_string", ""))[:30]
            new = (tool_input.get("new_string", ""))[:30]
            return f"{fp}: {old} → {new}" if fp else tool_name
        elif tool_name == "Bash":
            return (tool_input.get("command", ""))[:80]
        elif tool_name == "Grep":
            return f"pattern: '{tool_input.get('pattern', '')}'"
        return tool_name

    def _result_summary(self, result_text: str) -> str:
        lines = result_text.count("\n") + 1
        if len(result_text) > 200:
            return f"{lines} lines"
        return result_text[:100]

    async def _should_emit(self, task_id: str) -> bool:
        now = time.monotonic()
        last = self._last_emit.get(task_id, 0)
        if now - last < self._throttle_s:
            return False
        self._last_emit[task_id] = now
        return True

    async def process_event(self, task_id: str, event: dict) -> None:
        """Process a single stream event from the Claude CLI.

        Only ``assistant`` type events are processed; all others are ignored.
        """
        event_type = event.get("type")
        if event_type != "assistant":
            return
        message = event.get("message", {})
        for block in message.get("content", []):
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "")
                log_id = await self._store.record_task_log(
                    task_id=task_id,
                    log_type="text",
                    summary=text,
                    content=text,
                )
                if await self._should_emit(task_id):
                    await self._bus.emit(
                        "task.agent_log",
                        {
                            "task_id": task_id,
                            "log_id": log_id,
                            "log_type": "text",
                            "summary": text[:500],
                            "has_content": len(text) > 500,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                summary = self._tool_summary(tool_name, tool_input)
                log_id = await self._store.record_task_log(
                    task_id=task_id,
                    log_type="tool_use",
                    tool_name=tool_name,
                    summary=summary,
                    content=json.dumps(tool_input),
                )
                if await self._should_emit(task_id):
                    await self._bus.emit(
                        "task.agent_log",
                        {
                            "task_id": task_id,
                            "log_id": log_id,
                            "log_type": "tool_use",
                            "tool_name": tool_name,
                            "summary": summary,
                            "has_content": True,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
            elif block_type == "tool_result":
                result_text = str(block.get("content", ""))
                summary = self._result_summary(result_text)
                log_id = await self._store.record_task_log(
                    task_id=task_id,
                    log_type="tool_result",
                    summary=summary,
                    content=result_text,
                )
                if await self._should_emit(task_id):
                    await self._bus.emit(
                        "task.agent_log",
                        {
                            "task_id": task_id,
                            "log_id": log_id,
                            "log_type": "tool_result",
                            "summary": summary,
                            "has_content": True,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )


# ---------------------------------------------------------------------------
# DispatchDecision
# ---------------------------------------------------------------------------


@dataclass
class DispatchDecision:
    """Represents a decision to dispatch a single task."""

    task_id: str


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class Dispatcher:
    """Selects tasks ready to be dispatched to agent workers.

    Args:
        store:       The Maestro persistence layer.
        concurrency: Concurrency limits (global and per-goal).
        budget:      Daily budget configuration.
    """

    def __init__(
        self,
        store: Store,
        concurrency: ConcurrencyConfig,
        budget: BudgetConfig,
        resource_manager: ResourceManager | None = None,
    ) -> None:
        self._store = store
        self._concurrency = concurrency
        self._budget = budget
        self._resource_manager = resource_manager

    async def get_dispatch_decisions(self) -> list[DispatchDecision]:
        """Return the set of tasks that should be dispatched right now.

        Algorithm
        ---------
        1. Fetch today's cumulative spend from ``budget_daily``.
        2. Fetch the current total running/claimed count.
        3. Fetch dispatchable tasks (approved + scheduled_at filter done in SQL),
           ordered by priority ASC.
        4. Walk the candidate list and greedily assign each task to a slot,
           respecting:
           - global cap : total_running + already_dispatched < max_total_agents
           - goal cap   : running_in_goal + dispatched_in_goal < max_per_goal
                          (only for tasks that belong to a goal; standalone tasks
                          each get their own worktree so no limit applies)
           - budget cap : daily_spend + sum(dispatched budgets) + task.budget <=
                          daily_limit_usd
        5. Return the list of :class:`DispatchDecision` objects.
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # --- Step 1: budget baseline ---
        daily_spend = await self._store.get_daily_spend(today)

        # --- Step 2: global running count ---
        total_running = await self._store.count_running()

        # --- Step 3: candidates ---
        candidates = await self._store.list_dispatchable_tasks()

        # --- Step 4: greedy selection ---
        decisions: list[DispatchDecision] = []
        # Track how much virtual budget we have consumed during this call
        budgeted_so_far: float = 0.0
        # Track per-goal running counts already in the DB
        # (fetched lazily and cached to avoid repeated DB calls)
        ws_running_cache: dict[str, int] = {}
        # Track how many tasks we are dispatching per goal this cycle
        ws_dispatched: dict[str, int] = {}

        now = datetime.now(timezone.utc)

        for task in candidates:
            dispatched_count = len(decisions)

            # -- Retry backoff check --
            if task.status == TaskStatus.RETRY_QUEUED:
                if task.updated_at is None:
                    continue  # safety: skip if no updated_at
                backoff_ms = task.retry_backoff_ms()
                elapsed_ms = (now - task.updated_at).total_seconds() * 1000
                if elapsed_ms < backoff_ms:
                    continue  # still in backoff period

            # -- Dependency check --
            if task.depends_on:
                try:
                    dep_ids = json.loads(task.depends_on)
                except (json.JSONDecodeError, TypeError):
                    dep_ids = []
                if dep_ids:
                    deps_met = True
                    for dep_id in dep_ids:
                        dep_task = await self._store.get_task(dep_id)
                        if dep_task is None or dep_task.status.value != "completed":
                            deps_met = False
                            break
                    if not deps_met:
                        continue  # Dependencies not yet satisfied

            # -- Global slot check --
            if total_running + dispatched_count >= self._concurrency.max_total_agents:
                break  # No more global slots; no point continuing

            # -- Per-goal slot check --
            # Standalone tasks (no goal_id) each get their own worktree, so no
            # per-goal concurrency limit is applied between them.
            if task.goal_id is not None:
                goal_key = task.goal_id
                if goal_key not in ws_running_cache:
                    ws_running_cache[goal_key] = await self._store.count_running(
                        goal_id=task.goal_id
                    )
                goal_running = ws_running_cache[goal_key]
                goal_pending = ws_dispatched.get(goal_key, 0)

                if goal_running + goal_pending >= self._concurrency.max_per_goal:
                    continue  # This goal is full; try next candidate

            # -- Resource availability check --
            # (Resource checks are workspace-based and will be redesigned later;
            #  skipped for now.)

            # -- Budget check --
            projected_spend = daily_spend + budgeted_so_far + task.budget_usd
            if projected_spend > self._budget.daily_limit_usd:
                continue  # Would exceed daily budget; try next candidate

            # -- Accept this task --
            decisions.append(DispatchDecision(task_id=task.id))
            budgeted_so_far += task.budget_usd
            if task.goal_id is not None:
                goal_key = task.goal_id
                ws_dispatched[goal_key] = ws_dispatched.get(goal_key, 0) + 1

        return decisions
