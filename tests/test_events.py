import pytest

from maestro.events import EventBus


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
