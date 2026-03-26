"""
TDD tests for maestro.models

Tests cover:
- TaskStatus valid/invalid transitions
- Task creation with defaults
- Task.is_dispatchable()
- Task.needs_auto_approval()
- Task.retry_backoff_ms()
- TaskResult creation
"""

from datetime import datetime, timezone

import pytest

from maestro.models import (
    VALID_TRANSITIONS,
    InvalidTransitionError,
    Task,
    TaskResult,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# TaskStatus – valid transitions
# ---------------------------------------------------------------------------


class TestTaskStatusTransitions:
    """Verify that VALID_TRANSITIONS covers the spec state machine exactly."""

    def test_pending_can_transition_to_approved(self):
        assert TaskStatus.APPROVED in VALID_TRANSITIONS[TaskStatus.PENDING]

    def test_pending_can_transition_to_cancelled(self):
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.PENDING]

    def test_approved_can_transition_to_claimed(self):
        assert TaskStatus.CLAIMED in VALID_TRANSITIONS[TaskStatus.APPROVED]

    def test_approved_can_transition_to_cancelled(self):
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.APPROVED]

    def test_claimed_can_transition_to_running(self):
        assert TaskStatus.RUNNING in VALID_TRANSITIONS[TaskStatus.CLAIMED]

    def test_claimed_can_transition_to_retry_queued(self):
        assert TaskStatus.RETRY_QUEUED in VALID_TRANSITIONS[TaskStatus.CLAIMED]

    def test_running_can_transition_to_completed(self):
        assert TaskStatus.COMPLETED in VALID_TRANSITIONS[TaskStatus.RUNNING]

    def test_running_can_transition_to_paused(self):
        assert TaskStatus.PAUSED in VALID_TRANSITIONS[TaskStatus.RUNNING]

    def test_running_can_transition_to_retry_queued(self):
        assert TaskStatus.RETRY_QUEUED in VALID_TRANSITIONS[TaskStatus.RUNNING]

    def test_running_can_transition_to_failed(self):
        assert TaskStatus.FAILED in VALID_TRANSITIONS[TaskStatus.RUNNING]

    def test_paused_can_transition_to_approved(self):
        assert TaskStatus.APPROVED in VALID_TRANSITIONS[TaskStatus.PAUSED]

    def test_paused_can_transition_to_cancelled(self):
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.PAUSED]

    def test_retry_queued_can_transition_to_claimed(self):
        assert TaskStatus.CLAIMED in VALID_TRANSITIONS[TaskStatus.RETRY_QUEUED]

    def test_retry_queued_can_transition_to_cancelled(self):
        assert TaskStatus.CANCELLED in VALID_TRANSITIONS[TaskStatus.RETRY_QUEUED]

    def test_completed_has_no_outgoing_transitions(self):
        assert VALID_TRANSITIONS[TaskStatus.COMPLETED] == set()

    def test_failed_has_no_outgoing_transitions(self):
        assert VALID_TRANSITIONS[TaskStatus.FAILED] == set()

    def test_cancelled_has_no_outgoing_transitions(self):
        assert VALID_TRANSITIONS[TaskStatus.CANCELLED] == set()


class TestTaskStatusInvalidTransitions:
    """Verify that illegal transitions are rejected."""

    def test_pending_cannot_jump_to_running(self):
        assert TaskStatus.RUNNING not in VALID_TRANSITIONS[TaskStatus.PENDING]

    def test_pending_cannot_jump_to_completed(self):
        assert TaskStatus.COMPLETED not in VALID_TRANSITIONS[TaskStatus.PENDING]

    def test_approved_cannot_jump_to_completed(self):
        assert TaskStatus.COMPLETED not in VALID_TRANSITIONS[TaskStatus.APPROVED]

    def test_completed_cannot_go_back_to_running(self):
        assert TaskStatus.RUNNING not in VALID_TRANSITIONS[TaskStatus.COMPLETED]

    def test_failed_cannot_go_back_to_pending(self):
        assert TaskStatus.PENDING not in VALID_TRANSITIONS[TaskStatus.FAILED]


# ---------------------------------------------------------------------------
# Task – creation with defaults
# ---------------------------------------------------------------------------


