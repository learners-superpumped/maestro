"""Maestro WebSocket Manager — broadcasts EventBus events to connected clients."""

from __future__ import annotations

import json
import logging
from typing import Any

from aiohttp import WSMsgType, web

from maestro.events import EventBus

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self, bus: EventBus) -> None:
        self._clients: set[web.WebSocketResponse] = set()
        bus.on("*", self._broadcast)

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        """GET /ws — WebSocket endpoint."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        logger.info("WebSocket client connected (%d total)", len(self._clients))
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    pass  # Future: client→server messages
                elif msg.type == WSMsgType.ERROR:
                    logger.warning("WebSocket error: %s", ws.exception())
        finally:
            self._clients.discard(ws)
            logger.info(
                "WebSocket client disconnected (%d remaining)", len(self._clients)
            )
        return ws

    async def _broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        """Send event to all connected clients."""
        if not self._clients:
            return
        data = json.dumps({"type": event_type, "payload": payload}, default=str)
        dead: set[web.WebSocketResponse] = set()
        for ws in self._clients:
            try:
                await ws.send_str(data)
            except (ConnectionResetError, RuntimeError):
                dead.add(ws)
        self._clients -= dead
