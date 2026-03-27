"""
Conductor (지휘자) Agent — conversational system management interface.

The ConductorAgent accepts natural-language messages from users and drives the
Claude CLI via AgentRunner to fulfil them.  It streams results back through
the EventBus as ``conductor.stream`` events.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from maestro.config import MaestroConfig
from maestro.events import EventBus
from maestro.models import Task
from maestro.runner import AgentRunner, TaskResult
from maestro.store import Store

logger = logging.getLogger("maestro.conductor")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SESSION_ROTATION_THRESHOLD = 30  # start new session after this many messages
_PER_MESSAGE_BUDGET_USD = 1.0  # budget cap per single message exchange


class ConductorAgent:
    """Conductor (지휘자) agent — conversational system management interface."""

    def __init__(
        self,
        store: Store,
        bus: EventBus,
        config: MaestroConfig,
        base_path: Path,
    ) -> None:
        self._store = store
        self._bus = bus
        self._config = config
        self._base_path = Path(base_path) if isinstance(base_path, str) else base_path
        self._runner = AgentRunner()

        # Concurrency: one Claude CLI call per conversation
        self._active_runs: dict[str, asyncio.Task[None]] = {}
        # Queue of pending messages per conversation
        self._queues: dict[
            str, asyncio.Queue[tuple[str, str, asyncio.Future[str]]]
        ] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        conversation_id: str,
        user_message: str,
        user_id: str = "default",
    ) -> str:
        """Process a user message.  Streams response via EventBus.  Returns message_id.

        If the conversation already has an active Claude CLI run, the message
        is queued and processed after the current run finishes.
        """
        # If there is already an active run for this conversation, queue it
        if (
            conversation_id in self._active_runs
            and not self._active_runs[conversation_id].done()
        ):
            if conversation_id not in self._queues:
                self._queues[conversation_id] = asyncio.Queue()
            fut: asyncio.Future[str] = asyncio.get_event_loop().create_future()
            await self._queues[conversation_id].put((user_message, user_id, fut))
            return await fut

        return await self._run_message(conversation_id, user_message, user_id)

    # ------------------------------------------------------------------
    # Internal: run a single message through the CLI
    # ------------------------------------------------------------------

    async def _run_message(
        self,
        conversation_id: str,
        user_message: str,
        user_id: str,
    ) -> str:
        """Execute one message exchange end-to-end."""

        # 1. Get or create conversation
        conv = await self._store.get_conversation(conversation_id)
        if conv is None:
            conv = await self._store.create_conversation(
                id=conversation_id, user_id=user_id
            )

        # 2. Save user message
        msg_id = uuid.uuid4().hex[:12]
        await self._store.add_message(
            id=msg_id,
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )

        # 3. Build system prompt
        system_prompt = await self._build_system_prompt(user_id)

        # 4. Create ephemeral Task (NOT saved to DB)
        ephemeral_task = Task(
            id=msg_id,
            type="conductor",
            title="Conductor chat",
            instruction=user_message,
            budget_usd=_PER_MESSAGE_BUDGET_USD,
        )

        # 5. Prepare on_event callback
        assistant_message_id = uuid.uuid4().hex[:12]

        async def on_event(event: dict) -> None:
            await self._process_stream_event(
                conversation_id, assistant_message_id, event
            )

        # 6. Determine execute vs resume
        session_id = conv.get("session_id")
        message_count = conv.get("message_count", 0)

        # Session rotation: if messages exceed threshold, start fresh
        if message_count > _SESSION_ROTATION_THRESHOLD:
            session_id = None

        cwd = self._base_path

        # Pass daemon connection info as env vars for MCP servers
        agent_env = self._build_agent_env()

        # Wrap execution in an asyncio.Task for concurrency tracking
        result: TaskResult
        if session_id:
            result = await self._runner.resume(
                ephemeral_task,
                session_id,
                user_message,
                cwd,
                on_event=on_event,
                env=agent_env,
                permission_mode="bypass",
            )
        else:
            result = await self._runner.execute(
                ephemeral_task,
                cwd=cwd,
                max_turns=50,
                on_event=on_event,
                system_prompt=system_prompt,
                permission_mode="bypass",
                env=agent_env,
            )

        # 7. Save assistant response message
        assistant_content = ""
        if result.result:
            assistant_content = (
                result.result if isinstance(result.result, str) else str(result.result)
            )
        elif result.error:
            assistant_content = f"[Error] {result.error}"

        await self._store.add_message(
            id=assistant_message_id,
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            cost_usd=result.cost_usd,
        )

        # 8. Update conversation session_id and cost
        new_session_id = result.session_id or session_id
        if new_session_id:
            await self._store.update_conversation_session(
                conversation_id, session_id=new_session_id
            )
        if result.cost_usd > 0:
            await self._store.update_conversation_cost(conversation_id, result.cost_usd)

        # 9. Auto-set title from first user message if empty
        if not conv.get("title"):
            title = user_message[:60].strip()
            if len(user_message) > 60:
                title += "..."
            await self._store.update_conversation_session(
                conversation_id, session_id=new_session_id or ""
            )
            # Use a direct update for title
            async with self._store._conn() as db:
                await db.execute(
                    "UPDATE conductor_conversations SET title = ? WHERE id = ? AND title = ''",
                    (title, conversation_id),
                )
                await db.commit()

        # 10. Process queued messages
        await self._drain_queue(conversation_id)

        return assistant_message_id

    # ------------------------------------------------------------------
    # Queue processing
    # ------------------------------------------------------------------

    async def _drain_queue(self, conversation_id: str) -> None:
        """Process any queued messages for this conversation."""
        queue = self._queues.get(conversation_id)
        if not queue or queue.empty():
            return

        user_message, user_id, fut = await queue.get()
        try:
            result = await self._run_message(conversation_id, user_message, user_id)
            fut.set_result(result)
        except Exception as exc:
            fut.set_exception(exc)

    # ------------------------------------------------------------------
    # Stream event processing (no throttling)
    # ------------------------------------------------------------------

    async def _process_stream_event(
        self, conversation_id: str, message_id: str, event: dict
    ) -> None:
        """Parse Claude CLI stream-json events and emit to EventBus.

        Unlike AgentLogProcessor (which throttles at 0.5s), the conductor
        forwards every event immediately for real-time chat UX.
        """
        event_type = event.get("type")

        if event_type == "assistant":
            message = event.get("message", {})
            for block in message.get("content", []):
                block_type = block.get("type")

                if block_type == "text":
                    await self._bus.emit(
                        "conductor.stream",
                        {
                            "conversation_id": conversation_id,
                            "message_id": message_id,
                            "chunk_type": "text",
                            "content": block.get("text", ""),
                        },
                    )

                elif block_type == "tool_use":
                    await self._bus.emit(
                        "conductor.stream",
                        {
                            "conversation_id": conversation_id,
                            "message_id": message_id,
                            "chunk_type": "tool_use",
                            "tool_name": block.get("name", ""),
                            "tool_input": block.get("input", {}),
                        },
                    )

                elif block_type == "tool_result":
                    await self._bus.emit(
                        "conductor.stream",
                        {
                            "conversation_id": conversation_id,
                            "message_id": message_id,
                            "chunk_type": "tool_result",
                            "content": str(block.get("content", "")),
                        },
                    )

        elif event_type == "result":
            await self._bus.emit(
                "conductor.stream",
                {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "chunk_type": "done",
                    "cost_usd": float(event.get("total_cost_usd", 0.0)),
                    "is_error": event.get("is_error", False),
                },
            )

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    async def _build_system_prompt(self, user_id: str) -> str:
        """Build system prompt using 2-tier hierarchy (project override -> package builtin)."""
        prompt_parts: list[str] = []

        # Tier 2: project override (.maestro/prompts/conductor.md)
        override_path = self._base_path / ".maestro" / "prompts" / "conductor.md"
        if override_path.exists():
            prompt_parts.append(override_path.read_text())
            return "\n\n".join(prompt_parts)

        # Tier 1: package builtin
        import importlib.resources

        try:
            builtin = importlib.resources.files("maestro.prompts") / "conductor.md"
            if builtin.is_file():
                prompt_parts.append(builtin.read_text())
        except (FileNotFoundError, TypeError):
            pass

        if not prompt_parts:
            # Fallback minimal prompt
            prompt_parts.append(
                "You are the Conductor agent for the Maestro orchestration system. "
                "Help the user manage goals, tasks, and system operations."
            )

        return "\n\n".join(prompt_parts)

    # ------------------------------------------------------------------
    # Agent env vars
    # ------------------------------------------------------------------

    def _build_agent_env(self) -> dict[str, str]:
        """Build environment variables for the Claude CLI subprocess."""
        env: dict[str, str] = {
            "MAESTRO_BASE_PATH": str(self._base_path),
            "MAESTRO_DB_PATH": self._store._db_path,
        }
        # Port is injected by the daemon after start()
        if hasattr(self, "_daemon_port"):
            env["MAESTRO_DAEMON_PORT"] = str(self._daemon_port)
        return env

    def set_daemon_port(self, port: int) -> None:
        """Called by Daemon.start() to inject the API port."""
        self._daemon_port = port
