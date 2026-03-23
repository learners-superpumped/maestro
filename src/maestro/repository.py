"""
Repository Protocol definitions for Maestro.

These Protocol classes formalize the interfaces that the Store already
implements, making it possible to swap in a PostgresStore (or any other
backend) later without changing calling code.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

from maestro.models import Task, TaskStatus


class TaskRepository(Protocol):
    """Interface for task persistence operations."""

    async def create_task(self, task: Task) -> None: ...

    async def get_task(self, task_id: str) -> Optional[Task]: ...

    async def update_task_status(
        self, task_id: str, status: TaskStatus, **kwargs: Any
    ) -> None: ...

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        workspace: Optional[str] = None,
    ) -> list[Task]: ...

    async def list_dispatchable_tasks(self) -> list[Task]: ...

    async def count_running(self, workspace: Optional[str] = None) -> int: ...


class AssetRepository(Protocol):
    """Interface for asset persistence operations."""

    async def create_asset(self, asset: dict[str, Any]) -> None: ...

    async def get_asset(self, asset_id: str) -> Optional[dict[str, Any]]: ...

    async def list_assets(
        self,
        asset_type: Optional[str] = None,
        tags_contain: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]: ...


class BudgetRepository(Protocol):
    """Interface for budget persistence operations."""

    async def get_daily_spend(self, date: str) -> float: ...

    async def record_spend(self, date: str, amount: float) -> None: ...
