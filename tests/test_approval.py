"""Tests for maestro.approval — Approval Manager."""

from __future__ import annotations

import pathlib
import uuid

import pytest

from maestro.approval import ApprovalManager
from maestro.models import Task, TaskStatus
from maestro.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _task(
    task_id: str | None = None,
    status: TaskStatus = TaskStatus.RUNNING,
    **kwargs,
) -> Task:
    defaults = dict(
        id=task_id or uuid.uuid4().hex[:8],
        type="claude",
        workspace="ws1",
        title="Test task",
        instruction="Do something",
        status=status,
    )
    defaults.update(kwargs)
    return Task(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_submit_draft_pauses_task(db_path: pathlib.Path) -> None:
    """submit_draft should create an approval record and pause the task."""
    store = Store(db_path)
    mgr = ApprovalManager(store)

    task = _task(task_id="sub-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    approval_id = await mgr.submit_draft("sub-1", '{"content": "draft text"}')

    assert approval_id  # non-empty

    # Task should be paused
    updated = await store.get_task("sub-1")
    assert updated is not None
    assert updated.status == TaskStatus.PAUSED

    # Approval record should exist
    approval = await store.get_approval_by_task("sub-1")
    assert approval is not None
    assert approval["status"] == "pending"
    assert approval["draft_json"] == '{"content": "draft text"}'


async def test_approve_sets_task_approved(db_path: pathlib.Path) -> None:
    """approve() should update approval to 'approved' and task to APPROVED."""
    store = Store(db_path)
    mgr = ApprovalManager(store)

    task = _task(task_id="app-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    await mgr.submit_draft("app-1", '{"draft": true}')
    await mgr.approve("app-1")

    updated = await store.get_task("app-1")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED

    approval = await store.get_approval_by_task("app-1")
    assert approval is not None
    assert approval["status"] == "approved"
    assert approval["reviewed_at"] is not None


async def test_reject_cancels_task(db_path: pathlib.Path) -> None:
    """reject() should update approval to 'rejected' and task to CANCELLED."""
    store = Store(db_path)
    mgr = ApprovalManager(store)

    task = _task(task_id="rej-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    await mgr.submit_draft("rej-1", '{"draft": true}')
    await mgr.reject("rej-1", note="Not good enough")

    updated = await store.get_task("rej-1")
    assert updated is not None
    assert updated.status == TaskStatus.CANCELLED

    approval = await store.get_approval_by_task("rej-1")
    assert approval is not None
    assert approval["status"] == "rejected"
    assert approval["reviewer_note"] == "Not good enough"


async def test_revise_with_note(db_path: pathlib.Path) -> None:
    """revise() should set approval to 'revised' and task back to APPROVED."""
    store = Store(db_path)
    mgr = ApprovalManager(store)

    task = _task(task_id="rev-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    await mgr.submit_draft("rev-1", '{"draft": true}')
    await mgr.revise("rev-1", note="Fix the intro", revised_content="New intro text")

    updated = await store.get_task("rev-1")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED

    approval = await store.get_approval_by_task("rev-1")
    assert approval is not None
    assert approval["status"] == "revised"
    assert approval["reviewer_note"] == "Fix the intro"
    assert approval["revised_content"] == "New intro text"


async def test_get_pending_approvals(db_path: pathlib.Path) -> None:
    """get_pending_approvals should return only pending approvals with task info."""
    store = Store(db_path)
    mgr = ApprovalManager(store)

    t1 = _task(task_id="pend-1", status=TaskStatus.RUNNING, title="Task One")
    t2 = _task(task_id="pend-2", status=TaskStatus.RUNNING, title="Task Two")
    await store.create_task(t1)
    await store.create_task(t2)

    await mgr.submit_draft("pend-1", '{"d":1}')
    await mgr.submit_draft("pend-2", '{"d":2}')

    # Approve one
    await mgr.approve("pend-1")

    pending = await mgr.get_pending_approvals()
    assert len(pending) == 1
    assert pending[0]["task_id"] == "pend-2"
    assert pending[0]["task_title"] == "Task Two"


async def test_get_approval_for_task(db_path: pathlib.Path) -> None:
    """get_approval should return the latest approval or None."""
    store = Store(db_path)
    mgr = ApprovalManager(store)

    # No approval yet
    result = await mgr.get_approval("nonexistent")
    assert result is None

    task = _task(task_id="get-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    await mgr.submit_draft("get-1", '{"content": "test"}')

    result = await mgr.get_approval("get-1")
    assert result is not None
    assert result["task_id"] == "get-1"
    assert result["status"] == "pending"


async def test_approve_without_approval_record_raises(db_path: pathlib.Path) -> None:
    """approve() should raise ValueError if no approval record exists."""
    store = Store(db_path)
    mgr = ApprovalManager(store)

    task = _task(task_id="no-appr", status=TaskStatus.PAUSED)
    await store.create_task(task)

    with pytest.raises(ValueError, match="No approval record"):
        await mgr.approve("no-appr")
