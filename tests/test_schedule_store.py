import pytest

from maestro.store import Store


@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    await s.init_db()
    return s


@pytest.mark.asyncio
async def test_create_and_list_schedules(store):
    await store.create_schedule(
        name="daily-post",
        task_type="create_post",
        cron="0 9 * * *",
        approval_level=2,
    )
    await store.create_schedule(
        name="engage",
        task_type="engage",
        interval_ms=3600000,
        approval_level=0,
    )
    schedules = await store.list_schedules()
    assert len(schedules) == 2
    assert schedules[0]["name"] == "daily-post"


@pytest.mark.asyncio
async def test_get_schedule(store):
    await store.create_schedule(
        name="test",
        task_type="t",
        cron="* * * * *",
    )
    s = await store.get_schedule("test")
    assert s is not None
    assert s["agent"] == "default"
    assert s["enabled"] == 1


@pytest.mark.asyncio
async def test_update_schedule(store):
    await store.create_schedule(
        name="test",
        task_type="t",
        cron="0 9 * * *",
    )
    await store.update_schedule("test", cron="0 10 * * *", approval_level=1)
    s = await store.get_schedule("test")
    assert s["cron"] == "0 10 * * *"
    assert s["approval_level"] == 1


@pytest.mark.asyncio
async def test_delete_schedule(store):
    await store.create_schedule(
        name="test",
        task_type="t",
        cron="* * * * *",
    )
    await store.delete_schedule("test")
    assert await store.get_schedule("test") is None


@pytest.mark.asyncio
async def test_toggle_schedule(store):
    await store.create_schedule(
        name="test",
        task_type="t",
        cron="* * * * *",
    )
    await store.update_schedule("test", enabled=False)
    s = await store.get_schedule("test")
    assert s["enabled"] == 0


@pytest.mark.asyncio
async def test_list_enabled_schedules(store):
    await store.create_schedule(name="a", task_type="t", cron="* * * * *")
    await store.create_schedule(name="b", task_type="t2", cron="* * * * *")
    await store.update_schedule("b", enabled=False)
    enabled = await store.list_schedules(enabled_only=True)
    assert len(enabled) == 1
    assert enabled[0]["name"] == "a"
