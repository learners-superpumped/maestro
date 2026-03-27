"""Tests for maestro.integrations.slack — SlackAdapter."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

from maestro.config import SlackConfig
from maestro.integrations.slack import (
    SlackAdapter,
    _build_reject_modal,
    _build_revise_modal,
    _format_approval_done,
    _format_approval_request,
    _format_task_completed,
    _format_task_created,
    _format_task_failed,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    bot_token: str | None = None,
    app_token: str | None = None,
    channel: str = "#maestro-ops",
) -> SlackConfig:
    return SlackConfig(
        enabled=True,
        bot_token=bot_token,
        app_token=app_token,
        channel=channel,
    )


def _make_adapter(
    config: SlackConfig | None = None,
    store: AsyncMock | None = None,
    bus: MagicMock | None = None,
    conductor: AsyncMock | None = None,
    approval: AsyncMock | None = None,
) -> SlackAdapter:
    """Create a SlackAdapter with mock dependencies."""
    if config is None:
        config = _make_config(bot_token="xoxb-test", app_token="xapp-test")
    if store is None:
        store = AsyncMock()
        store.list_slack_threads = AsyncMock(return_value=[])
        store.create_slack_thread = AsyncMock(return_value={})
        store.update_slack_thread_progress = AsyncMock()
        store.get_task = AsyncMock(return_value=None)
        store.get_approval_by_task = AsyncMock(return_value=None)
    if bus is None:
        bus = MagicMock()
        bus.on = MagicMock()
        bus.off = MagicMock()
    if conductor is None:
        conductor = AsyncMock()
        conductor.handle_message = AsyncMock(return_value="OK")
    if approval is None:
        approval = AsyncMock()
        approval.approve = AsyncMock()
        approval.reject = AsyncMock()
        approval.revise = AsyncMock()

    return SlackAdapter(
        store=store,
        bus=bus,
        conductor=conductor,
        approval_manager=approval,
        config=config,
    )


def _mock_client() -> AsyncMock:
    """Create a mock Slack client with common methods."""
    client = AsyncMock()
    client.reactions_add = AsyncMock()
    client.reactions_remove = AsyncMock()
    client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.123456"})
    client.chat_update = AsyncMock()
    client.views_open = AsyncMock()
    return client


# ===========================================================================
# TestSlackAdapterInit
# ===========================================================================


class TestSlackAdapterInit:
    def test_init_stores_dependencies(self) -> None:
        store = AsyncMock()
        bus = MagicMock()
        conductor = AsyncMock()
        approval = AsyncMock()
        config = _make_config(bot_token="xoxb-test", app_token="xapp-test")

        adapter = SlackAdapter(store, bus, conductor, approval, config)

        assert adapter._store is store
        assert adapter._bus is bus
        assert adapter._conductor is conductor
        assert adapter._approval is approval
        assert adapter._config is config

    def test_not_available_without_tokens(self) -> None:
        adapter = _make_adapter(config=_make_config(bot_token=None, app_token=None))
        assert adapter.available is False

        adapter2 = _make_adapter(
            config=_make_config(bot_token="xoxb-test", app_token=None)
        )
        assert adapter2.available is False

        adapter3 = _make_adapter(
            config=_make_config(bot_token=None, app_token="xapp-test")
        )
        assert adapter3.available is False

    def test_available_with_tokens(self) -> None:
        adapter = _make_adapter(
            config=_make_config(bot_token="xoxb-test", app_token="xapp-test")
        )
        assert adapter.available is True


# ===========================================================================
# TestSlackAdapterInbound
# ===========================================================================


class TestSlackAdapterInbound:
    async def test_handle_mention_creates_conversation(self) -> None:
        """@mention creates a new conversation and calls conductor.handle_message."""
        conductor = AsyncMock()
        conductor.handle_message = AsyncMock(return_value="response text")
        store = AsyncMock()
        store.list_slack_threads = AsyncMock(return_value=[])
        store.create_slack_thread = AsyncMock(return_value={})
        store.update_slack_thread_progress = AsyncMock()

        adapter = _make_adapter(conductor=conductor, store=store)
        client = _mock_client()

        event = {
            "text": "<@U123BOT> hello world",
            "channel": "C123",
            "ts": "1111.2222",
            "user": "U456USER",
        }
        say = AsyncMock()

        await adapter._handle_mention_or_dm(event, say, client)

        # Conductor should be called with cleaned text
        conductor.handle_message.assert_called_once()
        call_args = conductor.handle_message.call_args
        assert call_args[0][1] == "hello world"  # cleaned text
        assert call_args[1]["user_id"] == "U456USER"

        # Store should create a mapping
        store.create_slack_thread.assert_called_once()

        # Reaction should be added then updated to checkmark
        client.reactions_add.assert_any_call(
            channel="C123", timestamp="1111.2222", name="hourglass_flowing_sand"
        )
        client.reactions_add.assert_any_call(
            channel="C123", timestamp="1111.2222", name="white_check_mark"
        )

    async def test_handle_mention_reuses_thread(self) -> None:
        """Existing thread mapping reuses conversation_id."""
        conductor = AsyncMock()
        conductor.handle_message = AsyncMock(return_value="ok")
        store = AsyncMock()
        store.list_slack_threads = AsyncMock(return_value=[])
        store.create_slack_thread = AsyncMock(return_value={})
        store.update_slack_thread_progress = AsyncMock()

        adapter = _make_adapter(conductor=conductor, store=store)
        client = _mock_client()

        # Pre-populate mapping
        adapter._thread_to_conv[("C123", "1111.0000")] = "existing-conv-id"
        adapter._conv_to_thread["existing-conv-id"] = ("C123", "1111.0000")

        event = {
            "text": "<@U123BOT> follow-up",
            "channel": "C123",
            "thread_ts": "1111.0000",
            "ts": "1111.3333",
            "user": "U456USER",
        }

        await adapter._handle_mention_or_dm(event, AsyncMock(), client)

        # Should NOT create a new mapping
        store.create_slack_thread.assert_not_called()

        # Conductor should be called with existing conversation_id
        call_args = conductor.handle_message.call_args
        assert call_args[0][0] == "existing-conv-id"

    async def test_handle_approve_action(self) -> None:
        """Approve button calls ApprovalManager.approve."""
        approval = AsyncMock()
        approval.approve = AsyncMock()
        adapter = _make_adapter(approval=approval)
        client = _mock_client()

        body = {
            "actions": [{"value": "task-123"}],
            "user": {"name": "testuser"},
            "channel": {"id": "C123"},
            "message": {"ts": "9999.0000"},
        }
        ack = AsyncMock()

        await adapter._handle_approve_action(ack, body, client)

        ack.assert_called_once()
        approval.approve.assert_called_once_with("task-123")
        # Message should be updated
        client.chat_update.assert_called_once()

    async def test_handle_reject_opens_modal(self) -> None:
        """Reject button opens a modal via views_open."""
        adapter = _make_adapter()
        client = _mock_client()

        body = {
            "actions": [{"value": "task-456"}],
            "trigger_id": "trigger-abc",
        }
        ack = AsyncMock()

        await adapter._handle_reject_action(ack, body, client)

        ack.assert_called_once()
        client.views_open.assert_called_once()
        call_kwargs = client.views_open.call_args[1]
        assert call_kwargs["trigger_id"] == "trigger-abc"
        view = call_kwargs["view"]
        assert view["callback_id"] == "maestro_reject_submit"
        assert view["private_metadata"] == "task-456"


# ===========================================================================
# TestSlackAdapterOutbound
# ===========================================================================


class TestSlackAdapterOutbound:
    async def test_task_created_sends_notification(self) -> None:
        """task.created event posts to the configured channel."""
        adapter = _make_adapter()
        client = _mock_client()

        # Inject a mock app with client
        adapter._app = MagicMock()
        adapter._app.client = client

        payload = {
            "task_id": "t-001",
            "title": "Write blog post",
            "agent": "writer",
            "type": "content",
        }

        await adapter._on_task_event("task.created", payload)

        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "#maestro-ops"
        blocks = call_kwargs["blocks"]
        text = blocks[0]["text"]["text"]
        assert "Write blog post" in text
        assert "t-001" in text

    async def test_task_completed_sends_notification(self) -> None:
        """task.completed event posts completion notification."""
        store = AsyncMock()
        store.list_slack_threads = AsyncMock(return_value=[])

        # Mock get_task to return a task-like object
        mock_task = MagicMock()
        mock_task.title = "Write blog post"
        store.get_task = AsyncMock(return_value=mock_task)
        store.get_task_slack_notification = AsyncMock(return_value=None)

        adapter = _make_adapter(store=store)
        client = _mock_client()
        adapter._app = MagicMock()
        adapter._app.client = client

        await adapter._on_task_event("task.completed", {"task_id": "t-001"})

        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        blocks = call_kwargs["blocks"]
        text = blocks[0]["text"]["text"]
        assert "Completed" in text
        assert "t-001" in text

    async def test_approval_submitted_sends_buttons(self) -> None:
        """approval.submitted event posts message with action buttons."""
        store = AsyncMock()
        store.list_slack_threads = AsyncMock(return_value=[])
        mock_task = MagicMock()
        mock_task.title = "Review content"
        mock_task.agent = "writer"
        store.get_task = AsyncMock(return_value=mock_task)
        store.get_approval_by_task = AsyncMock(
            return_value={"draft_json": "Some draft content"}
        )

        adapter = _make_adapter(store=store)
        client = _mock_client()
        adapter._app = MagicMock()
        adapter._app.client = client

        await adapter._on_approval_event(
            "approval.submitted",
            {"task_id": "t-002", "approval_id": "a-001"},
        )

        client.chat_postMessage.assert_called_once()
        call_kwargs = client.chat_postMessage.call_args[1]
        blocks = call_kwargs["blocks"]

        # Should have action buttons
        action_block = blocks[1]
        assert action_block["type"] == "actions"
        action_ids = [el["action_id"] for el in action_block["elements"]]
        assert "maestro_approve" in action_ids
        assert "maestro_reject" in action_ids
        assert "maestro_revise" in action_ids


# ===========================================================================
# TestSlackAdapterProgress
# ===========================================================================


class TestSlackAdapterProgress:
    async def test_progress_tool_use_updates_message(self) -> None:
        """tool_use stream event triggers immediate chat.update."""
        adapter = _make_adapter()
        client = _mock_client()
        adapter._app = MagicMock()
        adapter._app.client = client

        # Set up mapping
        conv_id = "conv-001"
        adapter._conv_to_thread[conv_id] = ("C123", "1111.0000")
        adapter._progress_msg_ts[conv_id] = "msg-ts-001"

        payload = {
            "conversation_id": conv_id,
            "type": "tool_use",
            "tool_name": "Read",
        }

        await adapter._on_conductor_stream("conductor.stream", payload)

        client.chat_update.assert_called_once()
        call_kwargs = client.chat_update.call_args[1]
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["ts"] == "msg-ts-001"
        assert "Read" in call_kwargs["text"]

    async def test_progress_done_replaces_with_final(self) -> None:
        """done stream event replaces progress message with final answer."""
        adapter = _make_adapter()
        client = _mock_client()
        adapter._app = MagicMock()
        adapter._app.client = client

        conv_id = "conv-002"
        adapter._conv_to_thread[conv_id] = ("C123", "1111.0000")
        adapter._progress_msg_ts[conv_id] = "msg-ts-002"
        adapter._progress_last_update[conv_id] = 100.0

        payload = {
            "conversation_id": conv_id,
            "type": "done",
            "text": "Here is the final answer.",
        }

        await adapter._on_conductor_stream("conductor.stream", payload)

        client.chat_update.assert_called_once()
        call_kwargs = client.chat_update.call_args[1]
        assert call_kwargs["text"] == "Here is the final answer."

        # Throttle state should be cleaned up
        assert conv_id not in adapter._progress_last_update

    async def test_progress_ignores_unmapped_conversation(self) -> None:
        """No update for conversations that did not originate from Slack."""
        adapter = _make_adapter()
        client = _mock_client()
        adapter._app = MagicMock()
        adapter._app.client = client

        payload = {
            "conversation_id": "web-only-conv",
            "type": "text",
            "text": "some progress",
        }

        await adapter._on_conductor_stream("conductor.stream", payload)

        client.chat_update.assert_not_called()

    async def test_progress_text_throttled(self) -> None:
        """text events are throttled to 4-second intervals."""
        adapter = _make_adapter()
        client = _mock_client()
        adapter._app = MagicMock()
        adapter._app.client = client

        conv_id = "conv-003"
        adapter._conv_to_thread[conv_id] = ("C123", "1111.0000")
        adapter._progress_msg_ts[conv_id] = "msg-ts-003"

        # Set last update to "now" (should be throttled)
        adapter._progress_last_update[conv_id] = time.monotonic()

        payload = {
            "conversation_id": conv_id,
            "type": "text",
            "text": "thinking...",
        }

        await adapter._on_conductor_stream("conductor.stream", payload)

        # Should NOT update because throttled
        client.chat_update.assert_not_called()


# ===========================================================================
# Block Kit formatting tests
# ===========================================================================


class TestBlockKitFormatting:
    def test_build_reject_modal(self) -> None:
        modal = _build_reject_modal("task-x")
        assert modal["callback_id"] == "maestro_reject_submit"
        assert modal["private_metadata"] == "task-x"
        assert modal["type"] == "modal"

    def test_build_revise_modal(self) -> None:
        modal = _build_revise_modal("task-y")
        assert modal["callback_id"] == "maestro_revise_submit"
        assert modal["private_metadata"] == "task-y"

    def test_format_approval_done(self) -> None:
        blocks = _format_approval_done("t1", "alice", "approved")
        assert len(blocks) == 1
        text = blocks[0]["text"]["text"]
        assert "Approved" in text
        assert "alice" in text

    def test_format_task_created(self) -> None:
        blocks = _format_task_created("t1", "My Task", "writer", "content")
        text = blocks[0]["text"]["text"]
        assert "My Task" in text
        assert "writer" in text

    def test_format_task_completed(self) -> None:
        blocks = _format_task_completed("t1", "Done Task")
        text = blocks[0]["text"]["text"]
        assert "Completed" in text
        assert "Done Task" in text

    def test_format_task_failed(self) -> None:
        blocks = _format_task_failed("t1", "Bad Task", "timeout error")
        text = blocks[0]["text"]["text"]
        assert "Failed" in text
        assert "timeout error" in text

    def test_format_task_failed_no_error(self) -> None:
        blocks = _format_task_failed("t1", "Bad Task", None)
        text = blocks[0]["text"]["text"]
        assert "Failed" in text
        assert "```" not in text

    def test_format_approval_request(self) -> None:
        blocks = _format_approval_request("t1", "Review This", "writer", "draft text")
        assert len(blocks) == 2
        # First block: info
        assert "Review This" in blocks[0]["text"]["text"]
        # Second block: actions
        assert blocks[1]["type"] == "actions"
        action_ids = [el["action_id"] for el in blocks[1]["elements"]]
        assert "maestro_approve" in action_ids
        assert "maestro_reject" in action_ids
        assert "maestro_revise" in action_ids
