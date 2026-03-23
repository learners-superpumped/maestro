"""
Maestro Budget Manager — tracks and enforces daily spending limits.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from maestro.config import BudgetConfig
from maestro.store import Store


class BudgetManager:
    """Track daily spend and enforce budget limits."""

    def __init__(self, store: Store, config: BudgetConfig) -> None:
        self._store = store
        self._config = config

    async def check_budget(self, additional_usd: float = 0.0) -> dict[str, Any]:
        """Check current budget status.

        Args:
            additional_usd: Hypothetical additional spend to check feasibility.

        Returns:
            Dict with daily_limit, spent_today, remaining, can_spend, alert.
        """
        today = date.today().isoformat()
        spent = await self._store.get_daily_spend(today)
        return {
            "daily_limit": self._config.daily_limit_usd,
            "spent_today": spent,
            "remaining": self._config.daily_limit_usd - spent,
            "can_spend": spent + additional_usd <= self._config.daily_limit_usd,
            "alert": spent
            >= self._config.daily_limit_usd * self._config.alert_threshold_pct / 100,
        }

    async def record_cost(self, task_id: str, cost_usd: float) -> None:
        """Record spending for a task.

        Updates both the daily budget table and the task's cost_usd field.
        """
        today = date.today().isoformat()
        await self._store.record_spend(today, cost_usd)
