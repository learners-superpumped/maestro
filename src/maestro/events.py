"""Maestro EventBus — async pub/sub with fnmatch pattern matching."""

from __future__ import annotations

import logging
from fnmatch import fnmatch
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

AsyncHandler = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """Lightweight async event bus with glob-pattern subscriptions."""

    def __init__(self) -> None:
        self._listeners: list[tuple[str, AsyncHandler]] = []

    def on(self, pattern: str, handler: AsyncHandler) -> None:
        self._listeners.append((pattern, handler))

    def off(self, pattern: str, handler: AsyncHandler) -> None:
        self._listeners = [
            (p, h) for p, h in self._listeners if not (p == pattern and h is handler)
        ]

    async def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        for pattern, handler in self._listeners:
            if fnmatch(event_type, pattern):
                try:
                    await handler(event_type, payload)
                except Exception:
                    logger.exception(
                        "EventBus handler %s failed for %s",
                        handler.__name__,
                        event_type,
                    )
