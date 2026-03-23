"""
Agent Runner for Maestro.

Manages subprocess execution of the Claude CLI, streams output as newline-
delimited JSON, parses events, and returns TaskResult instances.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from maestro.models import Task, TaskResult

logger = logging.getLogger(__name__)


def parse_stream_event(line: str) -> dict | None:
    """Parse a single line of stream-json output from the Claude CLI.

    Parameters
    ----------
    line:
        A raw text line from stdout. May be empty, whitespace-only, or
        contain a JSON object.

    Returns
    -------
    dict | None
        The parsed event dict, or ``None`` if the line is empty, whitespace-
        only, unparseable, or is not a JSON object.
    """
    stripped = line.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    # We only accept JSON objects (dicts), not arrays or scalars.
    if not isinstance(parsed, dict):
        return None
    return parsed


class AgentRunner:
    """Executes tasks by spawning the Claude CLI as a subprocess.

    The runner drives the Claude CLI with ``--output-format stream-json`` so
    that each line of stdout is a self-contained JSON event. It captures:

    - ``session_id`` from the initial ``{"type":"system", ...}`` event
    - ``cost_usd`` from the terminal ``{"type":"result", ...}`` event
    """

    # ------------------------------------------------------------------
    # Argument builders (pure functions – easy to unit-test)
    # ------------------------------------------------------------------

    def _build_execute_args(
        self,
        task: Task,
        allowed_tools: list[str],
        max_turns: int,
    ) -> list[str]:
        """Build the argument list for a fresh Claude CLI execution.

        Parameters
        ----------
        task:
            The task whose ``instruction`` and ``budget_usd`` drive the call.
        allowed_tools:
            Tool names to pass via ``--allowedTools`` (joined with commas).
        max_turns:
            Maximum number of agentic turns to allow.

        Returns
        -------
        list[str]
            Complete argv suitable for ``asyncio.create_subprocess_exec``.
        """
        return [
            "claude",
            "-p", task.instruction,
            "--output-format", "stream-json",
            "--allowedTools", ",".join(allowed_tools),
            "--max-turns", str(max_turns),
            "--max-budget-usd", str(task.budget_usd),
        ]

    def _build_resume_args(self, session_id: str, instruction: str) -> list[str]:
        """Build the argument list for resuming an existing Claude CLI session.

        Parameters
        ----------
        session_id:
            The UUID of the session to resume (captured from a previous run).
        instruction:
            The follow-up prompt to inject into the resumed session.

        Returns
        -------
        list[str]
            Complete argv suitable for ``asyncio.create_subprocess_exec``.
        """
        return [
            "claude",
            "--resume", session_id,
            "-p", instruction,
            "--output-format", "stream-json",
        ]

    # ------------------------------------------------------------------
    # Internal streaming helper
    # ------------------------------------------------------------------

    async def _stream(
        self,
        args: list[str],
        workspace_path: Path,
    ) -> TaskResult:
        """Spawn a subprocess, stream its stdout, and collect results.

        Parameters
        ----------
        args:
            The complete argv to pass to ``create_subprocess_exec``.
        workspace_path:
            The working directory for the spawned process.

        Returns
        -------
        TaskResult
            Populated with ``session_id``, ``cost_usd``, ``success``, and any
            ``error`` captured from the stream.
        """
        session_id: Optional[str] = None
        cost_usd: float = 0.0
        success: bool = False
        error: Optional[str] = None
        result_json: Optional[object] = None

        try:
            # Use create_subprocess_exec (not shell=True) to avoid injection.
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace_path),
            )

            assert proc.stdout is not None  # PIPE guarantees this

            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace")
                event = parse_stream_event(line)
                if event is None:
                    continue

                event_type = event.get("type")

                if event_type == "system":
                    if "session_id" in event:
                        session_id = event["session_id"]
                        logger.debug("Captured session_id=%s", session_id)

                elif event_type == "result":
                    cost_usd = float(event.get("cost_usd") or 0.0)
                    is_error = bool(event.get("is_error", False))
                    success = not is_error
                    if is_error:
                        error = event.get("error") or "Unknown error from Claude CLI"
                    result_json = event.get("result")
                    logger.debug(
                        "Result event: success=%s cost_usd=%s", success, cost_usd
                    )

            await proc.wait()

            if proc.returncode != 0 and not success:
                stderr_bytes = await proc.stderr.read() if proc.stderr else b""
                stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                error = error or f"Process exited with code {proc.returncode}: {stderr_text}"
                success = False

        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error running Claude CLI: %s", exc)
            error = str(exc)
            success = False

        return TaskResult(
            task_id="",  # Filled in by callers
            success=success,
            session_id=session_id,
            result_json=result_json,
            error=error,
            cost_usd=cost_usd,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def execute(
        self,
        task: Task,
        workspace_path: Path,
        allowed_tools: Optional[list[str]] = None,
        max_turns: int = 20,
    ) -> TaskResult:
        """Execute a task from scratch using the Claude CLI.

        Parameters
        ----------
        task:
            The task to execute.
        workspace_path:
            Working directory for the Claude subprocess.
        allowed_tools:
            Optional list of tool names.  Defaults to an empty list.
        max_turns:
            Maximum agentic turns.  Defaults to 20.

        Returns
        -------
        TaskResult
        """
        if allowed_tools is None:
            allowed_tools = []

        args = self._build_execute_args(task, allowed_tools, max_turns)
        logger.info("Executing task %s: %s", task.id, args)

        result = await self._stream(args, workspace_path)
        result.task_id = task.id
        return result

    async def resume(
        self,
        task: Task,
        session_id: str,
        instruction: str,
        workspace_path: Path,
    ) -> TaskResult:
        """Resume an existing Claude CLI session for a task.

        Parameters
        ----------
        task:
            The task being continued.
        session_id:
            The Claude CLI session UUID from the previous run.
        instruction:
            The follow-up prompt to send.
        workspace_path:
            Working directory for the Claude subprocess.

        Returns
        -------
        TaskResult
        """
        args = self._build_resume_args(session_id, instruction)
        logger.info("Resuming task %s (session=%s): %s", task.id, session_id, args)

        result = await self._stream(args, workspace_path)
        result.task_id = task.id
        return result
