"""Maestro Scheduler.

Determines which ScheduleEntry items are due to fire,
supporting both cron-based and interval-based schedules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from croniter import croniter

from maestro.config import ScheduleEntry

if TYPE_CHECKING:
    pass


class Scheduler:
    """Evaluates schedule entries and tracks which have been triggered."""

    def __init__(self, schedules: list[ScheduleEntry]) -> None:
        self._schedules = schedules
        # Maps schedule name → ISO datetime string of last trigger.
        self._last_triggered: dict[str, str] = {}

    def restore_last_triggered(self, data: dict[str, str]) -> None:
        """Restore last_triggered from DB on daemon startup."""
        self._last_triggered.update(data)

    def get_due_schedules(self, now: datetime, since: datetime) -> list[ScheduleEntry]:
        """Return cron-based schedules whose fire time falls within (since, now]."""
        due: list[ScheduleEntry] = []
        for entry in self._schedules:
            if entry.cron is None:
                continue
            since_naive = since.replace(tzinfo=None) if since.tzinfo else since
            now_naive = now.replace(tzinfo=None) if now.tzinfo else now
            cron = croniter(entry.cron, since_naive)
            next_fire: datetime = cron.get_next(datetime)
            if next_fire <= now_naive:
                due.append(entry)
        return due

    def get_due_intervals(self, now: datetime | None = None) -> list[ScheduleEntry]:
        """Return interval-based schedules that are currently due.

        Uses wall-clock time (datetime) instead of monotonic time
        for DB persistence compatibility.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        due: list[ScheduleEntry] = []
        for entry in self._schedules:
            if entry.interval_ms is None:
                continue
            last_iso = self._last_triggered.get(entry.name)
            if last_iso is None:
                due.append(entry)
                continue
            last_dt = datetime.fromisoformat(last_iso)
            elapsed_ms = (now - last_dt).total_seconds() * 1_000
            if elapsed_ms >= entry.interval_ms:
                due.append(entry)
        return due

    def mark_triggered(self, name: str, now: datetime | None = None) -> None:
        """Record that a schedule entry was just triggered."""
        if now is None:
            now = datetime.now(timezone.utc)
        self._last_triggered[name] = now.isoformat()
