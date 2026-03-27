"""Tests for maestro.budget — budget management."""

from __future__ import annotations

import pathlib

import pytest

from maestro.budget import BudgetManager
from maestro.config import BudgetConfig
from maestro.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _budget_config(
    daily_limit: float = 30.0,
    per_task: float = 5.0,
    alert_pct: int = 80,
) -> BudgetConfig:
    return BudgetConfig(
        daily_limit_usd=daily_limit,
        per_task_limit_usd=per_task,
        alert_threshold_pct=alert_pct,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_check_budget_under_limit(db_path: pathlib.Path) -> None:
    """Fresh budget with no spend should be fully available."""
    store = Store(db_path)
    mgr = BudgetManager(store, _budget_config(daily_limit=30.0))

    status = await mgr.check_budget()

    assert status["daily_limit"] == 30.0
    assert status["spent_today"] == 0.0
    assert status["remaining"] == 30.0
    assert status["can_spend"] is True
    assert status["alert"] is False


async def test_check_budget_exceeded(db_path: pathlib.Path) -> None:
    """Budget exceeded when spend reaches the limit."""
    store = Store(db_path)
    mgr = BudgetManager(store, _budget_config(daily_limit=10.0))

    # Simulate prior spend
    from datetime import date

    today = date.today().isoformat()
    await store.record_spend(today, 10.0)

    status = await mgr.check_budget(additional_usd=1.0)

    assert status["spent_today"] == pytest.approx(10.0)
    assert status["remaining"] == pytest.approx(0.0)
    assert status["can_spend"] is False


async def test_check_budget_with_additional(db_path: pathlib.Path) -> None:
    """can_spend accounts for the hypothetical additional amount."""
    store = Store(db_path)
    mgr = BudgetManager(store, _budget_config(daily_limit=10.0))

    from datetime import date

    today = date.today().isoformat()
    await store.record_spend(today, 8.0)

    # 8 + 2 = 10, exactly at limit — should be ok
    status = await mgr.check_budget(additional_usd=2.0)
    assert status["can_spend"] is True

    # 8 + 3 = 11, over limit
    status = await mgr.check_budget(additional_usd=3.0)
    assert status["can_spend"] is False


async def test_budget_alert_threshold(db_path: pathlib.Path) -> None:
    """Alert triggers when spend reaches the configured percentage."""
    store = Store(db_path)
    mgr = BudgetManager(store, _budget_config(daily_limit=100.0, alert_pct=80))

    from datetime import date

    today = date.today().isoformat()

    # 79% — no alert
    await store.record_spend(today, 79.0)
    status = await mgr.check_budget()
    assert status["alert"] is False

    # Push to 80% — alert
    await store.record_spend(today, 1.0)
    status = await mgr.check_budget()
    assert status["alert"] is True


async def test_record_cost(db_path: pathlib.Path) -> None:
    """record_cost updates the daily spend total."""
    store = Store(db_path)
    mgr = BudgetManager(store, _budget_config())

    await mgr.record_cost("task-1", 2.50)
    await mgr.record_cost("task-2", 1.25)

    from datetime import date

    today = date.today().isoformat()
    assert await store.get_daily_spend(today) == pytest.approx(3.75)
