"""
Slack integration for Maestro — send notifications via incoming webhook.
"""

from __future__ import annotations

import logging
import os

import aiohttp

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send notifications to Slack via webhook."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = webhook_url or os.environ.get("MAESTRO_SLACK_WEBHOOK")

    @property
    def available(self) -> bool:
        """Return True if a webhook URL is configured."""
        return self._webhook_url is not None

    async def send(self, message: str, channel: str | None = None) -> bool:
        """Send a message to Slack. Returns True if sent successfully."""
        if not self.available:
            return False

        payload: dict[str, str] = {"text": message}
        if channel:
            payload["channel"] = channel

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self._webhook_url, json=payload) as resp:  # type: ignore[arg-type]
                    ok = resp.status == 200
                    if not ok:
                        logger.warning("Slack webhook returned status %d", resp.status)
                    return ok
        except Exception:
            logger.exception("Failed to send Slack notification")
            return False

    async def send_approval_request(self, task_id: str, title: str, draft: str) -> bool:
        """Send a formatted approval request."""
        message = (
            "\U0001f514 *Approval Required*\n"
            f"*Task:* {title}\n"
            f"*ID:* `{task_id}`\n"
            f"*Draft:*\n```{draft[:500]}```\n"
            f"Approve via: `maestro approve {task_id}`"
        )
        return await self.send(message)

    async def send_completion(self, task_id: str, title: str) -> bool:
        """Send task completion notification."""
        message = f"\u2705 *Task Completed*\n*Task:* {title}\n*ID:* `{task_id}`"
        return await self.send(message)
