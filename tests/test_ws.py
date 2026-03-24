import pytest
from aiohttp import web

from maestro.events import EventBus
from maestro.ws import WebSocketManager


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def ws_manager(bus):
    return WebSocketManager(bus)


async def test_ws_connect_and_receive(aiohttp_client, bus, ws_manager):
    """Client connects via WS and receives broadcast events."""
    app = web.Application()
    app.router.add_get("/ws", ws_manager.handle)
    client = await aiohttp_client(app)

    async with client.ws_connect("/ws") as ws:
        await bus.emit("task.created", {"task_id": "1"})
        msg = await ws.receive_json()
        assert msg["type"] == "task.created"
        assert msg["payload"]["task_id"] == "1"


async def test_ws_multiple_clients(aiohttp_client, bus, ws_manager):
    """Multiple clients all receive the same event."""
    app = web.Application()
    app.router.add_get("/ws", ws_manager.handle)
    client = await aiohttp_client(app)

    async with client.ws_connect("/ws") as ws1, client.ws_connect("/ws") as ws2:
        await bus.emit("task.completed", {"task_id": "2"})
        msg1 = await ws1.receive_json()
        msg2 = await ws2.receive_json()
        assert msg1["type"] == "task.completed"
        assert msg2["type"] == "task.completed"
