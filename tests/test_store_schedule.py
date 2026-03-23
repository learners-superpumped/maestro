import pytest
from maestro.store import Store

@pytest.fixture
async def store(tmp_path):
    s = Store(str(tmp_path / "test.db"))
    await s.init_db()
    return s

@pytest.mark.asyncio
async def test_schedule_last_run_roundtrip(store):
    assert await store.get_schedule_last_run("test-sched") is None
    await store.set_schedule_last_run("test-sched", "2026-03-23T09:00:00Z")
    assert await store.get_schedule_last_run("test-sched") == "2026-03-23T09:00:00Z"

@pytest.mark.asyncio
async def test_schedule_last_run_upsert(store):
    await store.set_schedule_last_run("s1", "2026-03-23T09:00:00Z")
    await store.set_schedule_last_run("s1", "2026-03-23T10:00:00Z")
    assert await store.get_schedule_last_run("s1") == "2026-03-23T10:00:00Z"

@pytest.mark.asyncio
async def test_scheduler_state_roundtrip(store):
    assert await store.get_scheduler_state("last_tick") is None
    await store.set_scheduler_state("last_tick", "2026-03-23T09:00:00Z")
    assert await store.get_scheduler_state("last_tick") == "2026-03-23T09:00:00Z"

@pytest.mark.asyncio
async def test_increment_review_count(store):
    from maestro.models import Task
    task = Task(id="t1", type="test", workspace="ws", title="T", instruction="I")
    await store.create_task(task)
    t = await store.get_task("t1")
    assert t.review_count == 0
    await store.increment_review_count("t1")
    t = await store.get_task("t1")
    assert t.review_count == 1
