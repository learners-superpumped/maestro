"""Maestro Scheduler — DB-backed schedule evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from croniter import croniter

if TYPE_CHECKING:
    from maestro.store import Store


class Scheduler:
    """Evaluates DB-stored schedules and tracks trigger times."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self._last_triggered: dict[str, str] = {}

    def restore_last_triggered(self, data: dict[str, str]) -> None:
        self._last_triggered.update(data)

    async def get_due_schedules(self, now: datetime, since: datetime) -> list[dict]:
        """Return cron-based schedules due in (since, now]."""
        all_schedules = await self._store.list_schedules(enabled_only=True)
        due: list[dict] = []
        for entry in all_schedules:
            if entry["cron"] is None:
                continue
            since_naive = since.replace(tzinfo=None) if since.tzinfo else since
            now_naive = now.replace(tzinfo=None) if now.tzinfo else now
            cron = croniter(entry["cron"], since_naive)
            next_fire: datetime = cron.get_next(datetime)
            if next_fire <= now_naive:
                due.append(entry)
        return due

    async def get_due_intervals(self, now: datetime | None = None) -> list[dict]:
        """Return interval-based schedules that are currently due."""
        if now is None:
            now = datetime.now(timezone.utc)
        all_schedules = await self._store.list_schedules(enabled_only=True)
        due: list[dict] = []
        for entry in all_schedules:
            if entry["interval_ms"] is None:
                continue
            last_iso = self._last_triggered.get(entry["name"])
            if last_iso is None:
                due.append(entry)
                continue
            last_dt = datetime.fromisoformat(last_iso)
            elapsed_ms = (now - last_dt).total_seconds() * 1_000
            if elapsed_ms >= entry["interval_ms"]:
                due.append(entry)
        return due

    def mark_triggered(self, name: str, now: datetime | None = None) -> None:
        if now is None:
            now = datetime.now(timezone.utc)
        self._last_triggered[name] = now.isoformat()
