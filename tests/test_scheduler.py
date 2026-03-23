"""Tests for the Maestro Scheduler."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from maestro.config import ScheduleEntry
from maestro.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cron_entry(name: str, cron: str) -> ScheduleEntry:
    return ScheduleEntry(
        name=name,
        workspace="test-workspace",
        task_type="test_task",
        cron=cron,
        interval_ms=None,
    )


def _make_interval_entry(name: str, interval_ms: int) -> ScheduleEntry:
    return ScheduleEntry(
        name=name,
        workspace="test-workspace",
        task_type="test_task",
        cron=None,
        interval_ms=interval_ms,
    )


# ---------------------------------------------------------------------------
# Scheduler.get_due_schedules — cron-based
# ---------------------------------------------------------------------------


class TestGetDueSchedules:
    def test_cron_is_due_when_fire_time_falls_in_window(self) -> None:
        """A cron entry whose next fire time after `since` is <= `now` should be returned."""
        # "0 9 * * *" fires at 09:00 every day.
        entry = _make_cron_entry("daily-post", "0 9 * * *")
        scheduler = Scheduler([entry])

        # Window: 08:59 → 09:01 on 2026-03-23 — cron fires at 09:00, which is in range.
        since = datetime(2026, 3, 23, 8, 59, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 23, 9, 1, 0, tzinfo=timezone.utc)

        due = scheduler.get_due_schedules(now=now, since=since)

        assert len(due) == 1
        assert due[0].name == "daily-post"

    def test_cron_not_due_when_no_fire_time_in_window(self) -> None:
        """A cron entry whose fire time is outside the window must not be returned."""
        # "0 9 * * *" fires at 09:00 — window 09:01 → 09:59 misses it.
        entry = _make_cron_entry("daily-post", "0 9 * * *")
        scheduler = Scheduler([entry])

        since = datetime(2026, 3, 23, 9, 1, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 23, 9, 59, 0, tzinfo=timezone.utc)

        due = scheduler.get_due_schedules(now=now, since=since)

        assert due == []

    def test_interval_entries_ignored_by_get_due_schedules(self) -> None:
        """Interval-based entries must not appear in get_due_schedules results."""
        entry = _make_interval_entry("interval-job", 60_000)
        scheduler = Scheduler([entry])

        since = datetime(2026, 3, 23, 8, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 23, 9, 0, 0, tzinfo=timezone.utc)

        due = scheduler.get_due_schedules(now=now, since=since)

        assert due == []

    def test_multiple_cron_entries_only_due_ones_returned(self) -> None:
        """Only the cron entries whose fire time falls within the window are returned."""
        # fires at 09:00
        due_entry = _make_cron_entry("morning", "0 9 * * *")
        # fires at 18:00
        not_due_entry = _make_cron_entry("evening", "0 18 * * *")
        scheduler = Scheduler([due_entry, not_due_entry])

        since = datetime(2026, 3, 23, 8, 59, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 23, 9, 1, 0, tzinfo=timezone.utc)

        due = scheduler.get_due_schedules(now=now, since=since)

        assert len(due) == 1
        assert due[0].name == "morning"

    def test_empty_schedules_returns_empty_list(self) -> None:
        """Scheduler with no entries should always return an empty list."""
        scheduler = Scheduler([])

        since = datetime(2026, 3, 23, 8, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 3, 23, 9, 0, 0, tzinfo=timezone.utc)

        due = scheduler.get_due_schedules(now=now, since=since)

        assert due == []


# ---------------------------------------------------------------------------
# Scheduler.get_due_intervals — interval-based
# ---------------------------------------------------------------------------


class TestGetDueIntervals:
    def test_interval_is_due_on_first_call(self) -> None:
        """An interval entry with no recorded trigger should be due immediately."""
        entry = _make_interval_entry("frequent-job", 60_000)
        scheduler = Scheduler([entry])

        due = scheduler.get_due_intervals()

        assert len(due) == 1
        assert due[0].name == "frequent-job"

    def test_interval_not_due_immediately_after_mark_triggered(self) -> None:
        """After mark_triggered, an interval entry should not be due until the interval elapses."""
        # Very long interval (1 hour) so it won't elapse during the test.
        entry = _make_interval_entry("slow-job", 3_600_000)
        scheduler = Scheduler([entry])

        # Confirm it's due on the first call.
        assert len(scheduler.get_due_intervals()) == 1

        scheduler.mark_triggered("slow-job")

        # Should no longer be due immediately.
        assert scheduler.get_due_intervals() == []

    def test_interval_becomes_due_after_elapsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An interval entry should become due again once the interval has elapsed."""
        entry = _make_interval_entry("fast-job", 500)  # 500 ms
        scheduler = Scheduler([entry])

        # Simulate trigger happening 1 second ago by monkeypatching monotonic.
        triggered_at = time.monotonic() - 1.0  # 1 second ago
        scheduler._last_triggered["fast-job"] = triggered_at

        # 500 ms interval has elapsed — should be due.
        due = scheduler.get_due_intervals()

        assert len(due) == 1
        assert due[0].name == "fast-job"

    def test_cron_entries_ignored_by_get_due_intervals(self) -> None:
        """Cron-based entries must not appear in get_due_intervals results."""
        entry = _make_cron_entry("cron-job", "0 9 * * *")
        scheduler = Scheduler([entry])

        due = scheduler.get_due_intervals()

        assert due == []

    def test_empty_schedules_returns_empty_list(self) -> None:
        """Scheduler with no entries should always return an empty list for intervals."""
        scheduler = Scheduler([])

        assert scheduler.get_due_intervals() == []

    def test_multiple_interval_entries_independent(self) -> None:
        """Each interval entry tracks its own last_triggered independently."""
        job_a = _make_interval_entry("job-a", 3_600_000)  # 1 hour
        job_b = _make_interval_entry("job-b", 3_600_000)  # 1 hour
        scheduler = Scheduler([job_a, job_b])

        # Both due initially.
        assert len(scheduler.get_due_intervals()) == 2

        # Trigger only job-a.
        scheduler.mark_triggered("job-a")

        due = scheduler.get_due_intervals()
        assert len(due) == 1
        assert due[0].name == "job-b"


# ---------------------------------------------------------------------------
# Scheduler.mark_triggered
# ---------------------------------------------------------------------------


class TestMarkTriggered:
    def test_mark_triggered_records_timestamp(self) -> None:
        """mark_triggered should store a monotonic timestamp for the given name."""
        entry = _make_interval_entry("job", 1_000)
        scheduler = Scheduler([entry])

        before = time.monotonic()
        scheduler.mark_triggered("job")
        after = time.monotonic()

        assert "job" in scheduler._last_triggered
        assert before <= scheduler._last_triggered["job"] <= after

    def test_mark_triggered_unknown_name_is_recorded(self) -> None:
        """mark_triggered on an unknown name should still record without raising."""
        scheduler = Scheduler([])

        # Should not raise.
        scheduler.mark_triggered("nonexistent")

        assert "nonexistent" in scheduler._last_triggered
