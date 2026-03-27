"""Tests for maestro.notifications — Notification Manager."""

from __future__ import annotations

import pathlib

from maestro.notifications import NotificationManager
from maestro.store import Store

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_notify_creates_record(db_path: pathlib.Path) -> None:
    """notify() should insert a notification record."""
    store = Store(db_path)
    mgr = NotificationManager(store)

    nid = await mgr.notify("task_completed", "Task done!", task_id="t1")

    assert nid  # non-empty

    records = await store.list_notifications()
    assert len(records) == 1
    assert records[0]["id"] == nid
    assert records[0]["type"] == "task_completed"
    assert records[0]["message"] == "Task done!"
    assert records[0]["task_id"] == "t1"
    assert records[0]["delivered"] == 0
    assert records[0]["channel"] == "log"


async def test_get_undelivered(db_path: pathlib.Path) -> None:
    """get_undelivered should return only undelivered notifications."""
    store = Store(db_path)
    mgr = NotificationManager(store)

    n1 = await mgr.notify("info", "First")
    n2 = await mgr.notify("info", "Second")

    # Mark first as delivered
    await mgr.mark_delivered(n1)

    undelivered = await mgr.get_undelivered()
    assert len(undelivered) == 1
    assert undelivered[0]["id"] == n2


async def test_mark_delivered(db_path: pathlib.Path) -> None:
    """mark_delivered should set delivered=1."""
    store = Store(db_path)
    mgr = NotificationManager(store)

    nid = await mgr.notify("alert", "Something happened")

    # Before
    records = await store.list_notifications()
    assert records[0]["delivered"] == 0

    await mgr.mark_delivered(nid)

    # After
    records = await store.list_notifications()
    assert records[0]["delivered"] == 1


async def test_notify_with_channel(db_path: pathlib.Path) -> None:
    """Notifications can be sent to different channels."""
    store = Store(db_path)
    mgr = NotificationManager(store)

    await mgr.notify("info", "Log message", channel="log")
    await mgr.notify("info", "Slack message", channel="slack")

    log_notifs = await mgr.get_undelivered(channel="log")
    assert len(log_notifs) == 1
    assert log_notifs[0]["message"] == "Log message"

    slack_notifs = await mgr.get_undelivered(channel="slack")
    assert len(slack_notifs) == 1
    assert slack_notifs[0]["message"] == "Slack message"
