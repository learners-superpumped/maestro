"""
Maestro Daemon — central orchestrator that wires all components together.

Runs an async main loop that:
  1. Auto-approves pending tasks at low approval levels
  2. Dispatches approved tasks to agent workers
  3. Periodically reconciles running tasks (timeout detection)
  4. Exposes an internal HTTP API for worker communication
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aiohttp import web

from maestro.api import create_api_app
from maestro.budget import BudgetManager
from maestro.config import MaestroConfig
from maestro.integrations.slack import SlackNotifier
from maestro.dispatcher import Dispatcher
from maestro.models import Task, TaskResult, TaskStatus
from maestro.notifications import NotificationManager
from maestro.planner import Planner, SignalCollector
from maestro.reconciler import Reconciler
from maestro.runner import AgentRunner
from maestro.scheduler import Scheduler
from maestro.store import Store

logger = logging.getLogger("maestro.daemon")


class Daemon:
    """Central orchestration daemon for Maestro.

    Wires together the Store, Scheduler, Dispatcher, Reconciler, and
    AgentRunner into a single async run-loop that manages the full task
    lifecycle.

    Args:
        config:    Fully-loaded MaestroConfig.
        store:     Initialised Store instance (schema already applied).
        base_path: Root directory for workspaces, PID file, etc.
    """

    def __init__(self, config: MaestroConfig, store: Store, base_path: Path) -> None:
        self._config = config
        self._store = store
        self._base_path = base_path
        self._runner = AgentRunner()
        self._scheduler = Scheduler(config.schedules)
        self._dispatcher = Dispatcher(store, config.concurrency, config.budget)
        self._reconciler = Reconciler(store, config.agent.stall_timeout_ms)
        self._notifier = NotificationManager(store)
        self._slack = SlackNotifier(
            webhook_url=config.integrations.slack.webhook_url
        )
        self._budget_mgr = BudgetManager(store, config.budget)
        signal_collector = SignalCollector(store, config.goals)
        self._planner = Planner(store, config, signal_collector)
        self._running_procs: dict[str, asyncio.Task[None]] = {}
        self._shutdown = asyncio.Event()
        self._last_planner_tick: float = 0.0
        self._last_reconcile: float = 0.0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def start(self, port: int = 0) -> None:
        """Start the daemon: HTTP server, PID file, and main loop.

        Args:
            port: TCP port for the internal HTTP API.  ``0`` means the OS
                  picks an ephemeral port.
        """
        # 1. Create the aiohttp app
        app = create_api_app(self._store, slack=self._slack)

        # 2. Start TCP site on loopback
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()

        # Resolve the actual port (useful when port=0)
        actual_port = port
        if site._server and site._server.sockets:  # type: ignore[attr-defined]
            actual_port = site._server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]

        logger.info("Internal API listening on 127.0.0.1:%d", actual_port)

        # 3. Export the port so child processes can find us
        os.environ["MAESTRO_DAEMON_PORT"] = str(actual_port)

        # 4. Write PID file
        store_dir = self._base_path / "store"
        store_dir.mkdir(parents=True, exist_ok=True)
        pid_file = store_dir / "maestro.pid"
        pid_file.write_text(str(os.getpid()))
        logger.info("PID %d written to %s", os.getpid(), pid_file)

        try:
            # 5. Run main loop
            await self._main_loop()
        finally:
            # 6. Cleanup
            logger.info("Shutting down daemon…")
            # Cancel all running task coroutines
            for task_name, atask in self._running_procs.items():
                if not atask.done():
                    atask.cancel()
            if self._running_procs:
                await asyncio.gather(
                    *self._running_procs.values(), return_exceptions=True
                )
            self._running_procs.clear()

            # Remove PID file
            if pid_file.exists():
                pid_file.unlink()

            # Shutdown HTTP server
            await runner.cleanup()
            logger.info("Daemon stopped.")

    def stop(self) -> None:
        """Signal the daemon to exit its main loop gracefully."""
        self._shutdown.set()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _main_loop(self) -> None:
        """Run the tick loop until :meth:`stop` is called."""
        interval_s = self._config.daemon.dispatcher_interval_ms / 1_000.0
        reconcile_interval_s = self._config.daemon.reconcile_interval_ms / 1_000.0
        planner_interval_s = self._config.daemon.planner_interval_ms / 1_000.0

        logger.info(
            "Main loop started (dispatch every %.1fs, reconcile every %.1fs, planner every %.1fs)",
            interval_s,
            reconcile_interval_s,
            planner_interval_s,
        )

        loop = asyncio.get_event_loop()
        self._last_reconcile = loop.time()
        self._last_planner_tick = loop.time()

        while not self._shutdown.is_set():
            try:
                await self._auto_approve_pending()
                await self._resume_approved_tasks()
                await self._dispatch_tick()

                # Reconcile on schedule
                now_mono = loop.time()
                if (now_mono - self._last_reconcile) >= reconcile_interval_s:
                    await self._reconciler.reconcile()
                    self._last_reconcile = now_mono

                # Planner on schedule
                if (now_mono - self._last_planner_tick) >= planner_interval_s:
                    await self._planner_tick()
                    self._last_planner_tick = now_mono

            except Exception:
                logger.exception("Error in main loop tick")

            # Wait for the next tick or shutdown signal
            try:
                await asyncio.wait_for(
                    self._shutdown.wait(), timeout=interval_s
                )
                break  # shutdown was set
            except asyncio.TimeoutError:
                pass  # Normal — just means the interval elapsed

    # ------------------------------------------------------------------
    # Auto-approval
    # ------------------------------------------------------------------

    async def _auto_approve_pending(self) -> None:
        """Approve all pending tasks whose approval_level allows it."""
        pending = await self._store.list_tasks(status=TaskStatus.PENDING)
        for task in pending:
            if task.needs_auto_approval():
                await self._store.update_task_status(
                    task.id, TaskStatus.APPROVED
                )
                logger.info(
                    "Auto-approved task %s (level=%d)", task.id, task.approval_level
                )

    # ------------------------------------------------------------------
    # Planner
    # ------------------------------------------------------------------

    async def _planner_tick(self) -> None:
        """Run the planner to create new tasks from goal signals."""
        task_specs = await self._planner.plan()
        if task_specs:
            ids = await self._planner.create_planned_tasks(task_specs)
            logger.info("Planner created %d tasks: %s", len(ids), ids)

        # Update goal states for current signals
        signals = await self._planner.collector.collect_signals()
        now = datetime.now(timezone.utc).isoformat()
        for signal in signals:
            await self._store.update_goal_state(
                signal["goal_id"],
                last_evaluated_at=now,
                current_gap=json.dumps(signal),
            )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch_tick(self) -> None:
        """Ask the Dispatcher for decisions and spawn execution tasks."""
        # Clean up completed asyncio tasks
        done_ids = [
            tid for tid, atask in self._running_procs.items() if atask.done()
        ]
        for tid in done_ids:
            del self._running_procs[tid]

        decisions = await self._dispatcher.get_dispatch_decisions()
        for decision in decisions:
            task = await self._store.get_task(decision.task_id)
            if task is None:
                logger.warning("Dispatch decision for missing task %s", decision.task_id)
                continue

            # Transition to CLAIMED
            await self._store.update_task_status(task.id, TaskStatus.CLAIMED)
            task.status = TaskStatus.CLAIMED

            # Spawn an asyncio task for execution
            atask = asyncio.create_task(
                self._execute_task(task), name=f"task-{task.id}"
            )
            self._running_procs[task.id] = atask

    # ------------------------------------------------------------------
    # Resume paused-then-approved tasks
    # ------------------------------------------------------------------

    async def _resume_approved_tasks(self) -> None:
        """Find tasks that were paused, now approved, and have a session_id. Resume them."""
        approved = await self._store.list_tasks(status=TaskStatus.APPROVED)
        for task in approved:
            if task.session_id:  # Was paused and approved — resume
                # Avoid re-resuming if already in running_procs
                if task.id in self._running_procs:
                    continue

                approval = await self._store.get_approval_by_task(task.id)
                instruction = "Approved. Continue execution."
                if approval and approval.get("reviewer_note"):
                    instruction = f"Approved with feedback: {approval['reviewer_note']}"
                if approval and approval.get("revised_content"):
                    instruction = f"Revision requested: {approval['revised_content']}"

                await self._store.update_task_status(task.id, TaskStatus.CLAIMED)

                atask = asyncio.create_task(
                    self._resume_task(task, instruction),
                    name=f"resume-{task.id}",
                )
                self._running_procs[task.id] = atask

    async def _resume_task(self, task: Task, instruction: str) -> None:
        """Resume a paused task's CLI session."""
        workspace_path = self._base_path / "workspaces" / task.workspace
        if not workspace_path.exists():
            logger.error(
                "Workspace %s does not exist for resume of task %s",
                workspace_path, task.id,
            )
            await self._store.update_task_status(
                task.id,
                TaskStatus.FAILED,
                error=f"Workspace not found: {workspace_path}",
            )
            return

        now = datetime.now(timezone.utc)
        timeout_ms = self._config.agent.turn_timeout_ms
        timeout_at = datetime.fromtimestamp(
            now.timestamp() + timeout_ms / 1_000.0, tz=timezone.utc
        )

        await self._store.update_task_status(
            task.id,
            TaskStatus.RUNNING,
            started_at=now.isoformat(),
            timeout_at=timeout_at.isoformat(),
        )

        try:
            result = await self._runner.resume(
                task, task.session_id, instruction, workspace_path  # type: ignore[arg-type]
            )
        except Exception as exc:
            logger.exception("Runner raised resuming task %s: %s", task.id, exc)
            result = TaskResult(
                task_id=task.id,
                success=False,
                error=str(exc),
            )

        await self._handle_result(task, result)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_task(self, task: Task) -> None:
        """Execute a single task end-to-end.

        1. Verify workspace exists.
        2. Transition to RUNNING with started_at and timeout_at.
        3. Call the AgentRunner.
        4. Handle the result.
        """
        workspace_path = self._base_path / "workspaces" / task.workspace
        if not workspace_path.exists():
            logger.error(
                "Workspace %s does not exist for task %s", workspace_path, task.id
            )
            await self._store.update_task_status(
                task.id,
                TaskStatus.FAILED,
                error=f"Workspace not found: {workspace_path}",
            )
            return

        # Transition to RUNNING
        now = datetime.now(timezone.utc)
        timeout_ms = self._config.agent.turn_timeout_ms
        timeout_at = datetime.fromtimestamp(
            now.timestamp() + timeout_ms / 1_000.0, tz=timezone.utc
        )

        await self._store.update_task_status(
            task.id,
            TaskStatus.RUNNING,
            started_at=now.isoformat(),
            timeout_at=timeout_at.isoformat(),
        )
        task.status = TaskStatus.RUNNING

        # Execute via the runner
        try:
            result = await self._runner.execute(
                task,
                workspace_path,
                allowed_tools=self._config.agent.default_allowed_tools,
                max_turns=self._config.agent.default_max_turns,
            )
        except Exception as exc:
            logger.exception("Runner raised for task %s: %s", task.id, exc)
            result = TaskResult(
                task_id=task.id,
                success=False,
                error=str(exc),
            )

        await self._handle_result(task, result)

    # ------------------------------------------------------------------
    # Result handling
    # ------------------------------------------------------------------

    async def _handle_result(self, task: Task, result: TaskResult) -> None:
        """Process the outcome of a task execution.

        - On success: mark COMPLETED, record spend.
        - On failure: retry if attempts remain, else FAILED.
        """
        # Persist session_id if captured
        extra_fields: dict[str, object] = {}
        if result.session_id:
            extra_fields["session_id"] = result.session_id

        if result.success:
            now = datetime.now(timezone.utc)
            await self._store.update_task_status(
                task.id,
                TaskStatus.COMPLETED,
                cost_usd=result.cost_usd,
                completed_at=now.isoformat(),
                **extra_fields,
            )
            # Record daily spend
            if result.cost_usd > 0:
                today = now.strftime("%Y-%m-%d")
                await self._store.record_spend(today, result.cost_usd)

            logger.info(
                "Task %s completed (cost=$%.4f)", task.id, result.cost_usd
            )

            # Level 1 post-notification
            if task.approval_level == 1:
                await self._notifier.notify(
                    "task_completed",
                    f"Task completed: {task.title}",
                    task.id,
                )
                if self._slack.available:
                    await self._slack.send_completion(task.id, task.title)
        else:
            # Check retry eligibility
            new_attempt = task.attempt + 1
            if new_attempt < task.max_retries:
                await self._store.update_task_status(
                    task.id,
                    TaskStatus.RETRY_QUEUED,
                    attempt=new_attempt,
                    error=result.error,
                    **extra_fields,
                )
                logger.info(
                    "Task %s retry queued (attempt %d/%d): %s",
                    task.id, new_attempt, task.max_retries, result.error,
                )
            else:
                now = datetime.now(timezone.utc)
                await self._store.update_task_status(
                    task.id,
                    TaskStatus.FAILED,
                    attempt=new_attempt,
                    error=result.error,
                    completed_at=now.isoformat(),
                    **extra_fields,
                )
                logger.warning(
                    "Task %s failed after %d attempts: %s",
                    task.id, new_attempt, result.error,
                )