class TestTaskCreation:
    """Verify Task can be created and default values are applied correctly."""

    def _make_task(self, **kwargs):
        defaults = dict(
            id="task-001",
            type="shell",
            title="Test task",
            instruction="echo hello",
        )
        defaults.update(kwargs)
        return Task(**defaults)

    def test_task_creates_with_required_fields(self):
        task = self._make_task()
        assert task.id == "task-001"
        assert task.type == "shell"
        assert task.title == "Test task"
        assert task.instruction == "echo hello"

    def test_task_default_status_is_pending(self):
        task = self._make_task()
        assert task.status == TaskStatus.PENDING

    def test_task_default_priority_is_3(self):
        task = self._make_task()
        assert task.priority == 3

    def test_task_default_approval_level_is_2(self):
        task = self._make_task()
        assert task.approval_level == 2

    def test_task_default_attempt_is_0(self):
        task = self._make_task()
        assert task.attempt == 0

    def test_task_default_max_retries_is_3(self):
        task = self._make_task()
        assert task.max_retries == 3

    def test_task_default_budget_usd_is_5(self):
        task = self._make_task()
        assert task.budget_usd == 5.0

    def test_task_default_cost_usd_is_0(self):
        task = self._make_task()
        assert task.cost_usd == 0.0

    def test_task_optional_fields_default_to_none(self):
        task = self._make_task()
        assert task.goal_id is None
        assert task.parent_task_id is None
        assert task.schedule is None
        assert task.deadline is None
        assert task.session_id is None
        assert task.result is None
        assert task.error is None
        assert task.scheduled_at is None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.timeout_at is None

    def test_task_created_at_is_set_automatically(self):
        before = datetime.now(timezone.utc)
        task = self._make_task()
        after = datetime.now(timezone.utc)
        assert before <= task.created_at <= after

    def test_task_updated_at_is_set_automatically(self):
        before = datetime.now(timezone.utc)
        task = self._make_task()
        after = datetime.now(timezone.utc)
        assert before <= task.updated_at <= after

    def test_task_accepts_custom_priority(self):
        task = self._make_task(priority=1)
        assert task.priority == 1

    def test_task_accepts_custom_approval_level(self):
        task = self._make_task(approval_level=0)
        assert task.approval_level == 0

    def test_task_accepts_goal_id(self):
        task = self._make_task(goal_id="goal-42")
        assert task.goal_id == "goal-42"

    def test_task_accepts_parent_task_id(self):
        task = self._make_task(parent_task_id="task-parent")
        assert task.parent_task_id == "task-parent"

    def test_task_default_agent_is_default(self):
        task = self._make_task()
        assert task.agent == "default"

    def test_task_accepts_custom_agent(self):
        task = self._make_task(agent="researcher")
        assert task.agent == "researcher"

    def test_task_default_no_worktree_is_false(self):
        task = self._make_task()
        assert task.no_worktree is False

    def test_task_accepts_no_worktree_true(self):
        task = self._make_task(no_worktree=True)
        assert task.no_worktree is True


# ---------------------------------------------------------------------------
# Task.is_dispatchable()
# ---------------------------------------------------------------------------


class TestIsDispatchable:
    """is_dispatchable() must return True iff status == APPROVED."""

    def _make_task(self, status: TaskStatus) -> Task:
        return Task(
            id="task-dispatch",
            type="shell",
            title="dispatch test",
            instruction="echo hi",
            status=status,
        )

    def test_approved_is_dispatchable(self):
        assert self._make_task(TaskStatus.APPROVED).is_dispatchable() is True

    def test_pending_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.PENDING).is_dispatchable() is False

    def test_claimed_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.CLAIMED).is_dispatchable() is False

    def test_running_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.RUNNING).is_dispatchable() is False

    def test_completed_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.COMPLETED).is_dispatchable() is False

    def test_paused_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.PAUSED).is_dispatchable() is False

    def test_retry_queued_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.RETRY_QUEUED).is_dispatchable() is False

    def test_failed_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.FAILED).is_dispatchable() is False

    def test_cancelled_is_not_dispatchable(self):
        assert self._make_task(TaskStatus.CANCELLED).is_dispatchable() is False


# ---------------------------------------------------------------------------
# Task.needs_auto_approval()
# ---------------------------------------------------------------------------


class TestNeedsAutoApproval:
    """needs_auto_approval() returns True if PENDING and approval_level in {0, 1}."""

    def _make_task(self, status: TaskStatus, approval_level: int) -> Task:
        return Task(
            id="task-auto",
            type="shell",
            title="auto approval test",
            instruction="echo hi",
            status=status,
            approval_level=approval_level,
        )

    def test_pending_level_0_needs_auto_approval(self):
        assert self._make_task(TaskStatus.PENDING, 0).needs_auto_approval() is True

    def test_pending_level_1_needs_auto_approval(self):
        assert self._make_task(TaskStatus.PENDING, 1).needs_auto_approval() is True

    def test_pending_level_2_does_not_need_auto_approval(self):
        assert self._make_task(TaskStatus.PENDING, 2).needs_auto_approval() is False

    def test_approved_level_0_does_not_need_auto_approval(self):
        # Only PENDING status triggers auto approval
        assert self._make_task(TaskStatus.APPROVED, 0).needs_auto_approval() is False

    def test_approved_level_1_does_not_need_auto_approval(self):
        assert self._make_task(TaskStatus.APPROVED, 1).needs_auto_approval() is False

    def test_running_level_0_does_not_need_auto_approval(self):
        assert self._make_task(TaskStatus.RUNNING, 0).needs_auto_approval() is False


