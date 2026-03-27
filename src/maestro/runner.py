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
        system_prompt: str | None = None,
        permission_mode: str = "bypass",
    ) -> list[str]:
        """Build the argument list for a fresh Claude CLI execution.

        Parameters
        ----------
        task:
            The task whose ``instruction`` and ``budget_usd`` drive the call.
        allowed_tools:
            Tool names to pass via ``--allowedTools`` (only used when
            ``permission_mode`` is ``"restricted"``).
        max_turns:
            Maximum number of agentic turns to allow.
        system_prompt:
            Optional system prompt to append via ``--append-system-prompt``.
        permission_mode:
            ``"bypass"`` uses ``--dangerously-skip-permissions`` (all tools).
            ``"restricted"`` uses ``--allowedTools`` whitelist.

        Returns
        -------
        list[str]
            Complete argv suitable for ``asyncio.create_subprocess_exec``.
        """
        args = [
            "claude",
            "-p",
            task.instruction,
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-budget-usd",
            str(task.budget_usd),
        ]
        if max_turns > 0:
            args += ["--max-turns", str(max_turns)]
        if permission_mode == "bypass":
            args.append("--dangerously-skip-permissions")
        else:
            args += ["--allowedTools", ",".join(allowed_tools)]
        if system_prompt is not None:
            args += ["--append-system-prompt", system_prompt]
        return args

    def _build_resume_args(
        self,
        session_id: str,
        instruction: str,
        permission_mode: str = "bypass",
        system_prompt: str | None = None,
    ) -> list[str]:
        """Build the argument list for resuming an existing Claude CLI session.

        Parameters
        ----------
        session_id:
            The UUID of the session to resume (captured from a previous run).
        instruction:
            The follow-up prompt to inject into the resumed session.
        permission_mode:
            Permission mode to apply (``"bypass"`` adds
            ``--dangerously-skip-permissions``).
        system_prompt:
            Optional system prompt to append via ``--append-system-prompt``.

        Returns
        -------
        list[str]
            Complete argv suitable for ``asyncio.create_subprocess_exec``.
        """
        args = [
            "claude",
            "--resume",
            session_id,
            "-p",
            instruction,
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if permission_mode == "bypass":
            args.append("--dangerously-skip-permissions")
        if system_prompt is not None:
            args += ["--append-system-prompt", system_prompt]
        return args

    # ------------------------------------------------------------------
    # Internal streaming helper
    # ------------------------------------------------------------------

    async def _stream(
        self,
        args: list[str],
        cwd: Path,
        on_event: Optional[callable] = None,
        env: Optional[dict[str, str]] = None,
    ) -> TaskResult:
        """Spawn a subprocess, stream its stdout, and collect results.

        Parameters
        ----------
        args:
            The complete argv to pass to ``create_subprocess_exec``.
        cwd:
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
        result_text: Optional[object] = None
        result_from_event: bool = False  # True when result event had a result field
        last_assistant_text: Optional[str] = None
        subtype: Optional[str] = None

        try:
            # Merge daemon env vars into the current environment
            proc_env = None
            if env:
                import os

                proc_env = {**os.environ, **env}

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
                env=proc_env,
            )

            assert proc.stdout is not None  # PIPE guarantees this

            # Read raw chunks and split by newline manually.
            # This avoids asyncio's readline buffer limit (default 64KB)
            # which can be exceeded by large stream-json events
            # (e.g. web page snapshots, resume context).
            buffer = b""
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    raw_line, buffer = buffer.split(b"\n", 1)
                    line = raw_line.decode("utf-8", errors="replace")
                    event = parse_stream_event(line)
                    if event is None:
                        continue

                    if on_event is not None:
                        try:
                            await on_event(event)
                        except Exception:
                            logger.debug("on_event callback failed", exc_info=True)

                    event_type = event.get("type")

                    if event_type == "system":
                        if "session_id" in event:
                            session_id = event["session_id"]
                            logger.debug("Captured session_id=%s", session_id)

                    elif event_type == "assistant":
                        # Capture last assistant text as fallback
                        # Structure: {"message": {"content": [{"type": "text", "text": "..."}]}}
                        msg = event.get("message", {})
                        if isinstance(msg, dict):
                            parts = msg.get("content", [])
                            text_parts = [
                                p["text"]
                                for p in parts
                                if isinstance(p, dict)
                                and p.get("type") == "text"
                                and p.get("text")
                            ]
                            if text_parts:
                                last_assistant_text = "\n".join(text_parts)

                    elif event_type == "result":
                        cost_usd = float(event.get("total_cost_usd", 0.0))
                        is_error = event.get("is_error", False)
                        subtype = event.get("subtype")
                        success = not is_error
                        if is_error:
                            error = event.get("result", "CLI error")
                        result_text = event.get("result")
                        if result_text is not None:
                            result_from_event = True
                        if not session_id and "session_id" in event:
                            session_id = event["session_id"]

            # Process any remaining data in buffer
            if buffer:
                line = buffer.decode("utf-8", errors="replace")
                event = parse_stream_event(line)
                if event is not None:
                    if on_event is not None:
                        try:
                            await on_event(event)
                        except Exception:
                            logger.debug("on_event callback failed", exc_info=True)

                    event_type = event.get("type")
                    if event_type == "result":
                        cost_usd = float(event.get("total_cost_usd", 0.0))
                        is_error = event.get("is_error", False)
                        subtype = event.get("subtype")
                        success = not is_error
                        if is_error:
                            error = event.get("result", "CLI error")
                        result_text = event.get("result")
                        if result_text is not None:
                            result_from_event = True
                        if not session_id and "session_id" in event:
                            session_id = event["session_id"]

            await proc.wait()

            if proc.returncode != 0 and not success:
                stderr_bytes = await proc.stderr.read() if proc.stderr else b""
                stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
                error = (
                    error
                    or f"Process exited with code {proc.returncode}: {stderr_text}"
                )
                success = False

        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error running Claude CLI: %s", exc)
            error = str(exc)
            success = False

        # Treat empty/whitespace-only results as None
        if isinstance(result_text, str) and not result_text.strip():
            result_text = None
        # Fallback to last assistant text ONLY when the result event didn't
        # provide a result field at all.  When result_from_event is True the
        # CLI explicitly sent a (possibly empty) result — background agent
        # messages may have overwritten last_assistant_text, so using the
        # fallback would store the wrong value.
        if result_text is None and not result_from_event and last_assistant_text:
            result_text = last_assistant_text

        # If result event came but result was empty, treat as failure
        # (e.g. CLI hit max_turns mid-tool-call and exited without final message)
        if success and result_text is None:
            success = False
            error = error or "CLI exited without producing a result"

        return TaskResult(
            task_id="",  # Filled in by callers
            success=success,
            session_id=session_id,
            result=result_text,
            error=error,
            cost_usd=cost_usd,
            subtype=subtype,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def execute(
        self,
        task: Task,
        cwd: Path,
        allowed_tools: Optional[list[str]] = None,
        max_turns: int = 20,
        on_event: Optional[callable] = None,
        system_prompt: str | None = None,
        permission_mode: str = "bypass",
        env: Optional[dict[str, str]] = None,
    ) -> TaskResult:
        """Execute a task from scratch using the Claude CLI.

        Parameters
        ----------
        task:
            The task to execute.
        cwd:
            Working directory for the Claude subprocess.
        allowed_tools:
            Optional list of tool names (only used when permission_mode is
            "restricted").
        max_turns:
            Maximum agentic turns.  Defaults to 20.
        system_prompt:
            Optional system prompt to append via ``--append-system-prompt``.
        permission_mode:
            ``"bypass"`` (default) or ``"restricted"``.

        Returns
        -------
        TaskResult
        """
        if allowed_tools is None:
            allowed_tools = []

        args = self._build_execute_args(
            task, allowed_tools, max_turns, system_prompt, permission_mode
        )
        logger.info("Executing task %s: %s", task.id, args)

        result = await self._stream(args, cwd, on_event=on_event, env=env)
        result.task_id = task.id
        return result

    async def resume(
        self,
        task: Task,
        session_id: str,
        instruction: str,
        cwd: Path,
        on_event: Optional[callable] = None,
        env: Optional[dict[str, str]] = None,
        permission_mode: str = "bypass",
        system_prompt: str | None = None,
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
        cwd:
            Working directory for the Claude subprocess.
        permission_mode:
            Permission mode (``"bypass"`` skips permission checks).
        system_prompt:
            Optional system prompt to append via ``--append-system-prompt``.

        Returns
        -------
        TaskResult
        """
        args = self._build_resume_args(
            session_id, instruction, permission_mode, system_prompt
        )
        logger.info("Resuming task %s (session=%s): %s", task.id, session_id, args)

        result = await self._stream(args, cwd, on_event=on_event, env=env)
        result.task_id = task.id
        return result
