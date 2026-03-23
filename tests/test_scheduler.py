"""Tests for the Maestro Scheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        due = scheduler.get_due_intervals(now)

        assert len(due) == 1
        assert due[0].name == "frequent-job"

    def test_interval_not_due_immediately_after_trigger(self) -> None:
        """After mark_triggered, an interval entry should not be due until the interval elapses."""
        entry = _make_interval_entry("slow-job", 3_600_000)  # 1 hour
        scheduler = Scheduler([entry])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)

        # Confirm it's due on the first call.
        assert len(scheduler.get_due_intervals(now)) == 1

        scheduler.mark_triggered("slow-job", now)

        # Should no longer be due immediately (only 1 second later).
        soon = now + timedelta(seconds=1)
        assert scheduler.get_due_intervals(soon) == []

    def test_interval_due_after_elapsed(self) -> None:
        """An interval entry should become due again once the interval has elapsed."""
        entry = _make_interval_entry("fast-job", 500)  # 500 ms
        scheduler = Scheduler([entry])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        scheduler.mark_triggered("fast-job", now)

        later = now + timedelta(milliseconds=entry.interval_ms)
        due = scheduler.get_due_intervals(later)

        assert len(due) == 1
        assert due[0].name == "fast-job"

    def test_cron_entries_ignored_by_get_due_intervals(self) -> None:
        """Cron-based entries must not appear in get_due_intervals results."""
        entry = _make_cron_entry("cron-job", "0 9 * * *")
        scheduler = Scheduler([entry])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        due = scheduler.get_due_intervals(now)

        assert due == []

    def test_empty_schedules_returns_empty_list(self) -> None:
        """Scheduler with no entries should always return an empty list for intervals."""
        scheduler = Scheduler([])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        assert scheduler.get_due_intervals(now) == []

    def test_multiple_interval_entries_independent(self) -> None:
        """Each interval entry tracks its own last_triggered independently."""
        job_a = _make_interval_entry("job-a", 3_600_000)  # 1 hour
        job_b = _make_interval_entry("job-b", 3_600_000)  # 1 hour
        scheduler = Scheduler([job_a, job_b])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)

        # Both due initially.
        assert len(scheduler.get_due_intervals(now)) == 2

        # Trigger only job-a.
        scheduler.mark_triggered("job-a", now)

        soon = now + timedelta(seconds=1)
        due = scheduler.get_due_intervals(soon)
        assert len(due) == 1
        assert due[0].name == "job-b"


# ---------------------------------------------------------------------------
# Scheduler.mark_triggered
# ---------------------------------------------------------------------------


class TestMarkTriggered:
    def test_mark_triggered_records_iso_timestamp(self) -> None:
        """mark_triggered should store an ISO datetime string for the given name."""
        entry = _make_interval_entry("job", 1_000)
        scheduler = Scheduler([entry])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        scheduler.mark_triggered("job", now)

        assert "job" in scheduler._last_triggered
        assert scheduler._last_triggered["job"] == now.isoformat()

    def test_mark_triggered_unknown_name_is_recorded(self) -> None:
        """mark_triggered on an unknown name should still record without raising."""
        scheduler = Scheduler([])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        # Should not raise.
        scheduler.mark_triggered("nonexistent", now)

        assert "nonexistent" in scheduler._last_triggered


# ---------------------------------------------------------------------------
# Scheduler.restore_last_triggered
# ---------------------------------------------------------------------------


class TestRestoreLastTriggered:
    def test_restore_last_triggered(self) -> None:
        """Restored last_triggered should prevent immediate re-triggering."""
        entry = _make_interval_entry("interval-job", 3_600_000)  # 1 hour
        scheduler = Scheduler([entry])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        scheduler.restore_last_triggered({entry.name: now.isoformat()})

        # Should not be due immediately (just "restored" as triggered).
        soon = now + timedelta(seconds=1)
        due = scheduler.get_due_intervals(soon)
        assert entry not in due

    def test_restore_last_triggered_becomes_due_after_interval(self) -> None:
        """After restore, entry should become due once the interval elapses."""
        entry = _make_interval_entry("interval-job", 3_600_000)  # 1 hour
        scheduler = Scheduler([entry])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        scheduler.restore_last_triggered({entry.name: now.isoformat()})

        later = now + timedelta(milliseconds=entry.interval_ms)
        due = scheduler.get_due_intervals(later)
        assert entry in due

    def test_restore_merges_with_existing(self) -> None:
        """restore_last_triggered should merge, not replace, existing state."""
        job_a = _make_interval_entry("job-a", 3_600_000)
        job_b = _make_interval_entry("job-b", 3_600_000)
        scheduler = Scheduler([job_a, job_b])

        now = datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)
        scheduler.mark_triggered("job-a", now)
        scheduler.restore_last_triggered({"job-b": now.isoformat()})

        soon = now + timedelta(seconds=1)
        due = scheduler.get_due_intervals(soon)
        # Neither job should be due — both have been "triggered" at `now`.
        assert due == []
