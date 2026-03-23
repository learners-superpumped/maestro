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


def _safe_json_loads(s: Optional[str]) -> object:
    """Safely parse JSON, returning raw string if not valid JSON."""
    if not s:
        return None
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return s  # Return raw string if not valid JSON


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
        result_json=_safe_json_loads(d.get("result_json")),
        error=d.get("error"),
        cost_usd=d.get("cost_usd", 0.0),
        review_count=d.get("review_count", 0),
        created_at=_iso_to_dt(d["created_at"]) or datetime.now(timezone.utc),
        scheduled_at=_iso_to_dt(d.get("scheduled_at")),
        started_at=_iso_to_dt(d.get("started_at")),
        completed_at=_iso_to_dt(d.get("completed_at")),
        timeout_at=_iso_to_dt(d.get("timeout_at")),
        updated_at=_iso_to_dt(d["updated_at"]) or datetime.now(timezone.utc),
    )


def _row_to_asset(d: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw asset row dict, deserializing JSON fields."""
    if d.get("tags") and isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    elif not d.get("tags"):
        d["tags"] = []

    if d.get("platforms_published") and isinstance(d["platforms_published"], str):
        try:
            d["platforms_published"] = json.loads(d["platforms_published"])
        except (json.JSONDecodeError, TypeError):
            d["platforms_published"] = []
    elif not d.get("platforms_published"):
        d["platforms_published"] = []

    return d


def _row_to_action(d: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw action_history row dict, deserializing JSON fields."""
    if d.get("asset_ids") and isinstance(d["asset_ids"], str):
        try:
            d["asset_ids"] = json.loads(d["asset_ids"])
        except (json.JSONDecodeError, TypeError):
            d["asset_ids"] = []
    elif not d.get("asset_ids"):
        d["asset_ids"] = []

    if d.get("metrics") and isinstance(d["metrics"], str):
        try:
            d["metrics"] = json.loads(d["metrics"])
        except (json.JSONDecodeError, TypeError):
            d["metrics"] = {}
    elif not d.get("metrics"):
        d["metrics"] = {}

    return d


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
        await self._migrate()

    async def _migrate(self) -> None:
        try:
            async with self._conn() as db:
                await db.execute(
                    "ALTER TABLE tasks ADD COLUMN review_count INTEGER NOT NULL DEFAULT 0"
                )
                await db.commit()
        except Exception:
            pass

        # NEW: parent_task_id index
        try:
            async with self._conn() as db:
                await db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id)"
                )
                await db.commit()
        except Exception:
            pass

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
                    budget_usd, result_json, error, cost_usd, review_count,
                    created_at, scheduled_at, started_at, completed_at,
                    timeout_at, updated_at
                ) VALUES (
                    :id, :type, :status, :workspace, :title, :instruction,
                    :goal_id, :parent_task_id, :priority, :approval_level,
                    :schedule, :deadline, :session_id, :attempt, :max_retries,
                    :budget_usd, :result_json, :error, :cost_usd, :review_count,
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
                    "result_json": json.dumps(task.result_json)
                    if task.result_json is not None
                    else None,
                    "error": task.error,
                    "cost_usd": task.cost_usd,
                    "review_count": task.review_count,
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
            cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
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
            "session_id",
            "attempt",
            "error",
            "cost_usd",
            "result_json",
            "started_at",
            "completed_at",
            "timeout_at",
            "scheduled_at",
        }
        params: dict[str, Any] = {
            "status": status.value,
            "updated_at": _now_iso(),
            "id": task_id,
        }
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
          - status IN ('approved', 'retry_queued')
          - scheduled_at IS NULL OR scheduled_at <= now (UTC ISO string)

        Ordered by: priority ASC, scheduled_at ASC (NULLs first), created_at ASC.
        """
        now = _now_iso()
        sql = """
            SELECT * FROM tasks
            WHERE status IN ('approved', 'retry_queued')
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

    # ------------------------------------------------------------------
    # Asset CRUD
    # ------------------------------------------------------------------

    async def create_asset(self, asset: dict[str, Any]) -> None:
        """Insert a new asset row."""
        now = _now_iso()
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO assets (
                    id, type, path, title, description, tags,
                    embedding_model, embedded_at, platforms_published,
                    created_at, updated_at
                ) VALUES (
                    :id, :type, :path, :title, :description, :tags,
                    :embedding_model, :embedded_at, :platforms_published,
                    :created_at, :updated_at
                )
                """,
                {
                    "id": asset["id"],
                    "type": asset["type"],
                    "path": asset["path"],
                    "title": asset["title"],
                    "description": asset.get("description"),
                    "tags": json.dumps(asset["tags"]) if asset.get("tags") else None,
                    "embedding_model": asset.get("embedding_model"),
                    "embedded_at": asset.get("embedded_at"),
                    "platforms_published": (
                        json.dumps(asset["platforms_published"])
                        if asset.get("platforms_published")
                        else None
                    ),
                    "created_at": asset.get("created_at", now),
                    "updated_at": asset.get("updated_at", now),
                },
            )
            await db.commit()

    async def get_asset(self, asset_id: str) -> Optional[dict[str, Any]]:
        """Return asset dict or None."""
        async with self._conn() as db:
            cursor = await db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
            row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_asset(dict(row))

    async def list_assets(
        self,
        asset_type: Optional[str] = None,
        tags_contain: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Return assets optionally filtered by type and/or tags."""
        clauses: list[str] = []
        params: list[Any] = []

        if asset_type is not None:
            clauses.append("type = ?")
            params.append(asset_type)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM assets {where} ORDER BY created_at DESC"

        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()

        results = [_row_to_asset(dict(r)) for r in rows]

        # Filter by tags in Python (JSON array stored as text)
        if tags_contain:
            filtered = []
            for a in results:
                asset_tags = a.get("tags") or []
                if any(t in asset_tags for t in tags_contain):
                    filtered.append(a)
            results = filtered

        return results

    async def update_asset(self, asset_id: str, **kwargs: Any) -> None:
        """Update asset fields."""
        allowed = {
            "title",
            "description",
            "tags",
            "embedding_model",
            "embedded_at",
            "platforms_published",
            "type",
            "path",
        }
        params: dict[str, Any] = {"updated_at": _now_iso(), "id": asset_id}
        set_clauses = ["updated_at = :updated_at"]

        for key, value in kwargs.items():
            if key not in allowed:
                raise ValueError(f"update_asset: unknown field '{key}'")
            if key in ("tags", "platforms_published") and isinstance(value, list):
                value = json.dumps(value)
            params[key] = value
            set_clauses.append(f"{key} = :{key}")

        sql = f"UPDATE assets SET {', '.join(set_clauses)} WHERE id = :id"
        async with self._conn() as db:
            await db.execute(sql, params)
            await db.commit()

    # ------------------------------------------------------------------
    # Action History
    # ------------------------------------------------------------------

    async def record_action(self, action: dict[str, Any]) -> None:
        """Insert an action history record."""
        now = _now_iso()
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO action_history (
                    id, task_id, workspace, action_type, platform,
                    content, target_url, asset_ids, result_url, metrics,
                    created_at
                ) VALUES (
                    :id, :task_id, :workspace, :action_type, :platform,
                    :content, :target_url, :asset_ids, :result_url, :metrics,
                    :created_at
                )
                """,
                {
                    "id": action["id"],
                    "task_id": action["task_id"],
                    "workspace": action["workspace"],
                    "action_type": action["action_type"],
                    "platform": action["platform"],
                    "content": action.get("content"),
                    "target_url": action.get("target_url"),
                    "asset_ids": (
                        json.dumps(action["asset_ids"])
                        if action.get("asset_ids")
                        else None
                    ),
                    "result_url": action.get("result_url"),
                    "metrics": (
                        json.dumps(action["metrics"]) if action.get("metrics") else None
                    ),
                    "created_at": action.get("created_at", now),
                },
            )
            await db.commit()

    async def search_history(
        self,
        workspace: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return recent action history, optionally filtered by workspace."""
        clauses: list[str] = []
        params: list[Any] = []

        if workspace is not None:
            clauses.append("workspace = ?")
            params.append(workspace)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM action_history {where} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()

        return [_row_to_action(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    async def create_approval(self, approval: dict[str, Any]) -> None:
        """Insert a new approval record."""
        now = _now_iso()
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO approvals (
                    id, task_id, status, draft_json,
                    reviewer_note, revised_content,
                    created_at, reviewed_at
                ) VALUES (
                    :id, :task_id, :status, :draft_json,
                    :reviewer_note, :revised_content,
                    :created_at, :reviewed_at
                )
                """,
                {
                    "id": approval["id"],
                    "task_id": approval["task_id"],
                    "status": approval.get("status", "pending"),
                    "draft_json": approval["draft_json"],
                    "reviewer_note": approval.get("reviewer_note"),
                    "revised_content": approval.get("revised_content"),
                    "created_at": approval.get("created_at", now),
                    "reviewed_at": approval.get("reviewed_at"),
                },
            )
            await db.commit()

    async def get_approval_by_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """Return the latest approval record for a task, or None."""
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT * FROM approvals"
                " WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def list_approvals(
        self, status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return approval records, optionally filtered by status."""
        if status is not None:
            sql = "SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC"
            params: list[Any] = [status]
        else:
            sql = "SELECT * FROM approvals ORDER BY created_at DESC"
            params = []

        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_approval(self, approval_id: str, **kwargs: Any) -> None:
        """Update fields on an approval record."""
        allowed = {
            "status",
            "reviewer_note",
            "revised_content",
            "reviewed_at",
        }
        params: dict[str, Any] = {"id": approval_id}
        set_clauses: list[str] = []

        for key, value in kwargs.items():
            if key not in allowed:
                raise ValueError(f"update_approval: unknown field '{key}'")
            params[key] = value
            set_clauses.append(f"{key} = :{key}")

        if not set_clauses:
            return

        sql = f"UPDATE approvals SET {', '.join(set_clauses)} WHERE id = :id"
        async with self._conn() as db:
            await db.execute(sql, params)
            await db.commit()

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def create_notification(self, notification: dict[str, Any]) -> None:
        """Insert a new notification record."""
        now = _now_iso()
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO notifications (
                    id, type, task_id, message, delivered, channel, created_at
                ) VALUES (
                    :id, :type, :task_id, :message, :delivered, :channel, :created_at
                )
                """,
                {
                    "id": notification["id"],
                    "type": notification["type"],
                    "task_id": notification.get("task_id"),
                    "message": notification["message"],
                    "delivered": notification.get("delivered", 0),
                    "channel": notification.get("channel", "log"),
                    "created_at": notification.get("created_at", now),
                },
            )
            await db.commit()

    async def list_notifications(
        self,
        channel: Optional[str] = None,
        delivered: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Return notifications, optionally filtered by channel and/or delivered."""
        clauses: list[str] = []
        params: list[Any] = []

        if channel is not None:
            clauses.append("channel = ?")
            params.append(channel)
        if delivered is not None:
            clauses.append("delivered = ?")
            params.append(delivered)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM notifications {where} ORDER BY created_at DESC"

        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_notification(self, notification_id: str, **kwargs: Any) -> None:
        """Update fields on a notification record."""
        allowed = {"delivered"}
        params: dict[str, Any] = {"id": notification_id}
        set_clauses: list[str] = []

        for key, value in kwargs.items():
            if key not in allowed:
                raise ValueError(f"update_notification: unknown field '{key}'")
            params[key] = value
            set_clauses.append(f"{key} = :{key}")

        if not set_clauses:
            return

        sql = f"UPDATE notifications SET {', '.join(set_clauses)} WHERE id = :id"
        async with self._conn() as db:
            await db.execute(sql, params)
            await db.commit()

    # ------------------------------------------------------------------
    # Budget
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Goal State
    # ------------------------------------------------------------------

    async def get_goal_state(self, goal_id: str) -> dict[str, Any] | None:
        """Return the goal_state row for *goal_id*, or None."""
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT * FROM goal_state WHERE goal_id = ?", (goal_id,)
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def update_goal_state(self, goal_id: str, **kwargs: Any) -> None:
        """Upsert goal state.  Creates the row if it doesn't exist yet."""
        allowed = {
            "last_evaluated_at",
            "current_gap",
            "last_task_created_at",
        }
        now = _now_iso()

        for key in kwargs:
            if key not in allowed:
                raise ValueError(f"update_goal_state: unknown field '{key}'")

        async with self._conn() as db:
            # Try INSERT first, then UPDATE on conflict
            cols = ["goal_id", "updated_at"]
            vals = [goal_id, now]
            for key, value in kwargs.items():
                cols.append(key)
                vals.append(value)

            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join(cols)

            update_parts = ["updated_at = excluded.updated_at"]
            for key in kwargs:
                update_parts.append(f"{key} = excluded.{key}")
            update_clause = ", ".join(update_parts)

            sql = (
                f"INSERT INTO goal_state ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT(goal_id) DO UPDATE SET {update_clause}"
            )
            await db.execute(sql, vals)
            await db.commit()

    # ------------------------------------------------------------------
    # Schedule / Scheduler state
    # ------------------------------------------------------------------

    async def get_schedule_last_run(self, name: str) -> str | None:
        async with self._conn() as db:
            async with db.execute(
                "SELECT last_run_at FROM schedule_runs WHERE name = ?", (name,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def set_schedule_last_run(self, name: str, dt_iso: str) -> None:
        async with self._conn() as db:
            await db.execute(
                "INSERT INTO schedule_runs (name, last_run_at) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET last_run_at = excluded.last_run_at",
                (name, dt_iso),
            )
            await db.commit()

    async def get_scheduler_state(self, key: str) -> str | None:
        async with self._conn() as db:
            async with db.execute(
                "SELECT value FROM scheduler_state WHERE key = ?", (key,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def set_scheduler_state(self, key: str, value: str) -> None:
        async with self._conn() as db:
            await db.execute(
                "INSERT INTO scheduler_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            await db.commit()

    async def increment_review_count(self, task_id: str) -> None:
        async with self._conn() as db:
            await db.execute(
                "UPDATE tasks SET review_count = review_count + 1 WHERE id = ?",
                (task_id,),
            )
            await db.commit()

    async def list_children(self, parent_task_id: str) -> list[Task]:
        """Return direct children of a task."""
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT * FROM tasks WHERE parent_task_id = ? ORDER BY created_at ASC",
                (parent_task_id,),
            )
            rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]

    async def find_root_task_id(self, task_id: str) -> str:
        """Walk parent_task_id chain to find root (parent_task_id IS NULL)."""
        current = task_id
        seen: set[str] = set()
        while True:
            if current in seen:
                return current  # cycle protection
            seen.add(current)
            t = await self.get_task(current)
            if t is None or t.parent_task_id is None:
                return current
            current = t.parent_task_id

    async def get_task_tree(self, root_id: str) -> list[Task]:
        """Return root and all descendants using recursive CTE."""
        async with self._conn() as db:
            cursor = await db.execute(
                """
                WITH RECURSIVE tree AS (
                    SELECT * FROM tasks WHERE id = ?
                    UNION ALL
                    SELECT t.* FROM tasks t JOIN tree ON t.parent_task_id = tree.id
                )
                SELECT * FROM tree ORDER BY created_at ASC
                """,
                (root_id,),
            )
            rows = await cursor.fetchall()
        return [_row_to_task(r) for r in rows]

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
