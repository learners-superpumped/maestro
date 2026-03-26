import pytest

from maestro.events import EventBus, EventEmittingStore
from maestro.models import Task, TaskStatus


@pytest.fixture
def bus():
    return EventBus()


async def test_on_and_emit(bus):
    received = []

    async def handler(event_type, payload):
        received.append((event_type, payload))

    bus.on("task.*", handler)
    await bus.emit("task.created", {"task_id": "1"})
    assert len(received) == 1
    assert received[0] == ("task.created", {"task_id": "1"})


async def test_wildcard_all(bus):
    received = []

    async def handler(event_type, payload):
        received.append(event_type)

    bus.on("*", handler)
    await bus.emit("task.created", {})
    await bus.emit("asset.deleted", {})
    assert received == ["task.created", "asset.deleted"]


async def test_no_match(bus):
    received = []

    async def handler(event_type, payload):
        received.append(event_type)

    bus.on("task.*", handler)
    await bus.emit("asset.created", {})
    assert received == []


async def test_handler_error_isolated(bus):
    results = []

    async def bad_handler(event_type, payload):
        raise RuntimeError("boom")

    async def good_handler(event_type, payload):
        results.append("ok")

    bus.on("*", bad_handler)
    bus.on("*", good_handler)
    await bus.emit("test.event", {})
    assert results == ["ok"]


async def test_off(bus):
    received = []

    async def handler(event_type, payload):
        received.append(event_type)

    bus.on("task.*", handler)
    bus.off("task.*", handler)
    await bus.emit("task.created", {})
    assert received == []


async def test_exact_match(bus):
    received = []

    async def handler(event_type, payload):
        received.append(event_type)

    bus.on("task.created", handler)
    await bus.emit("task.created", {})
    await bus.emit("task.completed", {})
    assert received == ["task.created"]


# ---------------------------------------------------------------------------
# EventEmittingStore tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def emitting_store(tmp_path):
    bus = EventBus()
    store = EventEmittingStore(str(tmp_path / "test.db"), bus)
    await store.init_db()
    return store, bus


async def test_create_task_emits(emitting_store):
    store, bus = emitting_store
    received = []

    async def handler(et, p):
        received.append((et, p))

    bus.on("task.*", handler)
    task = Task(id="et-01", type="test", title="T", instruction="I")
    await store.create_task(task)
    assert len(received) == 1
    assert received[0][0] == "task.created"
    assert received[0][1]["task_id"] == "et-01"


async def test_update_status_emits(emitting_store):
    store, bus = emitting_store
    received = []

    async def handler(et, p):
        received.append((et, p))

    bus.on("task.*", handler)
    task = Task(id="et-02", type="test", title="T", instruction="I")
    await store.create_task(task)
    received.clear()
    await store.update_task_status("et-02", TaskStatus.APPROVED)
    assert any(e[0] == "task.status_changed" for e in received)


async def test_completed_emits_both(emitting_store):
    store, bus = emitting_store
    received = []

    async def handler(et, p):
        received.append(et)

    bus.on("task.*", handler)
    task = Task(
        id="et-03",
        type="test",
        title="T",
        instruction="I",
        status=TaskStatus.RUNNING,
    )
    await store.create_task(task)
    received.clear()
    await store.update_task_status("et-03", TaskStatus.COMPLETED)
    assert "task.status_changed" in received
    assert "task.completed" in received


async def test_db_write_still_works(emitting_store):
    store, bus = emitting_store
    task = Task(id="et-04", type="test", title="T", instruction="I")
    await store.create_task(task)
    loaded = await store.get_task("et-04")
    assert loaded is not None
    assert loaded.title == "T"


async def test_schedule_events(emitting_store):
    store, bus = emitting_store
    received = []

    async def handler(et, p):
        received.append(et)

    bus.on("schedule.*", handler)
    await store.create_schedule(name="s1", task_type="test", cron="0 * * * *")
    assert "schedule.created" in received
    received.clear()
    await store.delete_schedule("s1")
    assert "schedule.deleted" in received
