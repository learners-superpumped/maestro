"""
Maestro SQLite persistence layer.

All database access goes through this module.  Every connection enables
WAL journal mode for better concurrent read performance.
"""

from __future__ import annotations

import json
import pathlib
import secrets
import struct
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

import aiosqlite

try:
    import sqlite_vec

    _HAS_SQLITE_VEC = True
except ImportError:
    _HAS_SQLITE_VEC = False

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
        title=d["title"],
        instruction=d["instruction"],
        status=TaskStatus(d["status"]),
        agent=d.get("agent", "default"),
        no_worktree=bool(d.get("no_worktree", 0)),
        goal_id=d.get("goal_id"),
        parent_task_id=d.get("parent_task_id"),
        depends_on=d.get("depends_on"),
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

    if d.get("content_json") and isinstance(d["content_json"], str):
        try:
            d["content_json"] = json.loads(d["content_json"])
        except (json.JSONDecodeError, TypeError):
            pass  # Keep as raw string

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


def _has_tags(asset: dict, required_tags: list[str]) -> bool:
    """Check if an asset has all required tags."""
    asset_tags = asset.get("tags")
    if not asset_tags:
        return False
    if isinstance(asset_tags, str):
        try:
            asset_tags = json.loads(asset_tags)
        except (json.JSONDecodeError, TypeError):
            return False
    return all(t in asset_tags for t in required_tags)


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
        db = await aiosqlite.connect(self._db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        # Load sqlite-vec on every connection (if available)
        if _HAS_SQLITE_VEC and hasattr(db._connection, "enable_load_extension"):
            db._connection.enable_load_extension(True)
            sqlite_vec.load(db._connection)
            db._connection.enable_load_extension(False)
        try:
            yield db
        finally:
            await db.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def init_db(self) -> None:
        """Apply schema.sql to the database (idempotent)."""
        # Migrate FIRST so old tables are dropped before schema.sql runs
        await self._migrate()
        schema_sql = _SCHEMA_PATH.read_text()
        async with self._conn() as db:
            await db.executescript(schema_sql)
            await db.commit()
        # Create vector table for embeddings (requires sqlite-vec extension)
        try:
            async with self._conn() as db:
                await db.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS assets_vec USING vec0(
                        asset_id TEXT PRIMARY KEY,
                        embedding float[3072]
                    )
                """)
                await db.commit()
        except Exception:
            pass  # sqlite-vec not available; vector search disabled

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

        # tasks: add created_by and claimed_by
        try:
            async with self._conn() as db:
                await db.execute(
                    "ALTER TABLE tasks ADD COLUMN created_by TEXT DEFAULT 'system'"
                )
                await db.commit()
        except Exception:
            pass
        try:
            async with self._conn() as db:
                await db.execute("ALTER TABLE tasks ADD COLUMN claimed_by TEXT")
                await db.commit()
        except Exception:
            pass

        # approvals: add reviewed_by
        try:
            async with self._conn() as db:
                await db.execute("ALTER TABLE approvals ADD COLUMN reviewed_by TEXT")
                await db.commit()
        except Exception:
            pass

        # Migrate old assets schema to new asset pipeline schema
        try:
            async with self._conn() as db:
                cursor = await db.execute("PRAGMA table_info(assets)")
                columns = {row[1] for row in await cursor.fetchall()}
                if "path" in columns:  # Old schema detection
                    await db.execute("DROP TABLE IF EXISTS task_assets")
                    await db.execute("DROP TABLE IF EXISTS assets")
                    schema_sql = (
                        pathlib.Path(__file__).parent / "schema.sql"
                    ).read_text()
                    await db.executescript(schema_sql)
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
                    id, type, status, agent, no_worktree, title, instruction,
                    goal_id, parent_task_id, depends_on, priority, approval_level,
                    schedule, deadline, session_id, attempt, max_retries,
                    budget_usd, result_json, error, cost_usd, review_count,
                    created_at, scheduled_at, started_at, completed_at,
                    timeout_at, updated_at
                ) VALUES (
                    :id, :type, :status, :agent, :no_worktree, :title, :instruction,
                    :goal_id, :parent_task_id, :depends_on, :priority, :approval_level,
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
                    "agent": task.agent,
                    "no_worktree": 1 if task.no_worktree else 0,
                    "title": task.title,
                    "instruction": task.instruction,
                    "goal_id": task.goal_id,
                    "parent_task_id": task.parent_task_id,
                    "depends_on": task.depends_on,
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

    async def count_active_children(self, task_id: str) -> int:
        """Return the number of children that are not in a terminal state."""
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM tasks WHERE parent_task_id = ? AND status NOT IN ('completed', 'failed', 'cancelled')",
                (task_id,),
            )
            row = await cursor.fetchone()
        return row[0] if row else 0

    async def list_dependents(self, task_id: str) -> list[Task]:
        """Find all tasks whose depends_on contains the given task_id."""
        async with self._conn() as db:
            cursor = await db.execute(
                """SELECT * FROM tasks
                   WHERE depends_on IS NOT NULL
                     AND depends_on LIKE ?
                     AND status IN ('pending', 'approved', 'retry_queued')""",
                (f'%"{task_id}"%',),
            )
            rows = await cursor.fetchall()
        return [_row_to_task(dict(r)) for r in rows]

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
            "instruction",
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

    async def update_task_fields(self, task_id: str, **kwargs: Any) -> None:
        """Update arbitrary task fields (instruction, title, priority, etc.)."""
        allowed = {
            "title",
            "instruction",
            "priority",
            "approval_level",
            "budget_usd",
            "max_retries",
            "deadline",
        }
        sets, params = [], []
        for key, val in kwargs.items():
            if key not in allowed:
                raise ValueError(f"update_task_fields: unknown field '{key}'")
            sets.append(f"{key} = ?")
            params.append(val)
        if not sets:
            return
        sets.append("updated_at = ?")
        params.append(_now_iso())
        params.append(task_id)
        async with self._conn() as db:
            await db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
            await db.commit()

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        goal_id: Optional[str] = None,
        agent: Optional[str] = None,
        limit: int | None = None,
        root_only: bool = False,
    ) -> list[Task] | list[dict]:
        """Return tasks optionally filtered by status, goal_id, and/or agent.

        When *root_only* is True, only top-level tasks (those without a
        parent) are returned, and each result dict includes a
        ``children_summary`` key with ``total`` and ``completed`` counts.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if goal_id is not None:
            clauses.append("goal_id = ?")
            params.append(goal_id)
        if agent is not None:
            clauses.append("agent = ?")
            params.append(agent)
        if root_only:
            clauses.append("(parent_task_id IS NULL OR parent_task_id = '')")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        if root_only:
            sql = f"""
                SELECT t.*,
                    (SELECT COUNT(*) FROM tasks c WHERE c.parent_task_id = t.id) as children_total,
                    (SELECT COUNT(*) FROM tasks c WHERE c.parent_task_id = t.id AND c.status = 'completed') as children_completed,
                    (SELECT COUNT(*) FROM tasks c WHERE c.parent_task_id = t.id AND c.status NOT IN ('completed', 'failed', 'cancelled')) as children_active
                FROM tasks t {where}
                ORDER BY t.created_at DESC
            """
        else:
            sql = f"SELECT * FROM tasks {where} ORDER BY created_at DESC"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()

        if root_only:
            results: list[dict] = []
            for r in rows:
                d: dict[str, Any] = dict(r)
                children_total = d.pop("children_total", 0)
                children_completed = d.pop("children_completed", 0)
                children_active = d.pop("children_active", 0)
                d["children_summary"] = {
                    "total": children_total,
                    "completed": children_completed,
                }
                # 부모가 완료 상태이지만 자식 중 활성 태스크가 있으면
                # effective_status를 running으로 표시
                if d.get("status") == "completed" and children_active > 0:
                    d["effective_status"] = "running"
                else:
                    d["effective_status"] = d.get("status")
                results.append(d)
            return results

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

    async def count_running(self, goal_id: Optional[str] = None) -> int:
        """
        Count tasks currently running or claimed.

        If *goal_id* is given, restrict to that goal only.
        """
        params: list[Any] = []
        goal_clause = ""
        if goal_id is not None:
            goal_clause = "AND goal_id = ?"
            params.append(goal_id)

        sql = f"""
            SELECT COUNT(*) FROM tasks
            WHERE status IN ('running', 'claimed')
            {goal_clause}
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
                    id, task_id, created_by, asset_type,
                    media_type, title, description, tags, content_json,
                    file_path, file_size, embedding_model, embedded_at,
                    ttl_days, expires_at, archived,
                    created_at, updated_at
                ) VALUES (
                    :id, :task_id, :created_by, :asset_type,
                    :media_type, :title, :description, :tags, :content_json,
                    :file_path, :file_size, :embedding_model, :embedded_at,
                    :ttl_days, :expires_at, :archived,
                    :created_at, :updated_at
                )
                """,
                {
                    "id": asset["id"],
                    "task_id": asset.get("task_id"),
                    "created_by": asset.get("created_by", "human"),
                    "asset_type": asset["asset_type"],
                    "media_type": asset.get("media_type"),
                    "title": asset["title"],
                    "description": asset.get("description"),
                    "tags": json.dumps(asset["tags"]) if asset.get("tags") else None,
                    "content_json": (
                        json.dumps(asset["content_json"])
                        if asset.get("content_json")
                        and not isinstance(asset["content_json"], str)
                        else asset.get("content_json")
                    ),
                    "file_path": asset.get("file_path"),
                    "file_size": asset.get("file_size"),
                    "embedding_model": asset.get(
                        "embedding_model", "gemini-embedding-2-preview"
                    ),
                    "embedded_at": asset.get("embedded_at"),
                    "ttl_days": asset.get("ttl_days"),
                    "expires_at": asset.get("expires_at"),
                    "archived": asset.get("archived", 0),
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
            clauses.append("asset_type = ?")
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
            "content_json",
            "file_path",
            "file_size",
            "embedding_model",
            "embedded_at",
            "asset_type",
            "media_type",
            "ttl_days",
            "expires_at",
            "archived",
        }
        params: dict[str, Any] = {"updated_at": _now_iso(), "id": asset_id}
        set_clauses = ["updated_at = :updated_at"]

        for key, value in kwargs.items():
            if key not in allowed:
                raise ValueError(f"update_asset: unknown field '{key}'")
            if key == "tags" and isinstance(value, list):
                value = json.dumps(value)
            if (
                key == "content_json"
                and not isinstance(value, str)
                and value is not None
            ):
                value = json.dumps(value)
            params[key] = value
            set_clauses.append(f"{key} = :{key}")

        sql = f"UPDATE assets SET {', '.join(set_clauses)} WHERE id = :id"
        async with self._conn() as db:
            await db.execute(sql, params)
            await db.commit()

    async def delete_asset(self, asset_id: str) -> None:
        """Permanently delete an asset and its embedding vector."""
        async with self._conn() as db:
            try:
                await db.execute(
                    "DELETE FROM assets_vec WHERE asset_id = ?", (asset_id,)
                )
            except Exception:
                pass  # assets_vec may not exist if sqlite-vec is unavailable
            await db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            await db.commit()

    async def list_assets_filtered(
        self,
        *,
        asset_type: str | None = None,
        tags: list[str] | None = None,
        task_id: str | None = None,
        archived: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        """List assets with filters. All assets are project-global."""
        conditions = ["archived = ?"]
        params: list = [archived]
        if asset_type:
            conditions.append("asset_type = ?")
            params.append(asset_type)
        if task_id:
            conditions.append("task_id = ?")
            params.append(task_id)
        where = " AND ".join(conditions)
        where += " AND (expires_at IS NULL OR expires_at > datetime('now'))"

        async with self._conn() as db:
            cursor = await db.execute(
                f"SELECT * FROM assets WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            )
            rows = await cursor.fetchall()
        results = [_row_to_asset(dict(r)) for r in rows]
        if tags:
            results = [r for r in results if _has_tags(r, tags)]
        return results

    async def store_embedding(self, asset_id: str, embedding: list[float]) -> None:
        """Store embedding vector in assets_vec."""
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        async with self._conn() as db:
            await db.execute(
                "INSERT OR REPLACE INTO assets_vec (asset_id, embedding) VALUES (?, ?)",
                (asset_id, blob),
            )
            await db.execute(
                "UPDATE assets SET embedded_at = datetime('now') WHERE id = ?",
                (asset_id,),
            )
            await db.commit()

    async def vec_search(
        self,
        query_embedding: list[float],
        candidate_ids: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Vector similarity search via sqlite-vec."""
        blob = struct.pack(f"{len(query_embedding)}f", *query_embedding)
        async with self._conn() as db:
            if candidate_ids and len(candidate_ids) <= 1000:
                placeholders = ",".join("?" for _ in candidate_ids)
                cursor = await db.execute(
                    f"""SELECT asset_id, distance FROM assets_vec
                        WHERE asset_id IN ({placeholders})
                        AND embedding MATCH ?
                        ORDER BY distance LIMIT ?""",
                    candidate_ids + [blob, limit],
                )
            else:
                cursor = await db.execute(
                    """SELECT asset_id, distance FROM assets_vec
                       WHERE embedding MATCH ?
                       ORDER BY distance LIMIT ?""",
                    (blob, limit),
                )
            return [
                {"asset_id": r[0], "distance": r[1]} for r in await cursor.fetchall()
            ]

    async def archive_expired_assets(self) -> int:
        """Archive assets whose expires_at has passed."""
        async with self._conn() as db:
            cursor = await db.execute("""
                UPDATE assets SET archived = 1, updated_at = datetime('now')
                WHERE expires_at IS NOT NULL AND expires_at < datetime('now')
                AND archived = 0
            """)
            count = cursor.rowcount
            if count:
                await db.execute("""
                    DELETE FROM assets_vec WHERE asset_id IN (
                        SELECT id FROM assets WHERE archived = 1
                    )
                """)
            await db.commit()
            return count

    async def purge_archived_assets(self, grace_days: int = 30) -> int:
        """Permanently delete archived assets older than grace_days."""
        async with self._conn() as db:
            cursor = await db.execute(
                """
                DELETE FROM assets WHERE archived = 1
                AND updated_at < datetime('now', ? || ' days')
            """,
                (f"-{grace_days}",),
            )
            await db.commit()
            return cursor.rowcount

    async def record_asset_usage(
        self, asset_id: str, task_id: str, usage_type: str = "reference"
    ) -> None:
        """Record asset usage in asset_usage table."""
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO asset_usage (id, asset_id, task_id, usage_type, used_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            """,
                (secrets.token_hex(6), asset_id, task_id, usage_type),
            )
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
                    id, task_id, action_type, platform,
                    content, target_url, asset_ids, result_url, metrics,
                    created_at
                ) VALUES (
                    :id, :task_id, :action_type, :platform,
                    :content, :target_url, :asset_ids, :result_url, :metrics,
                    :created_at
                )
                """,
                {
                    "id": action["id"],
                    "task_id": action["task_id"],
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
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return recent action history."""
        params: list[Any] = []

        sql = "SELECT * FROM action_history ORDER BY created_at DESC LIMIT ?"
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
    # Goals
    # ------------------------------------------------------------------

    async def create_goal(
        self,
        *,
        id: str,
        description: str = "",
        metrics: str = "{}",
        cooldown_hours: int = 24,
        no_worktree: bool = False,
    ) -> dict:
        now = _now_iso()
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO goals
                   (id, description, no_worktree, metrics, cooldown_hours,
                    enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    id,
                    description,
                    1 if no_worktree else 0,
                    metrics,
                    cooldown_hours,
                    now,
                    now,
                ),
            )
            await db.commit()
        return await self.get_goal(id)  # type: ignore[return-value]

    async def get_goal(self, goal_id: str) -> dict | None:
        async with self._conn() as db:
            cur = await db.execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_goals(self, *, enabled_only: bool = False) -> list[dict]:
        async with self._conn() as db:
            sql = "SELECT * FROM goals"
            if enabled_only:
                sql += " WHERE enabled = 1"
            sql += " ORDER BY id"
            cur = await db.execute(sql)
            return [dict(r) for r in await cur.fetchall()]

    async def update_goal(self, goal_id: str, **fields) -> None:
        sets, params = [], []
        for key, val in fields.items():
            if key == "enabled":
                val = 1 if val else 0
            sets.append(f"{key} = ?")
            params.append(val)
        sets.append("updated_at = ?")
        params.append(_now_iso())
        params.append(goal_id)
        async with self._conn() as db:
            await db.execute(f"UPDATE goals SET {', '.join(sets)} WHERE id = ?", params)
            await db.commit()

    async def delete_goal(self, goal_id: str) -> None:
        async with self._conn() as db:
            await db.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
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

    async def seed_schedule(self, schedule: dict) -> None:
        """Insert a schedule if name doesn't already exist (for YAML migration)."""
        async with self._conn() as db:
            existing = await db.execute(
                "SELECT id FROM schedules WHERE name = ?", (schedule["name"],)
            )
            if await existing.fetchone():
                return
            now = datetime.now(timezone.utc).isoformat()
            sid = str(uuid.uuid4())[:8]
            await db.execute(
                """INSERT INTO schedules
                   (id, name, agent, no_worktree, task_type, cron, interval_ms, approval_level, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    sid,
                    schedule["name"],
                    schedule.get("agent", "default"),
                    1 if schedule.get("no_worktree") else 0,
                    schedule["task_type"],
                    schedule.get("cron"),
                    schedule.get("interval_ms"),
                    schedule.get("approval_level", 0),
                    now,
                    now,
                ),
            )
            await db.commit()

    async def create_schedule(
        self,
        *,
        name: str,
        task_type: str,
        agent: str = "default",
        no_worktree: bool = False,
        cron: str | None = None,
        interval_ms: int | None = None,
        approval_level: int = 0,
    ) -> dict:
        sid = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO schedules
                   (id, name, agent, no_worktree, task_type, cron, interval_ms,
                    approval_level, enabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    sid,
                    name,
                    agent,
                    1 if no_worktree else 0,
                    task_type,
                    cron,
                    interval_ms,
                    approval_level,
                    now,
                    now,
                ),
            )
            await db.commit()
        return await self.get_schedule(name)

    async def get_schedule(self, name: str) -> dict | None:
        async with self._conn() as db:
            cur = await db.execute("SELECT * FROM schedules WHERE name = ?", (name,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_schedules(self, *, enabled_only: bool = False) -> list[dict]:
        async with self._conn() as db:
            sql = "SELECT * FROM schedules"
            if enabled_only:
                sql += " WHERE enabled = 1"
            sql += " ORDER BY name"
            cur = await db.execute(sql)
            return [dict(r) for r in await cur.fetchall()]

    async def update_schedule(self, name: str, **fields) -> None:
        sets, params = [], []
        for key, val in fields.items():
            if key == "enabled":
                val = 1 if val else 0
            sets.append(f"{key} = ?")
            params.append(val)
        sets.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(name)
        async with self._conn() as db:
            await db.execute(
                f"UPDATE schedules SET {', '.join(sets)} WHERE name = ?", params
            )
            await db.commit()

    async def delete_schedule(self, name: str) -> None:
        async with self._conn() as db:
            await db.execute("DELETE FROM schedules WHERE name = ?", (name,))
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

    # ------------------------------------------------------------------
    # auto_extract_rules
    # ------------------------------------------------------------------

    async def create_extract_rule(
        self,
        *,
        task_type: str,
        asset_type: str,
        title_field: str | None = None,
        iterate: str | None = None,
        tags_from: list[str] | None = None,
    ) -> dict:
        rid = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags_from) if tags_from else None
        async with self._conn() as db:
            await db.execute(
                """INSERT INTO auto_extract_rules
                   (id, task_type, asset_type, title_field, iterate, tags_from, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(task_type) DO UPDATE SET
                     asset_type=excluded.asset_type, title_field=excluded.title_field,
                     iterate=excluded.iterate, tags_from=excluded.tags_from,
                     updated_at=excluded.updated_at""",
                (
                    rid,
                    task_type,
                    asset_type,
                    title_field,
                    iterate,
                    tags_json,
                    now,
                    now,
                ),
            )
            await db.commit()
        return await self.get_extract_rule(task_type)

    async def get_extract_rule(self, task_type: str) -> dict | None:
        async with self._conn() as db:
            cur = await db.execute(
                "SELECT * FROM auto_extract_rules WHERE task_type = ?",
                (task_type,),
            )
            row = await cur.fetchone()
            if row is None:
                return None
            d = dict(row)
            if d["tags_from"]:
                d["tags_from"] = json.loads(d["tags_from"])
            return d

    async def list_extract_rules(self) -> list[dict]:
        async with self._conn() as db:
            cur = await db.execute(
                "SELECT * FROM auto_extract_rules ORDER BY task_type"
            )
            rows = [dict(r) for r in await cur.fetchall()]
            for r in rows:
                if r["tags_from"]:
                    r["tags_from"] = json.loads(r["tags_from"])
            return rows

    async def delete_extract_rule(self, task_type: str) -> None:
        async with self._conn() as db:
            await db.execute(
                "DELETE FROM auto_extract_rules WHERE task_type = ?",
                (task_type,),
            )
            await db.commit()

    # ------------------------------------------------------------------
    # Task Events
    # ------------------------------------------------------------------

    async def record_task_event(
        self,
        task_id: str,
        event_type: str,
        actor: str,
        detail_json: Any = None,
    ) -> str:
        """Insert a task event row and return the new event_id."""
        event_id = uuid.uuid4().hex[:12]
        now = _now_iso()
        detail_str = json.dumps(detail_json) if detail_json is not None else None
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO task_events (id, task_id, event_type, actor, detail_json, created_at)
                VALUES (:id, :task_id, :event_type, :actor, :detail_json, :created_at)
                """,
                {
                    "id": event_id,
                    "task_id": task_id,
                    "event_type": event_type,
                    "actor": actor,
                    "detail_json": detail_str,
                    "created_at": now,
                },
            )
            await db.commit()
        return event_id

    async def get_task_events(
        self, task_id: str, include_children: bool = True
    ) -> list[dict[str, Any]]:
        """Return events for a task (and optionally its children), ordered by created_at ASC."""
        if include_children:
            sql = """
                SELECT e.* FROM task_events e
                WHERE e.task_id = :tid
                   OR e.task_id IN (SELECT id FROM tasks WHERE parent_task_id = :tid)
                ORDER BY e.created_at ASC
            """
        else:
            sql = """
                SELECT e.* FROM task_events e
                WHERE e.task_id = :tid
                ORDER BY e.created_at ASC
            """
        async with self._conn() as db:
            cursor = await db.execute(sql, {"tid": task_id})
            rows = await cursor.fetchall()
        result = []
        for row in rows:
            d = dict(row)
            if d.get("detail_json") and isinstance(d["detail_json"], str):
                try:
                    d["detail_json"] = json.loads(d["detail_json"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Task Logs
    # ------------------------------------------------------------------

    async def record_task_log(
        self,
        task_id: str,
        log_type: str,
        summary: str,
        content: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> int:
        """Insert a task log row with auto-incrementing seq and return the new log_id (INTEGER)."""
        now = _now_iso()
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM task_logs WHERE task_id = :tid",
                {"tid": task_id},
            )
            row = await cursor.fetchone()
            seq = row[0] if row else 1
            cursor = await db.execute(
                """
                INSERT INTO task_logs (task_id, seq, log_type, tool_name, summary, content, created_at)
                VALUES (:task_id, :seq, :log_type, :tool_name, :summary, :content, :created_at)
                """,
                {
                    "task_id": task_id,
                    "seq": seq,
                    "log_type": log_type,
                    "tool_name": tool_name,
                    "summary": summary,
                    "content": content,
                    "created_at": now,
                },
            )
            log_id = cursor.lastrowid
            await db.commit()
        return log_id

    async def get_task_logs(self, task_id: str) -> list[dict[str, Any]]:
        """Return all logs for a task (summary only, with has_content boolean), ordered by seq ASC."""
        async with self._conn() as db:
            cursor = await db.execute(
                """
                SELECT id, task_id, seq, log_type, tool_name, summary,
                       (content IS NOT NULL) as has_content, created_at
                FROM task_logs WHERE task_id = :tid ORDER BY seq ASC
                """,
                {"tid": task_id},
            )
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_task_log(self, task_id: str, log_id: str) -> Optional[dict[str, Any]]:
        """Return a single log entry with full content."""
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT * FROM task_logs WHERE task_id = :task_id AND id = :log_id",
                {"task_id": task_id, "log_id": log_id},
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def cleanup_logs(self, older_than_days: int) -> int:
        """Delete task logs older than *older_than_days* days and return the count deleted."""
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        cutoff_iso = cutoff.isoformat()
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM task_logs WHERE created_at < :cutoff",
                {"cutoff": cutoff_iso},
            )
            row = await cursor.fetchone()
            count = row[0] if row else 0
            await db.execute(
                "DELETE FROM task_logs WHERE created_at < :cutoff",
                {"cutoff": cutoff_iso},
            )
            await db.commit()
        return count
