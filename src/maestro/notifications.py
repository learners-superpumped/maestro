"""
Maestro Notification Manager.

Simple notification system backed by the notifications table.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from maestro.store import Store

logger = logging.getLogger(__name__)


class NotificationManager:
    """Creates, queries, and marks notifications as delivered."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def notify(
        self,
        type: str,
        message: str,
        task_id: str | None = None,
        channel: str = "log",
    ) -> str:
        """Create a notification and log it.

        Returns the notification_id.
        """
        notification_id = uuid.uuid4().hex[:12]

        await self._store.create_notification(
            {
                "id": notification_id,
                "type": type,
                "task_id": task_id,
                "message": message,
                "channel": channel,
            }
        )

        logger.info("[%s] %s (task=%s)", type, message, task_id)
        return notification_id

    async def get_undelivered(self, channel: str = "log") -> list[dict[str, Any]]:
        """Get undelivered notifications for a channel."""
        return await self._store.list_notifications(channel=channel, delivered=0)

    async def mark_delivered(self, notification_id: str) -> None:
        """Mark a notification as delivered."""
        await self._store.update_notification(notification_id, delivered=1)