# ---------------------------------------------------------------------------
# Task.retry_backoff_ms()
# ---------------------------------------------------------------------------


class TestRetryBackoffMs:
    """retry_backoff_ms() = min(10000 * 2^(attempt-1), 300_000)"""

    def _make_task(self, attempt: int) -> Task:
        return Task(
            id="task-retry",
            type="shell",
            title="retry test",
            instruction="echo hi",
            attempt=attempt,
        )

    def test_attempt_0_returns_base_value(self):
        # 2^(0-1) = 2^-1 = 0.5 → 10000 * 0.5 = 5000
        assert self._make_task(0).retry_backoff_ms() == 5000

    def test_attempt_1_returns_10000(self):
        # 10000 * 2^(1-1) = 10000 * 1 = 10000
        assert self._make_task(1).retry_backoff_ms() == 10_000

    def test_attempt_2_returns_20000(self):
        # 10000 * 2^(2-1) = 10000 * 2 = 20000
        assert self._make_task(2).retry_backoff_ms() == 20_000

    def test_attempt_3_returns_40000(self):
        # 10000 * 2^(3-1) = 10000 * 4 = 40000
        assert self._make_task(3).retry_backoff_ms() == 40_000

    def test_attempt_4_returns_80000(self):
        assert self._make_task(4).retry_backoff_ms() == 80_000

    def test_attempt_5_returns_160000(self):
        assert self._make_task(5).retry_backoff_ms() == 160_000

    def test_attempt_6_returns_capped_at_300000(self):
        # 10000 * 2^5 = 320000 > 300000 → capped
        assert self._make_task(6).retry_backoff_ms() == 300_000

    def test_large_attempt_always_capped(self):
        assert self._make_task(100).retry_backoff_ms() == 300_000


# ---------------------------------------------------------------------------
# Task.transition_to() – optional guard method
# ---------------------------------------------------------------------------


class TestTransitionTo:
    """If Task exposes a transition_to() method, it must enforce valid transitions."""

    def _make_task(self, status: TaskStatus = TaskStatus.PENDING) -> Task:
        return Task(
            id="task-trans",
            type="shell",
            title="transition test",
            instruction="echo hi",
            status=status,
        )

    def test_valid_transition_updates_status(self):
        task = self._make_task(TaskStatus.PENDING)
        task.transition_to(TaskStatus.APPROVED)
        assert task.status == TaskStatus.APPROVED

    def test_invalid_transition_raises_error(self):
        task = self._make_task(TaskStatus.PENDING)
        with pytest.raises(InvalidTransitionError):
            task.transition_to(TaskStatus.RUNNING)

    def test_transition_from_terminal_raises_error(self):
        task = self._make_task(TaskStatus.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            task.transition_to(TaskStatus.RUNNING)

    def test_valid_chain_pending_approved_claimed_running_completed(self):
        task = self._make_task(TaskStatus.PENDING)
        task.transition_to(TaskStatus.APPROVED)
        task.transition_to(TaskStatus.CLAIMED)
        task.transition_to(TaskStatus.RUNNING)
        task.transition_to(TaskStatus.COMPLETED)
        assert task.status == TaskStatus.COMPLETED

    def test_transition_updates_updated_at(self):
        task = self._make_task(TaskStatus.PENDING)
        old_updated_at = task.updated_at
        # Ensure time progresses
        import time

        time.sleep(0.001)
        task.transition_to(TaskStatus.APPROVED)
        assert task.updated_at >= old_updated_at


# ---------------------------------------------------------------------------
# TaskResult
# ---------------------------------------------------------------------------


class TestTaskResult:
    """TaskResult dataclass basic creation."""

    def test_task_result_success(self):
        result = TaskResult(
            task_id="task-001",
            success=True,
            result={"output": "hello"},
        )
        assert result.task_id == "task-001"
        assert result.success is True
        assert result.result == {"output": "hello"}

    def test_task_result_failure(self):
        result = TaskResult(
            task_id="task-002",
            success=False,
            error="command not found",
        )
        assert result.success is False
        assert result.error == "command not found"

    def test_task_result_defaults(self):
        result = TaskResult(task_id="task-003", success=True)
        assert result.session_id is None
        assert result.result is None
        assert result.error is None
        assert result.cost_usd == 0.0

    def test_task_result_with_session_id(self):
        result = TaskResult(
            task_id="task-004",
            success=True,
            session_id="sess-abc",
            cost_usd=1.23,
        )
        assert result.session_id == "sess-abc"
        assert result.cost_usd == 1.23
