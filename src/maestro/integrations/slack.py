"""
Slack integration adapter for Maestro — inbound events + outbound notifications.

Uses slack-bolt (Socket Mode) for bidirectional communication:
- Inbound: @mentions, DMs, approval button actions
- Outbound: task notifications, approval requests, conductor progress
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from typing import Any

try:
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp
except ImportError:
    AsyncApp = None  # type: ignore[assignment,misc]
    AsyncSocketModeHandler = None  # type: ignore[assignment,misc]

try:
    from markdown_to_mrkdwn import SlackMarkdownConverter

    _md_converter = SlackMarkdownConverter()
except Exception:
    _md_converter = None  # type: ignore[assignment]

from maestro.config import SlackConfig

logger = logging.getLogger(__name__)

# Progress text throttle interval (seconds)
_PROGRESS_THROTTLE_SECS = 4.0

# Slack message character limit (official limit is 40k, use 3500 for readability)
_SLACK_MSG_LIMIT = 3500


def _to_mrkdwn(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn format."""
    if _md_converter is not None:
        return str(_md_converter.convert(text))
    return text


def _split_message(text: str, limit: int = _SLACK_MSG_LIMIT) -> list[str]:
    """Split long text into multiple Slack-friendly chunks.

    Splits on paragraph boundaries (double newline) first, then single
    newlines, to keep messages readable.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        # Try to split at paragraph boundary
        split_at = remaining.rfind("\n\n", 0, limit)
        if split_at == -1:
            # Fall back to single newline
            split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            # Fall back to space
            split_at = remaining.rfind(" ", 0, limit)
        if split_at == -1:
            # Hard split
            split_at = limit

        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()

    return chunks or [text]


# ---------------------------------------------------------------------------
# Block Kit formatting helpers (module-level)
# ---------------------------------------------------------------------------


def _build_reject_modal(task_id: str) -> dict[str, Any]:
    """Build a Slack modal view for rejection with a reason input."""
    return {
        "type": "modal",
        "callback_id": "maestro_reject_submit",
        "private_metadata": task_id,
        "title": {"type": "plain_text", "text": "Reject Task"},
        "submit": {"type": "plain_text", "text": "Reject"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "reason_block",
                "label": {"type": "plain_text", "text": "Rejection reason"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "reason_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Why is this being rejected?",
                    },
                },
            }
        ],
    }


def _build_revise_modal(task_id: str) -> dict[str, Any]:
    """Build a Slack modal view for revision with notes input."""
    return {
        "type": "modal",
        "callback_id": "maestro_revise_submit",
        "private_metadata": task_id,
        "title": {"type": "plain_text", "text": "Request Revision"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "notes_block",
                "label": {"type": "plain_text", "text": "Revision notes"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "notes_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "What changes are needed?",
                    },
                },
            }
        ],
    }


def _format_approval_done(
    task_id: str, user_name: str, action: str
) -> list[dict[str, Any]]:
    """Format blocks for a completed approval action."""
    emoji = {"approved": "\u2705", "rejected": "\u274c", "revised": "\u270f\ufe0f"}.get(
        action, "\u2754"
    )
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{action.title()}* by {user_name}\nTask: `{task_id}`",
            },
        }
    ]


def _format_task_created(
    task_id: str, title: str, agent: str, task_type: str
) -> list[dict[str, Any]]:
    """Format blocks for a task.created notification."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"\U0001f4cb *New Task Created*\n"
                    f"*Title:* {title}\n"
                    f"*ID:* `{task_id}`\n"
                    f"*Agent:* {agent} | *Type:* {task_type}"
                ),
            },
        }
    ]


def _format_task_completed(task_id: str, title: str) -> list[dict[str, Any]]:
    """Format blocks for a task.completed notification."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"\u2705 *Task Completed*\n*Title:* {title}\n*ID:* `{task_id}`",
            },
        }
    ]


def _format_task_failed(
    task_id: str, title: str, error: str | None
) -> list[dict[str, Any]]:
    """Format blocks for a task.failed notification."""
    err_text = f"\n*Error:* ```{error}```" if error else ""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"\u274c *Task Failed*\n*Title:* {title}\n"
                    f"*ID:* `{task_id}`{err_text}"
                ),
            },
        }
    ]


def _format_approval_request(
    task_id: str, title: str, agent: str, draft: str
) -> list[dict[str, Any]]:
    """Format blocks for an approval request with action buttons."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"\U0001f514 *Approval Required*\n"
                    f"*Task:* {title}\n"
                    f"*ID:* `{task_id}` | *Agent:* {agent}\n"
                    f"*Draft:*\n```{draft[:500]}```"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "\u2705 Approve"},
                    "style": "primary",
                    "action_id": "maestro_approve",
                    "value": task_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "\u274c Reject"},
                    "style": "danger",
                    "action_id": "maestro_reject",
                    "value": task_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "\u270f\ufe0f Revise"},
                    "action_id": "maestro_revise",
                    "value": task_id,
                },
            ],
        },
    ]


