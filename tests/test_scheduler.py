from datetime import datetime, timedelta, timezone

import pytest

from maestro.scheduler import Scheduler
from maestro.store import Store


@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    await s.init_db()
    return s


@pytest.fixture
async def scheduler(store):
    return Scheduler(store)


@pytest.mark.asyncio
async def test_cron_schedule_due(store, scheduler):
    await store.create_schedule(
        name="daily",
        task_type="t",
        cron="0 9 * * *",
    )
    since = datetime(2026, 3, 24, 8, 0, tzinfo=timezone.utc)
    now = datetime(2026, 3, 24, 9, 1, tzinfo=timezone.utc)
    due = await scheduler.get_due_schedules(now, since)
    assert len(due) == 1
    assert due[0]["name"] == "daily"


@pytest.mark.asyncio
async def test_cron_schedule_not_due(store, scheduler):
    await store.create_schedule(
        name="daily",
        task_type="t",
        cron="0 9 * * *",
    )
    since = datetime(2026, 3, 24, 8, 0, tzinfo=timezone.utc)
    now = datetime(2026, 3, 24, 8, 30, tzinfo=timezone.utc)
    due = await scheduler.get_due_schedules(now, since)
    assert len(due) == 0


@pytest.mark.asyncio
async def test_interval_first_run(store, scheduler):
    await store.create_schedule(
        name="engage",
        task_type="t",
        interval_ms=3600000,
    )
    due = await scheduler.get_due_intervals()
    assert len(due) == 1


@pytest.mark.asyncio
async def test_interval_not_due(store, scheduler):
    await store.create_schedule(
        name="engage",
        task_type="t",
        interval_ms=3600000,
    )
    now = datetime.now(timezone.utc)
    scheduler.mark_triggered("engage", now)
    due = await scheduler.get_due_intervals(now + timedelta(minutes=30))
    assert len(due) == 0


@pytest.mark.asyncio
async def test_disabled_schedule_excluded(store, scheduler):
    await store.create_schedule(
        name="disabled",
        task_type="t",
        cron="* * * * *",
    )
    await store.update_schedule("disabled", enabled=False)
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    now = datetime(2026, 12, 31, tzinfo=timezone.utc)
    due = await scheduler.get_due_schedules(now, since)
    assert len(due) == 0
