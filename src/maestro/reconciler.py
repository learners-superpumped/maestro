"""
Maestro Reconciler.

Periodically scans running tasks and handles timed-out tasks by either
requeueing them for retry or marking them as failed.

Stall detection (no events for N seconds) is deferred to Phase 2.
Turn timeout is sufficient for Phase 1.
"""

from __future__ import annotations

from datetime import datetime, timezone

from maestro.models import Task, TaskStatus
from maestro.store import Store


class Reconciler:
    """Reconciles running tasks against their timeout deadlines."""

    def __init__(self, store: Store, stall_timeout_ms: int) -> None:
        self._store = store
        self._stall_timeout_ms = stall_timeout_ms

    async def find_timed_out_tasks(self) -> list[Task]:
        """Find running tasks where timeout_at is in the past."""
        now = datetime.now(timezone.utc)
        running = await self._store.list_tasks(status=TaskStatus.RUNNING)
        return [t for t in running if t.timeout_at is not None and t.timeout_at < now]

    def should_retry(self, task: Task) -> bool:
        """Return True if the task has retry attempts remaining."""
        return task.attempt < task.max_retries

    async def handle_timeout(self, task: Task) -> None:
        """Handle a timed-out task: requeue for retry or mark failed."""
        if self.should_retry(task):
            await self._store.update_task_status(
                task.id,
                TaskStatus.RETRY_QUEUED,
                attempt=task.attempt + 1,
                error="Timed out",
            )
        else:
            await self._store.update_task_status(
                task.id,
                TaskStatus.FAILED,
                error="Max retries exhausted",
            )

    async def reconcile(self) -> None:
        """Run one reconciliation pass over all running tasks."""
        for task in await self.find_timed_out_tasks():
            await self.handle_timeout(task)
