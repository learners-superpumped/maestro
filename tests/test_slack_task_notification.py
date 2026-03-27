"""Unit tests for SlackAdapter task notification update behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_adapter(store_mock):
    from maestro.config import SlackConfig
    from maestro.integrations.slack import SlackAdapter

    config = SlackConfig(
        bot_token="xoxb-test",
        app_token="xapp-test",
        channel="C_CHANNEL",
    )
    bus = MagicMock()
    bus.on = MagicMock()
    bus.off = MagicMock()
    conductor = MagicMock()
    approval = MagicMock()
    adapter = SlackAdapter(store_mock, bus, conductor, approval, config)
    # Inject a fake bolt app with client
    fake_client = AsyncMock()
    fake_app = MagicMock()
    fake_app.client = fake_client
    adapter._app = fake_app
    return adapter, fake_client


@pytest.mark.asyncio
async def test_task_created_saves_ts_to_store():
    store = AsyncMock()
    store.save_task_slack_notification = AsyncMock()
    adapter, client = _make_adapter(store)

    client.chat_postMessage = AsyncMock(return_value={"ts": "111.222"})

    await adapter._on_task_event(
        "task.created",
        {"task_id": "t1", "title": "My Task", "agent": "default", "type": "task"},
    )

    store.save_task_slack_notification.assert_awaited_once_with(
        "t1", "C_CHANNEL", "111.222"
    )


@pytest.mark.asyncio
async def test_task_completed_uses_chat_update_when_ts_known():
    from maestro.models import Task, TaskStatus

    store = AsyncMock()
    store.get_task = AsyncMock(
        return_value=Task(
            id="t1",
            type="task",
            title="My Task",
            instruction="x",
            agent="default",
            status=TaskStatus.COMPLETED,
        )
    )
    store.get_task_slack_notification = AsyncMock(return_value=("C_CHANNEL", "111.222"))
    adapter, client = _make_adapter(store)

    client.chat_update = AsyncMock()

    await adapter._on_task_event("task.completed", {"task_id": "t1"})

    client.chat_update.assert_awaited_once()
    call_kwargs = client.chat_update.call_args.kwargs
    assert call_kwargs["ts"] == "111.222"
    assert call_kwargs["channel"] == "C_CHANNEL"


@pytest.mark.asyncio
async def test_task_completed_fallback_new_message_when_no_ts():
    from maestro.models import Task, TaskStatus

    store = AsyncMock()
    store.get_task = AsyncMock(
        return_value=Task(
            id="t2",
            type="task",
            title="Other Task",
            instruction="x",
            agent="default",
            status=TaskStatus.COMPLETED,
        )
    )
    store.get_task_slack_notification = AsyncMock(return_value=None)
    adapter, client = _make_adapter(store)

    client.chat_postMessage = AsyncMock()

    await adapter._on_task_event("task.completed", {"task_id": "t2"})

    client.chat_postMessage.assert_awaited_once()


@pytest.mark.asyncio
async def test_task_failed_uses_chat_update_when_ts_known():
    from maestro.models import Task, TaskStatus

    store = AsyncMock()
    store.get_task = AsyncMock(
        return_value=Task(
            id="t3",
            type="task",
            title="Failed Task",
            instruction="x",
            agent="default",
            status=TaskStatus.FAILED,
        )
    )
    store.get_task_slack_notification = AsyncMock(return_value=("C_CHANNEL", "999.000"))
    adapter, client = _make_adapter(store)

    client.chat_update = AsyncMock()

    await adapter._on_task_event("task.failed", {"task_id": "t3", "error": "boom"})

    client.chat_update.assert_awaited_once()
    call_kwargs = client.chat_update.call_args.kwargs
    assert call_kwargs["ts"] == "999.000"
