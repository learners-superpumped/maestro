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


# ---------------------------------------------------------------------------
# EventEmittingStore
# ---------------------------------------------------------------------------

from maestro.models import TaskStatus  # noqa: E402
from maestro.store import Store  # noqa: E402


class EventEmittingStore(Store):
    """Store subclass that emits events on write operations."""

    def __init__(self, db_path: str, bus: EventBus) -> None:
        super().__init__(db_path)
        self._bus = bus

    # -- Tasks --
    async def create_task(self, task) -> None:
        await super().create_task(task)
        await self._bus.emit(
            "task.created",
            {
                "task_id": task.id,
                "workspace": task.workspace,
                "title": task.title,
                "type": task.type,
            },
        )

    async def update_task_status(self, task_id, status, **kwargs):
        old = await self.get_task(task_id)
        old_status = old.status.value if old else None
        await super().update_task_status(task_id, status, **kwargs)
        await self._bus.emit(
            "task.status_changed",
            {
                "task_id": task_id,
                "old_status": old_status,
                "new_status": status.value,
            },
        )
        if status == TaskStatus.COMPLETED:
            await self._bus.emit("task.completed", {"task_id": task_id})
        elif status == TaskStatus.FAILED:
            await self._bus.emit(
                "task.failed", {"task_id": task_id, "error": kwargs.get("error")}
            )

    async def update_task_fields(self, task_id, **kwargs):
        await super().update_task_fields(task_id, **kwargs)
        await self._bus.emit(
            "task.updated", {"task_id": task_id, "fields": list(kwargs.keys())}
        )

    async def increment_review_count(self, task_id):
        await super().increment_review_count(task_id)
        await self._bus.emit("task.review_updated", {"task_id": task_id})

    # -- Assets --
    async def create_asset(self, asset):
        await super().create_asset(asset)
        await self._bus.emit(
            "asset.registered",
            {
                "asset_id": asset["id"],
                "asset_type": asset["asset_type"],
                "workspace": asset.get("workspace", "_shared"),
                "title": asset["title"],
            },
        )

    async def update_asset(self, asset_id, **kwargs):
        await super().update_asset(asset_id, **kwargs)
        if kwargs.get("archived") == 1:
            await self._bus.emit("asset.archived", {"asset_id": asset_id})
        else:
            await self._bus.emit("asset.updated", {"asset_id": asset_id})

    async def delete_asset(self, asset_id):
        await super().delete_asset(asset_id)
        await self._bus.emit("asset.deleted", {"asset_id": asset_id})

    async def archive_expired_assets(self):
        count = await super().archive_expired_assets()
        if count > 0:
            await self._bus.emit("asset.bulk_archived", {"count": count})
        return count

    async def purge_archived_assets(self, grace_days=30):
        count = await super().purge_archived_assets(grace_days)
        if count > 0:
            await self._bus.emit("asset.bulk_purged", {"count": count})
        return count

    # -- Approvals --
    async def create_approval(self, approval):
        await super().create_approval(approval)
        await self._bus.emit(
            "approval.submitted",
            {
                "approval_id": approval["id"],
                "task_id": approval["task_id"],
            },
        )

    async def update_approval(self, approval_id, **kwargs):
        await super().update_approval(approval_id, **kwargs)
        status = kwargs.get("status")
        if status:
            await self._bus.emit(
                f"approval.{status}",
                {"approval_id": approval_id, "status": status},
            )

    # -- Schedules --
    async def create_schedule(self, **kwargs):
        result = await super().create_schedule(**kwargs)
        await self._bus.emit(
            "schedule.created",
            {"name": kwargs["name"], "workspace": kwargs["workspace"]},
        )
        return result

    async def update_schedule(self, name, **fields):
        await super().update_schedule(name, **fields)
        event = "schedule.toggled" if "enabled" in fields else "schedule.updated"
        await self._bus.emit(event, {"name": name, **fields})

    async def delete_schedule(self, name):
        await super().delete_schedule(name)
        await self._bus.emit("schedule.deleted", {"name": name})

    # -- Extract Rules --
    async def create_extract_rule(self, **kwargs):
        result = await super().create_extract_rule(**kwargs)
        await self._bus.emit(
            "rule.created",
            {
                "workspace": kwargs["workspace"],
                "task_type": kwargs["task_type"],
                "asset_type": kwargs["asset_type"],
            },
        )
        return result

    async def delete_extract_rule(self, workspace, task_type):
        await super().delete_extract_rule(workspace, task_type)
        await self._bus.emit(
            "rule.deleted", {"workspace": workspace, "task_type": task_type}
        )
