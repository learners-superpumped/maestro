"""
Maestro data models.

Defines the TaskStatus state machine, the Task and TaskResult dataclasses,
and the VALID_TRANSITIONS mapping that enforces the spec state machine.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# TaskStatus
# ---------------------------------------------------------------------------


class TaskStatus(str, enum.Enum):
    """All possible states a Task can be in."""

    PENDING = "pending"
    APPROVED = "approved"
    CLAIMED = "claimed"
    RUNNING = "running"
    PAUSED = "paused"
    RETRY_QUEUED = "retry_queued"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

#: Maps each status to the set of statuses it may legally transition to.
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.APPROVED, TaskStatus.CANCELLED},
    TaskStatus.APPROVED: {TaskStatus.CLAIMED, TaskStatus.CANCELLED},
    TaskStatus.CLAIMED: {TaskStatus.RUNNING, TaskStatus.RETRY_QUEUED},
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.PAUSED,
        TaskStatus.RETRY_QUEUED,
        TaskStatus.FAILED,
    },
    TaskStatus.PAUSED: {TaskStatus.APPROVED, TaskStatus.CANCELLED},
    TaskStatus.RETRY_QUEUED: {TaskStatus.CLAIMED, TaskStatus.CANCELLED},
    # Terminal states – no outgoing transitions
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
}


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InvalidTransitionError(Exception):
    """Raised when a Task.transition_to() call violates the state machine."""

    def __init__(self, from_status: TaskStatus, to_status: TaskStatus) -> None:
        super().__init__(
            f"Cannot transition from '{from_status.value}' to '{to_status.value}'"
        )
        self.from_status = from_status
        self.to_status = to_status


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """
    Represents a single unit of work managed by Maestro.

    Required fields
    ---------------
    id          : Unique task identifier
    type        : Task type (e.g. "shell", "claude")
    workspace   : Absolute path to the working directory
    title       : Human-readable title
    instruction : The instruction / command to execute

    Optional fields (all default to None unless noted)
    ---------------------------------------------------
    goal_id         : Parent goal identifier
    parent_task_id  : ID of a parent task (for sub-tasks)
    status          : Current state (default: PENDING)
    priority        : 1 (urgent) – 5 (low), default 3
    approval_level  : 0 = auto, 1 = post-notify, 2 = pre-approve (default 2)
    schedule        : Cron expression for recurring tasks
    deadline        : Hard deadline datetime
    session_id      : UUID captured from Claude CLI session
    attempt         : Number of execution attempts so far (default 0)
    max_retries     : Maximum retry attempts (default 3)
    budget_usd      : Max spend allowed in USD (default 5.0)
    result_json     : Structured output from the last execution
    error           : Error message from the last failure
    cost_usd        : Accumulated cost in USD (default 0.0)
    created_at      : Creation timestamp (auto-set)
    scheduled_at    : When the task is next scheduled to run
    started_at      : When execution last began
    completed_at    : When execution last completed/failed
    timeout_at      : Execution deadline
    updated_at      : Last modification timestamp (auto-set)
    """

    # --- Required fields ---
    id: str
    type: str
    workspace: str
    title: str
    instruction: str

    # --- Optional identifiers ---
    goal_id: Optional[str] = None
    parent_task_id: Optional[str] = None

    # --- State ---
    status: TaskStatus = TaskStatus.PENDING

    # --- Scheduling & priority ---
    priority: int = 3
    approval_level: int = 2
    schedule: Optional[str] = None
    deadline: Optional[datetime] = None

    # --- Execution tracking ---
    session_id: Optional[str] = None
    attempt: int = 0
    max_retries: int = 3
    budget_usd: float = 5.0

    # --- Results ---
    result_json: Optional[Any] = None
    error: Optional[str] = None
    cost_usd: float = 0.0
    review_count: int = 0

    # --- Timestamps (auto-set) ---
    created_at: datetime = field(default_factory=_now)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=_now)

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def transition_to(self, new_status: TaskStatus) -> None:
        """
        Transition this task to *new_status*, enforcing the state machine.

        Raises
        ------
        InvalidTransitionError
            If the transition from the current status to *new_status* is not
            permitted by the spec state machine.
        """
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidTransitionError(self.status, new_status)
        self.status = new_status
        self.updated_at = _now()

    # ------------------------------------------------------------------
    # Business logic helpers
    # ------------------------------------------------------------------

    def is_dispatchable(self) -> bool:
        """Return True iff the task is ready to be dispatched to a worker."""
        return self.status == TaskStatus.APPROVED

    def needs_auto_approval(self) -> bool:
        """
        Return True if the task should be auto-approved without human review.

        Conditions: status is PENDING *and* approval_level is 0 (auto) or
        1 (post-notify, i.e. approve first, notify afterwards).
        """
        return self.status == TaskStatus.PENDING and self.approval_level in (0, 1)

    def retry_backoff_ms(self) -> int:
        """
        Exponential back-off delay for the next retry attempt in milliseconds.

        Formula: min(10_000 * 2^(attempt - 1), 300_000)

        This intentionally handles attempt == 0 gracefully:
        2^(0-1) = 0.5  →  10_000 * 0.5 = 5_000 ms.
        """
        raw = 10_000 * (2 ** (self.attempt - 1))
        return int(min(raw, 300_000))


# ---------------------------------------------------------------------------
# TaskResult
# ---------------------------------------------------------------------------


@dataclass
class TaskResult:
    """
    Captures the outcome of a single task execution.

    Fields
    ------
    task_id     : ID of the task that was executed
    success     : Whether execution succeeded
    session_id  : Claude CLI session UUID (if applicable)
    result_json : Structured output (optional)
    error       : Error message on failure (optional)
    cost_usd    : Cost incurred by this execution (default 0.0)
    """

    task_id: str
    success: bool
    session_id: Optional[str] = None
    result_json: Optional[Any] = None
    error: Optional[str] = None
    cost_usd: float = 0.0