# ---------------------------------------------------------------------------
# SlackAdapter
# ---------------------------------------------------------------------------


class SlackAdapter:
    """Slack integration adapter — inbound events + outbound notifications."""

    def __init__(
        self,
        store: Any,
        bus: Any,
        conductor: Any,
        approval_manager: Any,
        config: SlackConfig,
    ) -> None:
        self._store = store
        self._bus = bus
        self._conductor = conductor
        self._approval = approval_manager
        self._config = config

        # In-memory caches: thread <-> conversation mapping
        # (channel_id, thread_ts) -> conversation_id
        self._thread_to_conv: dict[tuple[str, str], str] = {}
        # conversation_id -> (channel_id, thread_ts)
        self._conv_to_thread: dict[str, tuple[str, str]] = {}

        # Progress throttle state: conversation_id -> last_update_monotonic
        self._progress_last_update: dict[str, float] = {}
        # Progress message ts: conversation_id -> progress_msg_ts
        self._progress_msg_ts: dict[str, str] = {}
        # Accumulated text for final message: conversation_id -> text
        self._accumulated_text: dict[str, str] = {}

        # Slack-bolt app & socket handler (created on start)
        self._app: Any | None = None
        self._socket_handler: Any | None = None

    @property
    def available(self) -> bool:
        """True if both bot_token and app_token are set."""
        return bool(self._config.bot_token and self._config.app_token)

    # ------------------------------------------------------------------
    # LIFECYCLE
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start slack-bolt app in Socket Mode."""
        if not self.available:
            logger.warning("SlackAdapter: missing bot_token or app_token, not starting")
            return

        if AsyncApp is None:
            logger.warning("SlackAdapter: slack-bolt not installed, not starting")
            return

        self._app = AsyncApp(token=self._config.bot_token)
        self._register_handlers()

        # Register EventBus listeners
        self._bus.on("task.*", self._on_task_event)
        self._bus.on("approval.*", self._on_approval_event)
        self._bus.on("conductor.stream", self._on_conductor_stream)

        # Restore thread mappings from DB
        await self._restore_mappings()

        # Start socket mode
        self._socket_handler = AsyncSocketModeHandler(self._app, self._config.app_token)
        self._socket_task = asyncio.create_task(self._socket_handler.start_async())
        logger.info("SlackAdapter started in Socket Mode")

    async def stop(self) -> None:
        """Stop socket handler and unregister EventBus listeners."""
        if self._socket_handler is not None:
            await self._socket_handler.close_async()
            self._socket_handler = None
        if (
            hasattr(self, "_socket_task")
            and self._socket_task
            and not self._socket_task.done()
        ):
            self._socket_task.cancel()
            self._socket_task = None  # type: ignore[assignment]

        self._bus.off("task.*", self._on_task_event)
        self._bus.off("approval.*", self._on_approval_event)
        self._bus.off("conductor.stream", self._on_conductor_stream)
        logger.info("SlackAdapter stopped")

    # ------------------------------------------------------------------
    # MAPPING
    # ------------------------------------------------------------------

    async def _restore_mappings(self) -> None:
        """Restore thread <-> conversation mappings from DB."""
        threads = await self._store.list_slack_threads()
        for t in threads:
            key = (t["slack_channel_id"], t["slack_thread_ts"])
            conv_id = t["conversation_id"]
            self._thread_to_conv[key] = conv_id
            self._conv_to_thread[conv_id] = key
            if t.get("progress_msg_ts"):
                self._progress_msg_ts[conv_id] = t["progress_msg_ts"]

    async def _create_mapping(
        self,
        channel_id: str,
        thread_ts: str,
        conversation_id: str,
        user_id: str,
    ) -> None:
        """Create new mapping in DB + memory."""
        await self._store.create_slack_thread(
            channel_id, thread_ts, conversation_id, user_id
        )
        key = (channel_id, thread_ts)
        self._thread_to_conv[key] = conversation_id
        self._conv_to_thread[conversation_id] = key

    # ------------------------------------------------------------------
    # INBOUND HANDLERS
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        """Register all slack event/action handlers on bolt app."""
        if self._app is None:
            return

        self._app.event("app_mention")(self._on_app_mention)
        self._app.event("message")(self._on_direct_message)

        # Approval actions
        self._app.action("maestro_approve")(self._handle_approve_action)
        self._app.action("maestro_reject")(self._handle_reject_action)
        self._app.action("maestro_revise")(self._handle_revise_action)

        # Modal submissions
        self._app.view("maestro_reject_submit")(self._handle_reject_submit)
        self._app.view("maestro_revise_submit")(self._handle_revise_submit)

    async def _on_app_mention(self, event: dict, say: Any, client: Any) -> None:
        """Handle @maestro mentions."""
        await self._handle_mention_or_dm(event, say, client)

    async def _on_direct_message(self, event: dict, say: Any, client: Any) -> None:
        """Handle DMs and thread replies to bot — ignore bot's own messages."""
        if event.get("bot_id") or event.get("subtype"):
            return

        # DMs: always handle
        if event.get("channel_type") == "im":
            await self._handle_mention_or_dm(event, say, client)
            return

        # Channel thread replies: handle if thread is already
        # mapped (ongoing conversation)
        thread_ts = event.get("thread_ts")
        if thread_ts:
            channel_id = event["channel"]
            key = (channel_id, thread_ts)
            if key in self._thread_to_conv:
                await self._handle_mention_or_dm(event, say, client)

    async def _handle_mention_or_dm(self, event: dict, say: Any, client: Any) -> None:
        """Unified handler for mentions and DMs.

        1. Clean bot mention from text
        2. Look up or create conversation mapping
        3. Add reaction + send progress message
        4. Call conductor.handle_message
        5. Update reaction on completion/error
        """
        text = event.get("text", "")
        # Strip bot mention tags
        text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()
        if not text:
            return

        channel_id = event["channel"]
        # Use thread_ts if in a thread, otherwise the message's own ts
        thread_ts = event.get("thread_ts") or event["ts"]
        user_id = event.get("user", "unknown")
        msg_ts = event["ts"]

        # Look up existing mapping
        key = (channel_id, thread_ts)
        conversation_id = self._thread_to_conv.get(key)

        if conversation_id is None:
            # Create new conversation
            conversation_id = uuid.uuid4().hex[:16]
            await self._create_mapping(channel_id, thread_ts, conversation_id, user_id)

        # Add hourglass reaction
        try:
            await client.reactions_add(
                channel=channel_id, timestamp=msg_ts, name="hourglass_flowing_sand"
            )
        except Exception:
            logger.debug("Failed to add reaction", exc_info=True)

        # Send progress message in thread
        try:
            progress_resp = await client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text="\u23f3 \ucc98\ub9ac \uc911...",
            )
            progress_msg_ts = progress_resp["ts"]
            self._progress_msg_ts[conversation_id] = progress_msg_ts
            await self._store.update_slack_thread_progress(
                channel_id, thread_ts, progress_msg_ts
            )
        except Exception:
            logger.debug("Failed to send progress message", exc_info=True)
            progress_msg_ts = None

        # Call conductor
        try:
            await self._conductor.handle_message(conversation_id, text, user_id=user_id)
            # Success: replace reaction with checkmark
            try:
                await client.reactions_remove(
                    channel=channel_id,
                    timestamp=msg_ts,
                    name="hourglass_flowing_sand",
                )
                await client.reactions_add(
                    channel=channel_id, timestamp=msg_ts, name="white_check_mark"
                )
            except Exception:
                logger.debug("Failed to update reaction", exc_info=True)
        except Exception as exc:
            logger.exception("Conductor handle_message failed")
            # Error: replace reaction with X
            try:
                await client.reactions_remove(
                    channel=channel_id,
                    timestamp=msg_ts,
                    name="hourglass_flowing_sand",
                )
                await client.reactions_add(
                    channel=channel_id, timestamp=msg_ts, name="x"
                )
            except Exception:
                logger.debug("Failed to update reaction", exc_info=True)

            # Send error message in thread
            try:
                await client.chat_postMessage(
                    channel=channel_id,
                    thread_ts=thread_ts,
                    text=f"\u274c Error: {exc}",
                )
            except Exception:
                logger.debug("Failed to send error message", exc_info=True)

    # ------------------------------------------------------------------
    # APPROVAL ACTIONS
    # ------------------------------------------------------------------

    async def _handle_approve_action(self, ack: Any, body: dict, client: Any) -> None:
        """Approve button pressed."""
        await ack()
        action = body["actions"][0]
        task_id = action["value"]
        user_name = body.get("user", {}).get("name", "unknown")

        try:
            await self._approval.approve(task_id)
            blocks = _format_approval_done(task_id, user_name, "approved")
            await client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                blocks=blocks,
                text=f"Approved by {user_name}",
            )
        except Exception:
            logger.exception("Failed to handle approve action for %s", task_id)

    async def _handle_reject_action(self, ack: Any, body: dict, client: Any) -> None:
        """Reject button pressed — open modal for reason."""
        await ack()
        action = body["actions"][0]
        task_id = action["value"]

        try:
            await client.views_open(
                trigger_id=body["trigger_id"],
                view=_build_reject_modal(task_id),
            )
        except Exception:
            logger.exception("Failed to open reject modal for %s", task_id)

    async def _handle_revise_action(self, ack: Any, body: dict, client: Any) -> None:
        """Revise button pressed — open modal for notes."""
        await ack()
        action = body["actions"][0]
        task_id = action["value"]

        try:
            await client.views_open(
                trigger_id=body["trigger_id"],
                view=_build_revise_modal(task_id),
            )
        except Exception:
            logger.exception("Failed to open revise modal for %s", task_id)

    async def _handle_reject_submit(
        self, ack: Any, body: dict, client: Any, view: dict
    ) -> None:
        """Modal submit for rejection."""
        await ack()
        task_id = view["private_metadata"]
        note = view["state"]["values"]["reason_block"]["reason_input"]["value"] or ""
        user_name = body.get("user", {}).get("name", "unknown")

        try:
            await self._approval.reject(task_id, note=note)
            logger.info("Task %s rejected by %s: %s", task_id, user_name, note)
        except Exception:
            logger.exception("Failed to reject task %s", task_id)

    async def _handle_revise_submit(
        self, ack: Any, body: dict, client: Any, view: dict
    ) -> None:
        """Modal submit for revision."""
        await ack()
        task_id = view["private_metadata"]
        note = view["state"]["values"]["notes_block"]["notes_input"]["value"] or ""
        user_name = body.get("user", {}).get("name", "unknown")

        try:
            await self._approval.revise(task_id, note=note)
            logger.info(
                "Task %s revision requested by %s: %s", task_id, user_name, note
            )
        except Exception:
            logger.exception("Failed to revise task %s", task_id)

    # ------------------------------------------------------------------
    # OUTBOUND: TASK EVENTS
    # ------------------------------------------------------------------

    async def _on_task_event(self, event_type: str, payload: dict) -> None:
        """EventBus handler for task.* events."""
        client = self._get_client()
        if client is None:
            return

        channel = self._config.channel
        task_id = payload.get("task_id", "")

        if event_type == "task.created":
            title = payload.get("title", "")
            agent = payload.get("agent", "default")
            task_type = payload.get("type", "")
            blocks = _format_task_created(task_id, title, agent, task_type)
            try:
                await client.chat_postMessage(
                    channel=channel, blocks=blocks, text=f"New task: {title}"
                )
            except Exception:
                logger.exception("Failed to send task.created notification")

        elif event_type == "task.completed":
            task = await self._store.get_task(task_id)
            title = task.title if task else task_id
            blocks = _format_task_completed(task_id, title)
            try:
                await client.chat_postMessage(
                    channel=channel, blocks=blocks, text=f"Task completed: {title}"
                )
            except Exception:
                logger.exception("Failed to send task.completed notification")

        elif event_type == "task.failed":
            task = await self._store.get_task(task_id)
            title = task.title if task else task_id
            error = payload.get("error")
            blocks = _format_task_failed(task_id, title, error)
            try:
                await client.chat_postMessage(
                    channel=channel, blocks=blocks, text=f"Task failed: {title}"
                )
            except Exception:
                logger.exception("Failed to send task.failed notification")

    # ------------------------------------------------------------------
    # OUTBOUND: APPROVAL EVENTS
    # ------------------------------------------------------------------

    async def _on_approval_event(self, event_type: str, payload: dict) -> None:
        """EventBus handler for approval.* events."""
        if event_type != "approval.submitted":
            return

        client = self._get_client()
        if client is None:
            return

        task_id = payload.get("task_id", "")
        task = await self._store.get_task(task_id)
        approval = await self._store.get_approval_by_task(task_id)

        title = task.title if task else task_id
        agent = task.agent if task else "unknown"
        draft = (approval or {}).get("draft_json", "") or ""

        blocks = _format_approval_request(task_id, title, agent, draft)
        try:
            await client.chat_postMessage(
                channel=self._config.channel,
                blocks=blocks,
                text=f"Approval required: {title}",
            )
        except Exception:
            logger.exception("Failed to send approval.submitted notification")

    # ------------------------------------------------------------------
    # OUTBOUND: CONDUCTOR PROGRESS (throttled)
    # ------------------------------------------------------------------

    async def _on_conductor_stream(self, event_type: str, payload: dict) -> None:
        """EventBus handler for conductor.stream events.

        - Only for Slack-originated conversations
        - tool_use: immediate update with tool summary
        - text: throttled update (4 second interval)
        - done: replace progress message with final answer
        """
        conversation_id = payload.get("conversation_id")
        if not conversation_id:
            return

        # Only handle conversations that originated from Slack
        thread_info = self._conv_to_thread.get(conversation_id)
        if thread_info is None:
            return

        channel_id, thread_ts = thread_info
        client = self._get_client()
        if client is None:
            return

        progress_msg_ts = self._progress_msg_ts.get(conversation_id)
        if not progress_msg_ts:
            return

        chunk_type = payload.get("type", payload.get("chunk_type", ""))

        if chunk_type == "tool_use":
            # Immediate update with tool summary
            tool_name = payload.get("tool_name", "tool")
            text = f"\U0001f527 Using {tool_name}..."
            try:
                await client.chat_update(
                    channel=channel_id,
                    ts=progress_msg_ts,
                    text=text,
                )
            except Exception:
                logger.debug("Failed to update progress (tool_use)", exc_info=True)

        elif chunk_type == "text":
            # Accumulate text for final message
            content = payload.get("content", "")
            self._accumulated_text[conversation_id] = content

            # Throttled update — show preview while processing
            now = time.monotonic()
            last = self._progress_last_update.get(conversation_id, 0.0)
            if now - last < _PROGRESS_THROTTLE_SECS:
                return

            self._progress_last_update[conversation_id] = now
            # Show first portion as preview during processing
            converted = _to_mrkdwn(content)
            preview = converted[:3000] + (
                "\n\n_typing…_" if len(converted) > 3000 else ""
            )
            try:
                await client.chat_update(
                    channel=channel_id,
                    ts=progress_msg_ts,
                    text=preview or "\u23f3 Processing...",
                )
            except Exception:
                logger.debug("Failed to update progress (text)", exc_info=True)

        elif chunk_type == "done":
            # Send final response — split into multiple messages if needed
            raw_text = (
                payload.get("text")
                or self._accumulated_text.pop(conversation_id, None)
                or "\u2705 Done"
            )
            self._accumulated_text.pop(conversation_id, None)
            final_text = _to_mrkdwn(raw_text)
            chunks = _split_message(final_text)

            # First chunk: update the progress message in-place
            try:
                await client.chat_update(
                    channel=channel_id,
                    ts=progress_msg_ts,
                    text=chunks[0],
                )
            except Exception:
                logger.debug("Failed to update progress (done)", exc_info=True)

            # Remaining chunks: post as new messages in thread
            for chunk in chunks[1:]:
                try:
                    await client.chat_postMessage(
                        channel=channel_id,
                        thread_ts=thread_ts,
                        text=chunk,
                    )
                except Exception:
                    logger.debug("Failed to send continuation message", exc_info=True)

            # Cleanup throttle state
            self._progress_last_update.pop(conversation_id, None)

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _get_client(self) -> Any | None:
        """Get Slack WebClient from bolt app."""
        if self._app is None:
            return None
        return self._app.client
