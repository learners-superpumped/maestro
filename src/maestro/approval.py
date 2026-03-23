"""
Maestro Approval Manager.

Coordinates the approval workflow: submit drafts for review, approve, reject,
or request revisions on paused tasks.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from maestro.models import TaskStatus
from maestro.store import Store

logger = logging.getLogger(__name__)


class ApprovalManager:
    """Manages the approval lifecycle for tasks that require human review."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def submit_draft(self, task_id: str, draft_json: str) -> str:
        """Submit a draft for approval.

        Creates an approval record with status='pending' and pauses the task.

        Returns the approval_id.
        """
        approval_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()

        await self._store.create_approval(
            {
                "id": approval_id,
                "task_id": task_id,
                "status": "pending",
                "draft_json": draft_json,
                "created_at": now,
            }
        )

        await self._store.update_task_status(task_id, TaskStatus.PAUSED)

        logger.info("Draft submitted for task %s (approval=%s)", task_id, approval_id)
        return approval_id

    async def approve(self, task_id: str) -> None:
        """Approve a pending approval and set the task back to APPROVED."""
        approval = await self._store.get_approval_by_task(task_id)
        if approval is None:
            raise ValueError(f"No approval record found for task {task_id}")

        now = datetime.now(timezone.utc).isoformat()
        await self._store.update_approval(
            approval["id"],
            status="approved",
            reviewed_at=now,
        )

        await self._store.update_task_status(task_id, TaskStatus.APPROVED)
        logger.info("Approved task %s (approval=%s)", task_id, approval["id"])

    async def reject(self, task_id: str, note: str | None = None) -> None:
        """Reject an approval and cancel the task."""
        approval = await self._store.get_approval_by_task(task_id)
        if approval is None:
            raise ValueError(f"No approval record found for task {task_id}")

        now = datetime.now(timezone.utc).isoformat()
        update_kwargs: dict[str, Any] = {
            "status": "rejected",
            "reviewed_at": now,
        }
        if note:
            update_kwargs["reviewer_note"] = note

        await self._store.update_approval(approval["id"], **update_kwargs)
        await self._store.update_task_status(task_id, TaskStatus.CANCELLED)
        logger.info("Rejected task %s (approval=%s)", task_id, approval["id"])

    async def revise(
        self,
        task_id: str,
        note: str,
        revised_content: str | None = None,
    ) -> None:
        """Request revision. Sets the task back to APPROVED with feedback."""
        approval = await self._store.get_approval_by_task(task_id)
        if approval is None:
            raise ValueError(f"No approval record found for task {task_id}")

        now = datetime.now(timezone.utc).isoformat()
        update_kwargs: dict[str, Any] = {
            "status": "revised",
            "reviewer_note": note,
            "reviewed_at": now,
        }
        if revised_content is not None:
            update_kwargs["revised_content"] = revised_content

        await self._store.update_approval(approval["id"], **update_kwargs)
        await self._store.update_task_status(task_id, TaskStatus.APPROVED)
        logger.info(
            "Revision requested for task %s (approval=%s)", task_id, approval["id"]
        )

    async def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all pending approvals with task info."""
        approvals = await self._store.list_approvals(status="pending")
        results = []
        for appr in approvals:
            task = await self._store.get_task(appr["task_id"])
            entry: dict[str, Any] = dict(appr)
            if task:
                entry["task_title"] = task.title
                entry["task_workspace"] = task.workspace
                entry["task_status"] = task.status.value
            results.append(entry)
        return results

    async def get_approval(self, task_id: str) -> Optional[dict[str, Any]]:
        """Get the latest approval record for a task."""
        return await self._store.get_approval_by_task(task_id)
