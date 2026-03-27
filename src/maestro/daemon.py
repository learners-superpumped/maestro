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
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import web

from maestro.api import create_api_app
from maestro.approval import ApprovalManager
from maestro.assets import AssetManager
from maestro.budget import BudgetManager
from maestro.conductor import ConductorAgent
from maestro.config import MaestroConfig
from maestro.dispatcher import AgentLogProcessor, Dispatcher
from maestro.events import EventBus, EventEmittingStore
from maestro.integrations.slack import SlackAdapter
from maestro.models import Task, TaskResult, TaskStatus
from maestro.notifications import NotificationManager
from maestro.planner import Planner
from maestro.reconciler import Reconciler
from maestro.runner import AgentRunner
from maestro.scheduler import Scheduler
from maestro.store import Store
from maestro.worktree import WorktreeManager
from maestro.ws import WebSocketManager

logger = logging.getLogger("maestro.daemon")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Daemon:
    """Central orchestration daemon for Maestro.

    Wires together the Store, Scheduler, Dispatcher, Reconciler, and
    AgentRunner into a single async run-loop that manages the full task
    lifecycle.

    Args:
        config:    Fully-loaded MaestroConfig.
        store:     Initialised Store instance (schema already applied).
        base_path: Root directory for worktrees, PID file, etc.
    """

    def __init__(self, config: MaestroConfig, store: Store, base_path: Path) -> None:
        self._config = config
        # Wrap store with event emission
        self._bus = EventBus()
        if isinstance(store, EventEmittingStore):
            self._store = store
            self._bus = store._bus
        else:
            self._store = EventEmittingStore(store._db_path, self._bus)
        self._ws_manager = WebSocketManager(self._bus)
        self._base_path = base_path
        self._runner = AgentRunner()
        self._scheduler = Scheduler(store)
        self._dispatcher = Dispatcher(store, config.concurrency, config.budget)
        self._reconciler = Reconciler(store, config.agent.stall_timeout_ms)
        self._notifier = NotificationManager(store)
        self._budget_mgr = BudgetManager(store, config.budget)
        self._planner = Planner(store, config)
        self._approval_manager = ApprovalManager(store)

        # Asset manager (embedding client is optional)
        embedding_client = None
        if self._config.assets.gemini_api_key:
            try:
                from maestro.embedding import EmbeddingClient

                embedding_client = EmbeddingClient(self._config.assets.gemini_api_key)
            except Exception:
                pass
        # Drive provider (optional)
        drive_provider = None
        if self._config.drive.enabled and self._config.drive.refresh_token:
            try:
                from maestro.drive import DriveProvider

                drive_provider = DriveProvider(
                    client_id=self._config.drive.client_id,
                    client_secret=self._config.drive.client_secret,
                    refresh_token=self._config.drive.refresh_token,
                    drive_id=self._config.drive.drive_id,
                    root_folder_id=self._config.drive.root_folder_id,
                )
                logger.info("Google Drive provider initialized")
            except Exception:
                logger.warning("Failed to initialize Drive provider", exc_info=True)
        self._drive_provider = drive_provider

        self._asset_manager = AssetManager(
            self._store,
            embedding_client,
            self._config,
            self._base_path,
            drive=drive_provider,
        )

        self._worktree_mgr = WorktreeManager(base_path)

        # Conductor agent
        self._conductor = ConductorAgent(
            store=self._store,
            bus=self._bus,
            config=config,
            base_path=base_path,
        )

        self._slack = SlackAdapter(
            store=self._store,
            bus=self._bus,
            conductor=self._conductor,
            approval_manager=self._approval_manager,
            config=config.integrations.slack,
        )

        self._port: int = 0
        self._running_procs: dict[str, asyncio.Task[None]] = {}
        self._shutdown = asyncio.Event()
        self._last_planner_tick: float = 0.0
        self._last_reconcile: float = 0.0
        self._last_scheduler_tick: float = 0.0
        self._last_cleanup_tick: float = 0.0
        self._last_reminder_tick: float = 0.0

    # ------------------------------------------------------------------
    # Seed helpers
    # ------------------------------------------------------------------

    async def _seed_from_yaml(self) -> None:
        """One-time migration: seed DB from YAML schedules if DB is empty."""
        existing = await self._store.list_schedules()
        if existing:
            return  # Already has schedules in DB, skip seeding

        # Check if config still has schedules in YAML (old format)
        yaml_path = self._base_path / "maestro.yaml"
        if not yaml_path.exists():
            return
        import yaml

        raw = yaml.safe_load(yaml_path.read_text()) or {}
        for s in raw.get("schedules", []):
            await self._store.create_schedule(
                name=s["name"],
                agent=s.get("agent", "default"),
                task_type=s["task_type"],
                cron=s.get("cron"),
                interval_ms=s.get("interval_ms"),
                approval_level=s.get("approval_level", 0),
            )
            logger.info("Seeded schedule from YAML: %s", s["name"])

        # Seed auto_extract rules
        assets_cfg = raw.get("assets", {})
        for agent_name, type_rules in assets_cfg.get("auto_extract", {}).items():
            for task_type, rule in type_rules.items():
                tags = rule.get("tags_from", [])
                await self._store.create_extract_rule(
                    task_type=task_type,
                    asset_type=rule["asset_type"],
                    title_field=rule.get("title_field"),
                    iterate=rule.get("iterate"),
                    tags_from=tags if tags else None,
                )
                logger.info(
                    "Seeded extract rule from YAML: %s/%s", agent_name, task_type
                )

    # ------------------------------------------------------------------
    # CWD & prompt resolution
    # ------------------------------------------------------------------

    def _resolve_cwd(self, task: Task) -> Path:
        """Determine the working directory for a task."""
        agent_def = self._config.agents.get(task.agent)
        if not self._worktree_mgr.is_git_repo():
            return self._base_path
        if task.no_worktree or (agent_def and agent_def.no_worktree):
            return self._base_path
        if task.goal_id:
            return self._worktree_mgr.ensure_worktree(f"goal-{task.goal_id}")
        # For review/revision tasks without goal_id, reuse parent task's worktree
        # so reviewer can see the changes the agent actually made
        if task.parent_task_id:
            parent_wt = f"task-{task.parent_task_id}"
            if parent_wt in self._worktree_mgr.list_worktrees():
                return self._worktree_mgr.ensure_worktree(parent_wt)
        return self._worktree_mgr.ensure_worktree(f"task-{task.id}")

    def _load_prompt(self, agent_name: str) -> str | None:
        """Load agent prompt using 3-tier hierarchy.

        Hierarchy: project override -> package builtin -> None.
        """
        agent_def = self._config.agents.get(agent_name)
        if not agent_def:
            return None

        prompt_parts: list[str] = []
        if agent_def.role:
            prompt_parts.append(f"# Role\n{agent_def.role}")

        # Tier 2: project override (.maestro/prompts/)
        if agent_def.instructions:
            override_path = self._base_path / agent_def.instructions
            if override_path.exists():
                prompt_parts.append(override_path.read_text())
                return "\n\n".join(prompt_parts)

        # Tier 1: package builtin
        import importlib.resources

        try:
            builtin = importlib.resources.files("maestro.prompts") / f"{agent_name}.md"
            if builtin.is_file():
                prompt_parts.append(builtin.read_text())
        except (FileNotFoundError, TypeError):
            pass

        return "\n\n".join(prompt_parts) if prompt_parts else None

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
        app = create_api_app(self._store, project_root=self._base_path)
        app["asset_manager"] = self._asset_manager
        app["drive_provider"] = self._drive_provider
        app["daemon"] = self
        app["conductor"] = self._conductor
        app["base_path"] = self._base_path
        app["slack_adapter"] = self._slack
        app.router.add_get("/ws", self._ws_manager.handle)

        # 2. Start TCP site on loopback
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", port)
        await site.start()

        # Resolve the actual port (useful when port=0)
        actual_port = port
        if site._server and site._server.sockets:  # type: ignore[attr-defined]
            actual_port = site._server.sockets[0].getsockname()[1]  # type: ignore[attr-defined]

        self._port = actual_port
        self._conductor.set_daemon_port(actual_port)
        logger.info("Internal API listening on http://127.0.0.1:%d", actual_port)

        if self._config.integrations.slack.enabled:
            try:
                await self._slack.start()
            except Exception:
                logger.exception(
                    "Failed to start Slack adapter (continuing without Slack)"
                )

        # 3. Write PID and port files to .maestro/ (fixed location)
        maestro_dir = self._base_path / ".maestro"
        maestro_dir.mkdir(parents=True, exist_ok=True)
        pid_file = maestro_dir / "maestro.pid"
        pid_file.write_text(str(os.getpid()))
        port_file = maestro_dir / "maestro.port"
        port_file.write_text(str(actual_port))
        logger.info("PID %d written to %s", os.getpid(), pid_file)

        # 5. Seed DB from YAML on first run (backward compatibility)
        await self._seed_from_yaml()

        await self._store.backfill_fts()

        # 6. Restore scheduler state from DB
        schedules = await self._store.list_schedules(enabled_only=True)
        restored: dict[str, str] = {}
        for s in schedules:
            last = await self._store.get_schedule_last_run(s["name"])
            if last:
                restored[s["name"]] = last
        self._scheduler.restore_last_triggered(restored)

        try:
            # 6. Run main loop
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

            if self._slack.available:
                try:
                    await self._slack.stop()
                except Exception:
                    logger.debug("Error stopping Slack adapter", exc_info=True)

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
        scheduler_interval_s = self._config.daemon.scheduler_interval_ms / 1_000.0
        cleanup_interval_s = self._config.assets.cleanup_interval_ms / 1_000.0
        reminder_interval_s = 10.0  # 10-second reminder check interval

        logger.info(
            "Main loop started (dispatch every %.1fs, reconcile every %.1fs,"
            " planner every %.1fs, scheduler every %.1fs, reminder every %.1fs)",
            interval_s,
            reconcile_interval_s,
            planner_interval_s,
            scheduler_interval_s,
            reminder_interval_s,
        )

        loop = asyncio.get_event_loop()
        self._last_reconcile = loop.time()
        self._last_planner_tick = loop.time()
        self._last_scheduler_tick = loop.time()
        self._last_cleanup_tick = loop.time()
        self._last_reminder_tick = loop.time()

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

                # Scheduler on schedule
                if (now_mono - self._last_scheduler_tick) >= scheduler_interval_s:
                    await self._scheduler_tick()
                    self._last_scheduler_tick = now_mono

                # Asset cleanup on schedule
                if (now_mono - self._last_cleanup_tick) >= cleanup_interval_s:
                    await self._cleanup_tick()
                    self._last_cleanup_tick = now_mono

                # Reminder check on schedule
                if (now_mono - self._last_reminder_tick) >= reminder_interval_s:
                    await self._reminder_tick()
                    self._last_reminder_tick = now_mono

            except Exception:
                logger.exception("Error in main loop tick")

            # Wait for the next tick or shutdown signal
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval_s)
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
                await self._store.update_task_status(task.id, TaskStatus.APPROVED)
                logger.info(
                    "Auto-approved task %s (level=%d)", task.id, task.approval_level
                )

    # ------------------------------------------------------------------
    # Planner
    # ------------------------------------------------------------------

    async def _planner_tick(self) -> None:
        """Run the planner to create new tasks from goal signals."""
        task_specs = await self._planner.plan()
        if not task_specs:
            return

        # Collect signals to know which goals to update
        signals = await self._planner.collector.collect_signals()
        {s["goal_id"] for s in signals}

        for spec in task_specs:
            task = Task(
                id=str(uuid.uuid4())[:8],
                type=spec.get("type", "planning"),
                agent=spec.get("agent", "planner"),
                title=spec["title"],
                instruction=spec["instruction"],
                priority=spec.get("priority", 1),
                approval_level=spec.get("approval_level", 0),
            )
            await self._store.create_task(task)
            logger.info("Planner created task %s: %s", task.id, task.title)

        # Update goal state
        for signal in signals:
            await self._store.update_goal(
                signal["goal_id"],
                last_evaluated_at=_now_iso(),
                current_gap=signal["description"],
                last_task_created_at=_now_iso(),
            )

    async def trigger_goal(self, goal_id: str) -> int:
        """Manually trigger planner for a single goal, bypassing cooldown.

        Returns the number of tasks created.
        """

        goal = await self._store.get_goal(goal_id)
        if not goal:
            return 0

        # Build a signal directly, bypassing cooldown/active-task guards
        signal = {
            "goal_id": goal["id"],
            "type": "manual_trigger",
            "description": f"Manual trigger for goal {goal['id']}",
            "data": {"metrics": goal.get("metrics", "{}")},
        }

        task_specs = await self._planner._build_planning_task([signal])
        task = Task(
            id=str(uuid.uuid4())[:8],
            type=task_specs.get("type", "planning"),
            agent=task_specs.get("agent", "planner"),
            title=task_specs["title"],
            instruction=task_specs["instruction"],
            priority=task_specs.get("priority", 1),
            approval_level=task_specs.get("approval_level", 0),
        )
        await self._store.create_task(task)
        logger.info("Manual trigger created task %s for goal %s", task.id, goal_id)

        await self._store.update_goal(
            goal_id,
            last_evaluated_at=_now_iso(),
            current_gap=signal["description"],
            last_task_created_at=_now_iso(),
        )

        return 1

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch_tick(self) -> None:
        """Ask the Dispatcher for decisions and spawn execution tasks."""
        # Clean up completed asyncio tasks
        done_ids = [tid for tid, atask in self._running_procs.items() if atask.done()]
        for tid in done_ids:
            del self._running_procs[tid]

        decisions = await self._dispatcher.get_dispatch_decisions()
        for decision in decisions:
            task = await self._store.get_task(decision.task_id)
            if task is None:
                logger.warning(
                    "Dispatch decision for missing task %s", decision.task_id
                )
                continue

            # Inject dependency results into instruction
            if task.depends_on:
                try:
                    dep_ids = json.loads(task.depends_on)
                except (json.JSONDecodeError, TypeError):
                    dep_ids = []
                if dep_ids:
                    context_parts = []
                    for dep_id in dep_ids:
                        dep_task = await self._store.get_task(dep_id)
                        if not dep_task:
                            continue
                        rj = dep_task.result
                        if not rj or (isinstance(rj, str) and not rj.strip()):
                            continue
                        result_str = (
                            json.dumps(rj, ensure_ascii=False)
                            if not isinstance(rj, str)
                            else rj
                        )
                        context_parts.append(f"### {dep_task.title}\n{result_str}")
                    if context_parts:
                        context = "\n\n".join(context_parts)
                        task.instruction = (
                            f"## 이전 단계 결과\n\n{context}\n\n"
                            f"## 지시\n\n{task.instruction}"
                        )

            # Transition to CLAIMED (persist enriched instruction if modified)
            claim_kwargs: dict = {}
            if task.depends_on and "이전 단계 결과" in task.instruction:
                claim_kwargs["instruction"] = task.instruction
            await self._store.update_task_status(
                task.id, TaskStatus.CLAIMED, **claim_kwargs
            )
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
        """Find tasks that were paused, now approved, and have a session_id.

        Resume them.
        """
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
        cwd = self._resolve_cwd(task)

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

        agent_env = {
            "MAESTRO_DAEMON_PORT": str(self._port),
            "MAESTRO_BASE_PATH": str(self._base_path),
            "MAESTRO_DB_PATH": self._store._db_path,
        }

        # Resolve permission mode for resume
        agent_def = self._config.agents.get(
            task.agent, self._config.agents.get("default")
        )
        if agent_def and agent_def.permission_mode:
            resume_perm = agent_def.permission_mode
        else:
            resume_perm = self._config.agent.permission_mode

        # Re-inject system prompt on resume so agent stays on-role
        system_prompt = self._load_prompt(task.agent)
        task_context = (
            "## Execution Environment\n"
            "You are a HEADLESS autonomous agent in the Maestro orchestration system.\n"
            "There is NO human operator reading your output. "
            "No one can answer questions.\n\n"
            "RULES:\n"
            "1. NEVER ask questions, present choices, or wait for input. "
            "Always make the best judgment call yourself and keep going.\n"
            "2. If you lack critical information, state your assumptions and proceed.\n"
            "3. Your final output is stored as the task result. "
            "Make it complete and actionable.\n\n"
            f"## Maestro Task Context\n"
            f"- Task ID: {task.id}\n"
            f"- Task Type: {task.type}\n"
            f"- Task Title: {task.title}\n"
        )
        if system_prompt:
            system_prompt = f"{task_context}\n{system_prompt}"
        else:
            system_prompt = task_context

        if not task.session_id:
            return

        try:
            result = await self._runner.resume(
                task,
                task.session_id,
                instruction,
                cwd,
                env=agent_env,
                permission_mode=resume_perm,
                system_prompt=system_prompt,
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

        1. Resolve cwd and agent config.
        2. Transition to RUNNING with started_at and timeout_at.
        3. Call the AgentRunner.
        4. Handle the result.
        """
        agent_def = self._config.agents.get(
            task.agent, self._config.agents.get("default")
        )
        cwd = self._resolve_cwd(task)
        system_prompt = self._load_prompt(task.agent)

        # Inject headless execution context so the agent understands its environment
        task_context = (
            "## Execution Environment\n"
            "You are a HEADLESS autonomous agent in the Maestro orchestration system.\n"
            "There is NO human operator reading your output. "
            "No one can answer questions.\n\n"
            "RULES:\n"
            "1. NEVER ask questions, present choices, or wait for input. "
            "Always make the best judgment call yourself and keep going.\n"
            "2. If you lack critical information, state your assumptions and proceed.\n"
            "3. Your final output is stored as the task result. "
            "Make it complete and actionable.\n\n"
            f"## Maestro Task Context\n"
            f"- Task ID: {task.id}\n"
            f"- Task Type: {task.type}\n"
            f"- Task Title: {task.title}\n"
        )
        if system_prompt:
            system_prompt = f"{task_context}\n{system_prompt}"
        else:
            system_prompt = task_context

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
        processor = AgentLogProcessor(self._store, self._bus)

        async def on_event(event: dict) -> None:
            await processor.process_event(task.id, event)

        # Resolve effective permission mode
        if agent_def and agent_def.permission_mode:
            effective_permission_mode = agent_def.permission_mode
        else:
            effective_permission_mode = self._config.agent.permission_mode

        # Pass daemon connection info as env vars for MCP servers
        agent_env = {
            "MAESTRO_DAEMON_PORT": str(self._port),
            "MAESTRO_BASE_PATH": str(self._base_path),
            "MAESTRO_DB_PATH": self._store._db_path,
        }

        try:
            result = await self._runner.execute(
                task,
                cwd=cwd,
                allowed_tools=agent_def.tools
                if agent_def
                else self._config.agent.default_allowed_tools,
                max_turns=agent_def.max_turns
                if agent_def
                else self._config.agent.default_max_turns,
                on_event=on_event,
                system_prompt=system_prompt,
                permission_mode=effective_permission_mode,
                env=agent_env,
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

        # Deterministic subtype-based handling:
        # error_max_turns means Claude hit the turn limit — treat as retryable failure
        if result.subtype == "error_max_turns" and result.session_id:
            logger.warning(
                "Task %s hit max_turns limit (subtype=%s)",
                task.id,
                result.subtype,
            )
            result.success = False
            result.error = result.error or "Reached max agentic turns limit"

        if result.success:
            now = datetime.now(timezone.utc)
            if result.result is not None:
                # Re-fetch from DB to check if result was already set
                # (e.g. from a previous execution before resume)
                current = await self._store.get_task(task.id)
                if not current or not current.result:
                    extra_fields["result"] = result.result
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

            logger.info("Task %s completed (cost=$%.4f)", task.id, result.cost_usd)

            # Index completed task for FTS search
            try:
                completed_task = await self._store.get_task(task.id)
                if completed_task:
                    await self._store.index_task_fts(completed_task)
            except Exception:
                logger.debug("FTS indexing failed for task %s", task.id, exc_info=True)

            # Level 1 post-notification
            if task.approval_level == 1:
                await self._notifier.notify(
                    "task_completed",
                    f"Task completed: {task.title}",
                    task.id,
                )
                pass  # Slack task completion is handled via event bus

            # Post-completion processing (planning results, review pipeline)
            if result.success:
                await self._on_task_completed(task, result)

            # Auto-cleanup worktree if no changes
            if not task.no_worktree and self._worktree_mgr.is_git_repo():
                if task.goal_id:
                    wt_name = f"goal-{task.goal_id}"
                    # Only cleanup goal worktree if no non-terminal tasks remain
                    goal_tasks = await self._store.list_tasks(goal_id=task.goal_id)
                    terminal = {"completed", "failed", "cancelled"}
                    has_remaining = any(
                        t.id != task.id and t.status.value not in terminal
                        for t in goal_tasks
                    )
                    if (
                        not has_remaining
                        and wt_name in self._worktree_mgr.list_worktrees()
                    ):
                        if not self._worktree_mgr.has_changes(wt_name):
                            self._worktree_mgr.remove_worktree(wt_name)
                else:
                    wt_name = f"task-{task.id}"
                    if wt_name in self._worktree_mgr.list_worktrees():
                        # Defer cleanup for tasks entering review pipeline;
                        # review/revision tasks reuse this worktree via
                        # parent_task_id fallback in _resolve_cwd
                        if task.approval_level >= 1 and result.success:
                            pass
                        elif not self._worktree_mgr.has_changes(wt_name):
                            self._worktree_mgr.remove_worktree(wt_name)
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
                    task.id,
                    new_attempt,
                    task.max_retries,
                    result.error,
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
                    task.id,
                    new_attempt,
                    result.error,
                )

                # Index failed task for FTS search
                try:
                    failed_task = await self._store.get_task(task.id)
                    if failed_task:
                        await self._store.index_task_fts(failed_task)
                except Exception:
                    logger.debug(
                        "FTS indexing failed for task %s", task.id, exc_info=True
                    )

                await self._cascade_cancel(task.id)

    async def _cascade_cancel(self, task_id: str) -> None:
        """Cancel all tasks that depend on the given task (recursively)."""
        dependents = await self._store.list_dependents(task_id)
        for t in dependents:
            await self._store.update_task_status(
                t.id,
                TaskStatus.CANCELLED,
                error=f"Dependency {task_id} failed",
            )
            logger.info("Cascade-cancelled task %s (dep %s failed)", t.id, task_id)
            await self._cascade_cancel(t.id)

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    async def _scheduler_tick(self) -> None:
        now = datetime.now(timezone.utc)
        last_tick_iso = await self._store.get_scheduler_state("last_tick")
        if last_tick_iso:
            since = datetime.fromisoformat(last_tick_iso)
        else:
            since = now - timedelta(
                seconds=self._config.daemon.scheduler_interval_ms / 1000
            )

        due = await self._scheduler.get_due_schedules(now, since)
        due += await self._scheduler.get_due_intervals(now)

        for entry in due:
            if await self._has_active_task_for_schedule(entry):
                continue
            task = Task(
                id=str(uuid.uuid4())[:8],
                type=entry["task_type"],
                agent=entry.get("agent", "default"),
                no_worktree=bool(entry.get("no_worktree", False)),
                title=f"Scheduled: {entry['name']}",
                instruction=(
                    f"스케줄 '{entry['name']}' 실행. task_type: {entry['task_type']}. "
                    f"적절한 액션을 수행하라."
                ),
                approval_level=entry["approval_level"],
            )
            await self._store.create_task(task)
            self._scheduler.mark_triggered(entry["name"], now)
            await self._store.set_schedule_last_run(entry["name"], now.isoformat())

        await self._store.set_scheduler_state("last_tick", now.isoformat())

    async def _has_active_task_for_schedule(self, entry: dict) -> bool:
        tasks = await self._store.list_tasks(agent=entry.get("agent", "default"))
        return any(
            t.type == entry["task_type"]
            and t.status.value not in ("completed", "failed", "cancelled")
            for t in tasks
        )

    # ------------------------------------------------------------------
    # Asset cleanup
    # ------------------------------------------------------------------

    async def _cleanup_tick(self) -> None:
        """Archive expired assets and purge old archives."""
        try:
            archived = await self._store.archive_expired_assets()
            if archived:
                logger.info("Archived %d expired assets", archived)
            purged = await self._store.purge_archived_assets(
                grace_days=self._config.assets.archive_grace_days
            )
            if purged:
                logger.info("Purged %d archived assets", purged)
        except Exception as e:
            logger.warning("Asset cleanup failed: %s", e)

    # ------------------------------------------------------------------
    # Reminders
    # ------------------------------------------------------------------

    async def _reminder_tick(self) -> None:
        """Check for due reminders and emit events (10-second interval)."""
        try:
            due = await self._store.get_due_reminders()
            for reminder in due:
                await self._bus.emit(
                    "reminder.triggered",
                    {
                        "id": reminder["id"],
                        "user_id": reminder["user_id"],
                        "message": reminder["message"],
                        "trigger_at": reminder["trigger_at"],
                    },
                )
                await self._store.mark_reminder_delivered(reminder["id"])
                logger.info(
                    "Reminder triggered: %s (user=%s)",
                    reminder["id"],
                    reminder["user_id"],
                )
        except Exception as e:
            logger.warning("Reminder tick failed: %s", e)

    # ------------------------------------------------------------------
    # Post-completion processing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(text):
        if isinstance(text, (list, dict)):
            return text
        if not isinstance(text, str):
            return None
        stripped = text.strip()
        # Try direct parse first
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, TypeError):
            pass
        # Try extracting from markdown code block (```json ... ```)
        import re

        match = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", stripped)
        if match:
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, TypeError):
                pass
        # Try finding first { or [ and parsing from there
        for i, ch in enumerate(stripped):
            if ch in "{[":
                try:
                    return json.loads(stripped[i:])
                except (json.JSONDecodeError, TypeError):
                    pass
                break
        return None

    async def _on_task_completed(self, task: Task, result: TaskResult) -> None:
        # planning과 review는 자체 핸들러가 있으므로 approval 체크 불필요
        if task.type == "planning" and result.result:
            parsed = self._extract_json(result.result)
            if isinstance(parsed, list):
                await self._planner.create_planned_tasks(parsed)
            else:
                logger.error("Failed to parse planning result for task %s", task.id)
            return

        if task.type == "review" and result.result:
            await self._handle_review_result(task, result)
            return

        # Emit revision event on parent task
        if task.parent_task_id and task.type != "review":
            await self._store.record_task_event(
                task_id=task.parent_task_id,
                event_type="revision_submitted",
                actor=f"agent:{task.id}",
                detail_json={
                    "cost_usd": result.cost_usd,
                    "revision_task_id": task.id,
                },
            )

        # Auto-extract assets from result
        if result.result and self._asset_manager:
            rule = await self._store.get_extract_rule(task.type)
            if rule:
                rules = {
                    "asset_type": rule["asset_type"],
                    "title_field": rule.get("title_field"),
                    "iterate": rule.get("iterate"),
                    "tags_from": rule.get("tags_from"),
                }
                try:
                    rj = result.result
                    if isinstance(rj, str):
                        rj = json.loads(rj)
                    if isinstance(rj, dict):
                        await self._asset_manager.auto_extract(
                            task_id=task.id,
                            result=rj,
                            rules=rules,
                        )
                except Exception as e:
                    logger.warning(
                        "Asset auto-extract failed for task %s: %s", task.id, e
                    )

        # Resume 완료 → 리뷰 재진입 방지
        # task.session_id == result.session_id 이면 동일 세션을 이어받은 것이므로
        # 이미 리뷰 사이클이 완료된 상태. 재리뷰 하지 않음.
        if (
            task.session_id
            and result.session_id
            and task.session_id == result.session_id
        ):
            return

        # Level 0은 리뷰 없이 완료
        if task.approval_level == 0:
            return

        # Level 1, 2: 실행 완료 후 reviewer 검증
        await self._create_review_task(task, result)

    def _effective_no_worktree(self, task: Task) -> bool:
        """Check if a task effectively runs in base_path (no worktree)."""
        if task.no_worktree:
            return True
        agent_def = self._config.agents.get(task.agent)
        return bool(agent_def and agent_def.no_worktree)

    def _try_deferred_worktree_cleanup(self, task: Task) -> None:
        """Clean up deferred worktree for independent tasks after review cycle ends."""
        if task.goal_id or task.no_worktree:
            return  # Goal worktrees have their own lifecycle
        if not self._worktree_mgr.is_git_repo():
            return
        wt_name = f"task-{task.id}"
        if wt_name in self._worktree_mgr.list_worktrees():
            if not self._worktree_mgr.has_changes(wt_name):
                self._worktree_mgr.remove_worktree(wt_name)

    async def _create_review_task(
        self, original_task: Task, result: TaskResult
    ) -> None:
        review_task = Task(
            id=str(uuid.uuid4())[:8],
            type="review",
            agent="reviewer",
            title=f"Review: {original_task.title}",
            instruction=json.dumps(
                {
                    "original_task_id": original_task.parent_task_id
                    or original_task.id,
                    "original_agent": original_task.agent,
                    "original_instruction": original_task.instruction,
                    "result": result.result,
                },
                ensure_ascii=False,
            ),
            approval_level=0,
            priority=1,
            # Inherit worktree context so reviewer runs in same directory
            no_worktree=self._effective_no_worktree(original_task),
            goal_id=original_task.goal_id,
            # Chain to worktree-owning root task for _resolve_cwd
            parent_task_id=(original_task.parent_task_id or original_task.id),
        )
        await self._store.create_task(review_task)

    async def _handle_review_result(
        self, review_task: Task, result: TaskResult
    ) -> None:
        review_data = self._extract_json(result.result)
        if not isinstance(review_data, dict):
            logger.error("Review result not valid JSON for task %s", review_task.id)
            # Record the failure as an event so it's visible in the Activity feed
            instruction_data = self._extract_json(review_task.instruction)
            if isinstance(instruction_data, dict):
                original_task_id = instruction_data.get("original_task_id")
                if original_task_id:
                    await self._store.record_task_event(
                        task_id=original_task_id,
                        event_type="review_submitted",
                        actor=f"agent:{review_task.id}",
                        detail_json={
                            "verdict": "error",
                            "summary": (
                                "Review failed: response was"
                                " not valid JSON. Will retry."
                            ),
                            "issues": [],
                            "review_task_id": review_task.id,
                        },
                    )
            return

        instruction_data = self._extract_json(review_task.instruction)
        original_task_id = instruction_data["original_task_id"]
        original_task = await self._store.get_task(original_task_id)
        if original_task is None:
            return

        # Emit review event on the original task
        await self._store.record_task_event(
            task_id=original_task_id,
            event_type="review_submitted",
            actor=f"agent:{review_task.id}",
            detail_json={
                "verdict": review_data.get("verdict"),
                "summary": review_data.get("summary", ""),
                "issues": review_data.get("issues", []),
                "review_task_id": review_task.id,
                "review_round": original_task.review_count + 1,
            },
        )

        if review_data.get("verdict") == "pass":
            await self._approval_manager.submit_draft(
                original_task_id,
                json.dumps(
                    {
                        "result": result.result,
                        "review_summary": review_data.get("summary", ""),
                    }
                ),
            )
            self._try_deferred_worktree_cleanup(original_task)
        elif original_task.review_count >= self._config.agent.max_review_rounds:
            await self._approval_manager.submit_draft(
                original_task_id,
                json.dumps(
                    {
                        "result": result.result,
                        "review_summary": (
                            f"자동 검증 {original_task.review_count}"
                            "회 실패. 수동 검토 필요."
                        ),
                        "issues": review_data.get("issues", []),
                    }
                ),
            )
            self._try_deferred_worktree_cleanup(original_task)
        else:
            await self._store.increment_review_count(original_task_id)
            feedback = "\n".join(review_data.get("issues", []))
            revision_task = Task(
                id=str(uuid.uuid4())[:8],
                type=original_task.type,
                agent=original_task.agent,
                title=(
                    f"Revision #{original_task.review_count + 1}: {original_task.title}"
                ),
                instruction=(
                    f"# 리뷰어 피드백 (반드시 해결할 것)\n{feedback}\n\n"
                    f"# 원본 지시\n{original_task.instruction}\n\n"
                    + (
                        f"# 이전 작업 결과\n{original_task.result}\n\n"
                        if original_task.result
                        else ""
                    )
                    + "중요: 이전 시도에서 위 피드백의 문제가 발견되었습니다. "
                    "반드시 Edit/Write 도구를 사용하여 파일을 직접 수정하고, "
                    "수정 후 파일을 다시 읽어 "
                    "변경사항이 실제로 적용되었는지 확인하세요. "
                    "도구를 사용하지 않고 결과만 보고하는 것은 허용되지 않습니다."
                ),
                approval_level=original_task.approval_level,
                priority=original_task.priority,
                no_worktree=original_task.no_worktree,
                goal_id=original_task.goal_id,
                parent_task_id=original_task_id,
            )
            await self._store.create_task(revision_task)
