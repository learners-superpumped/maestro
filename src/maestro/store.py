"""
Maestro SQLite persistence layer.

All database access goes through this module.  Every connection enables
WAL journal mode for better concurrent read performance.
"""

from __future__ import annotations

import json
import pathlib
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

import aiosqlite

from maestro.models import Task, TaskStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCHEMA_PATH = pathlib.Path(__file__).resolve().parent / "schema.sql"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt_to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


def _iso_to_dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _row_to_task(row: aiosqlite.Row) -> Task:
    """Convert a sqlite3.Row (from tasks table) into a Task dataclass."""
    d: dict[str, Any] = dict(row)
    return Task(
        id=d["id"],
        type=d["type"],
        workspace=d["workspace"],
        title=d["title"],
        instruction=d["instruction"],
        status=TaskStatus(d["status"]),
        goal_id=d.get("goal_id"),
        parent_task_id=d.get("parent_task_id"),
        priority=d.get("priority", 3),
        approval_level=d.get("approval_level", 2),
        schedule=d.get("schedule"),
        deadline=_iso_to_dt(d.get("deadline")),
        session_id=d.get("session_id"),
        attempt=d.get("attempt", 0),
        max_retries=d.get("max_retries", 3),
        budget_usd=d.get("budget_usd", 5.0),
        result_json=json.loads(d["result_json"]) if d.get("result_json") else None,
        error=d.get("error"),
        cost_usd=d.get("cost_usd", 0.0),
        created_at=_iso_to_dt(d["created_at"]) or datetime.now(timezone.utc),
        scheduled_at=_iso_to_dt(d.get("scheduled_at")),
        started_at=_iso_to_dt(d.get("started_at")),
        completed_at=_iso_to_dt(d.get("completed_at")),
        timeout_at=_iso_to_dt(d.get("timeout_at")),
        updated_at=_iso_to_dt(d["updated_at"]) or datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class Store:
    """Async SQLite store for Maestro tasks and related entities."""

    def __init__(self, db_path: pathlib.Path | str) -> None:
        self._db_path = str(db_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def _conn(self) -> AsyncIterator[aiosqlite.Connection]:
        """Async context manager that yields a WAL-mode connection."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            yield db

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def init_db(self) -> None:
        """Apply schema.sql to the database (idempotent)."""
        schema_sql = _SCHEMA_PATH.read_text()
        async with self._conn() as db:
            await db.executescript(schema_sql)
            await db.commit()

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------

    async def create_task(self, task: Task) -> None:
        """Insert a new task row."""
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO tasks (
                    id, type, status, workspace, title, instruction,
                    goal_id, parent_task_id, priority, approval_level,
                    schedule, deadline, session_id, attempt, max_retries,
                    budget_usd, result_json, error, cost_usd,
                    created_at, scheduled_at, started_at, completed_at,
                    timeout_at, updated_at
                ) VALUES (
                    :id, :type, :status, :workspace, :title, :instruction,
                    :goal_id, :parent_task_id, :priority, :approval_level,
                    :schedule, :deadline, :session_id, :attempt, :max_retries,
                    :budget_usd, :result_json, :error, :cost_usd,
                    :created_at, :scheduled_at, :started_at, :completed_at,
                    :timeout_at, :updated_at
                )
                """,
                {
                    "id": task.id,
                    "type": task.type,
                    "status": task.status.value,
                    "workspace": task.workspace,
                    "title": task.title,
                    "instruction": task.instruction,
                    "goal_id": task.goal_id,
                    "parent_task_id": task.parent_task_id,
                    "priority": task.priority,
                    "approval_level": task.approval_level,
                    "schedule": task.schedule,
                    "deadline": _dt_to_iso(task.deadline),
                    "session_id": task.session_id,
                    "attempt": task.attempt,
                    "max_retries": task.max_retries,
                    "budget_usd": task.budget_usd,
                    "result_json": json.dumps(task.result_json) if task.result_json is not None else None,
                    "error": task.error,
                    "cost_usd": task.cost_usd,
                    "created_at": _dt_to_iso(task.created_at),
                    "scheduled_at": _dt_to_iso(task.scheduled_at),
                    "started_at": _dt_to_iso(task.started_at),
                    "completed_at": _dt_to_iso(task.completed_at),
                    "timeout_at": _dt_to_iso(task.timeout_at),
                    "updated_at": _dt_to_iso(task.updated_at),
                },
            )
            await db.commit()

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Return the Task with *task_id*, or None if not found."""
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_task(row)

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        **kwargs: Any,
    ) -> None:
        """
        Update the status of a task and any additional column values.

        Extra keyword arguments are passed as column=value pairs and must
        correspond to valid column names in the tasks table.
        """
        allowed_extra = {
            "session_id", "attempt", "error", "cost_usd", "result_json",
            "started_at", "completed_at", "timeout_at", "scheduled_at",
        }
        params: dict[str, Any] = {"status": status.value, "updated_at": _now_iso(), "id": task_id}
        set_clauses = ["status = :status", "updated_at = :updated_at"]

        for key, value in kwargs.items():
            if key not in allowed_extra:
                raise ValueError(f"update_task_status: unknown field '{key}'")
            params[key] = value
            set_clauses.append(f"{key} = :{key}")

        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = :id"
        async with self._conn() as db:
            await db.execute(sql, params)
            await db.commit()

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        workspace: Optional[str] = None,
    ) -> list[Task]:
        """Return tasks optionally filtered by status and/or workspace."""
        clauses: list[str] = []
        params: list[Any] = []

        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if workspace is not None:
            clauses.append("workspace = ?")
            params.append(workspace)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM tasks {where} ORDER BY created_at ASC"

        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()

        return [_row_to_task(r) for r in rows]

    async def list_dispatchable_tasks(self) -> list[Task]:
        """
        Return tasks that are ready to be dispatched.

        Criteria:
          - status = 'approved'
          - scheduled_at IS NULL OR scheduled_at <= now (UTC ISO string)

        Ordered by: priority ASC, scheduled_at ASC (NULLs first), created_at ASC.
        """
        now = _now_iso()
        sql = """
            SELECT * FROM tasks
            WHERE status = 'approved'
              AND (scheduled_at IS NULL OR scheduled_at <= ?)
            ORDER BY priority ASC,
                     CASE WHEN scheduled_at IS NULL THEN 0 ELSE 1 END ASC,
                     scheduled_at ASC,
                     created_at ASC
        """
        async with self._conn() as db:
            cursor = await db.execute(sql, (now,))
            rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]

    async def count_running(self, workspace: Optional[str] = None) -> int:
        """
        Count tasks currently running or claimed.

        If *workspace* is given, restrict to that workspace only.
        """
        params: list[Any] = []
        workspace_clause = ""
        if workspace is not None:
            workspace_clause = "AND workspace = ?"
            params.append(workspace)

        sql = f"""
            SELECT COUNT(*) FROM tasks
            WHERE status IN ('running', 'claimed')
            {workspace_clause}
        """
        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    async def get_daily_spend(self, date: str) -> float:
        """Return total spend for *date* (YYYY-MM-DD), or 0.0 if no record."""
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT total_cost_usd FROM budget_daily WHERE date = ?", (date,)
            )
            row = await cursor.fetchone()
        return row[0] if row else 0.0

    async def record_spend(self, date: str, amount: float) -> None:
        """
        Upsert *amount* into budget_daily for *date*.

        On conflict (same date), accumulate the cost.
        """
        now = _now_iso()
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO budget_daily (date, total_cost_usd, task_count, updated_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_cost_usd = total_cost_usd + excluded.total_cost_usd,
                    task_count = task_count + 1,
                    updated_at = excluded.updated_at
                """,
                (date, amount, now),
            )
            await db.commit()
