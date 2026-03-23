"""Maestro Scheduler.

Determines which :class:`~maestro.config.ScheduleEntry` items are due to fire,
supporting both cron-based and interval-based schedules.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from croniter import croniter

from maestro.config import ScheduleEntry

if TYPE_CHECKING:
    pass


class Scheduler:
    """Evaluates schedule entries and tracks which have been triggered.

    Args:
        schedules: List of :class:`ScheduleEntry` objects loaded from config.
    """

    def __init__(self, schedules: list[ScheduleEntry]) -> None:
        self._schedules = schedules
        # Maps schedule name → time.monotonic() value recorded at last trigger.
        self._last_triggered: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Cron-based
    # ------------------------------------------------------------------

    def get_due_schedules(self, now: datetime, since: datetime) -> list[ScheduleEntry]:
        """Return cron-based schedules whose fire time falls within ``(since, now]``.

        Uses ``croniter`` to find the next fire time after ``since``.  If that
        fire time is <= ``now``, the entry is considered due.

        Only entries with a ``cron`` field set are evaluated.  Interval-based
        entries are silently ignored.

        Args:
            now:   The upper bound of the check window (inclusive).
            since: The lower bound of the check window (exclusive).

        Returns:
            List of :class:`ScheduleEntry` objects that are due.
        """
        due: list[ScheduleEntry] = []

        for entry in self._schedules:
            if entry.cron is None:
                continue

            # croniter works with naive datetimes; strip tzinfo for comparison.
            since_naive = since.replace(tzinfo=None) if since.tzinfo is not None else since
            now_naive = now.replace(tzinfo=None) if now.tzinfo is not None else now

            cron = croniter(entry.cron, since_naive)
            next_fire: datetime = cron.get_next(datetime)

            if next_fire <= now_naive:
                due.append(entry)

        return due

    # ------------------------------------------------------------------
    # Interval-based
    # ------------------------------------------------------------------

    def get_due_intervals(self) -> list[ScheduleEntry]:
        """Return interval-based schedules that are currently due.

        An entry is due when either:
        - It has never been triggered (no entry in ``_last_triggered``), or
        - The elapsed time since the last trigger >= the configured interval.

        Only entries with an ``interval_ms`` field set are evaluated.  Cron-based
        entries are silently ignored.

        Returns:
            List of :class:`ScheduleEntry` objects that are due.
        """
        due: list[ScheduleEntry] = []
        now_mono = time.monotonic()

        for entry in self._schedules:
            if entry.interval_ms is None:
                continue

            last = self._last_triggered.get(entry.name)
            if last is None:
                # Never triggered — always due on first call.
                due.append(entry)
                continue

            elapsed_ms = (now_mono - last) * 1_000
            if elapsed_ms >= entry.interval_ms:
                due.append(entry)

        return due

    # ------------------------------------------------------------------
    # Trigger bookkeeping
    # ------------------------------------------------------------------

    def mark_triggered(self, name: str) -> None:
        """Record that a schedule entry was just triggered.

        Args:
            name: The :attr:`~maestro.config.ScheduleEntry.name` of the entry.
        """
        self._last_triggered[name] = time.monotonic()
