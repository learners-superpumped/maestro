"""
Maestro Dispatcher — selects approved tasks eligible for immediate execution.

The Dispatcher evaluates all approved tasks against three constraints:
  1. Global concurrency  (max_total_agents)
  2. Per-workspace concurrency (max_per_workspace)
  3. Daily budget (daily_limit_usd)

Tasks are evaluated in priority order (as returned by
``Store.list_dispatchable_tasks``).  The scheduled_at filter is applied in
SQL — tasks with a future scheduled_at are never returned by the store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from maestro.config import BudgetConfig, ConcurrencyConfig
from maestro.resources import ResourceManager
from maestro.store import Store


# ---------------------------------------------------------------------------
# DispatchDecision
# ---------------------------------------------------------------------------


@dataclass
class DispatchDecision:
    """Represents a decision to dispatch a single task."""

    task_id: str
    workspace: str


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class Dispatcher:
    """Selects tasks ready to be dispatched to agent workers.

    Args:
        store:       The Maestro persistence layer.
        concurrency: Concurrency limits (global and per-workspace).
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
           - global cap  : total_running + already_dispatched < max_total_agents
           - workspace cap: running_in_ws + dispatched_in_ws < max_per_workspace
           - budget cap   : daily_spend + sum(dispatched budgets) + task.budget <=
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
        # Track per-workspace running counts already in the DB
        # (fetched lazily and cached to avoid repeated DB calls)
        ws_running_cache: dict[str, int] = {}
        # Track how many tasks we are dispatching per workspace this cycle
        ws_dispatched: dict[str, int] = {}

        for task in candidates:
            dispatched_count = len(decisions)

            # -- Global slot check --
            if total_running + dispatched_count >= self._concurrency.max_total_agents:
                break  # No more global slots; no point continuing

            # -- Per-workspace slot check --
            ws = task.workspace
            if ws not in ws_running_cache:
                ws_running_cache[ws] = await self._store.count_running(workspace=ws)
            ws_running = ws_running_cache[ws]
            ws_pending = ws_dispatched.get(ws, 0)

            if ws_running + ws_pending >= self._concurrency.max_per_workspace:
                continue  # This workspace is full; try next candidate

            # -- Resource availability check --
            if self._resource_manager is not None:
                required = self._resource_manager.get_workspace_resources(ws)
                if required and not self._resource_manager.all_available(required):
                    continue  # Required resources are locked; try next candidate

            # -- Budget check --
            projected_spend = daily_spend + budgeted_so_far + task.budget_usd
            if projected_spend > self._budget.daily_limit_usd:
                continue  # Would exceed daily budget; try next candidate

            # -- Accept this task --
            decisions.append(DispatchDecision(task_id=task.id, workspace=ws))
            budgeted_so_far += task.budget_usd
            ws_dispatched[ws] = ws_pending + 1

        return decisions
