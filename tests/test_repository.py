"""Tests for maestro.repository — Protocol conformance checks."""

from __future__ import annotations

import pathlib

import pytest

from maestro.models import Task, TaskStatus
from maestro.store import Store

# ---------------------------------------------------------------------------
# Protocol conformance — static check via isinstance with runtime_checkable
# would require runtime_checkable; instead we verify the Store has the right
# methods with the right signatures by calling them.
# ---------------------------------------------------------------------------


@pytest.fixture
async def store(db_path: pathlib.Path) -> Store:
    s = Store(db_path)
    return s


def _make_task(task_id: str = "repo-t1") -> Task:
    return Task(
        id=task_id,
        type="shell",
        title="Repo Test",
        instruction="do repo things",
        status=TaskStatus.PENDING,
    )


# ---------------------------------------------------------------------------
# TaskRepository
# ---------------------------------------------------------------------------


async def test_store_satisfies_task_repository(store: Store) -> None:
    """Store should implement all TaskRepository methods."""
    # create_task
    task = _make_task("tr-1")
    await store.create_task(task)

    # get_task
    fetched = await store.get_task("tr-1")
    assert fetched is not None
    assert fetched.id == "tr-1"

    # update_task_status
    await store.update_task_status("tr-1", TaskStatus.APPROVED)
    updated = await store.get_task("tr-1")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED

    # list_tasks
    tasks = await store.list_tasks()
    assert len(tasks) >= 1

    # list_tasks with filters
    pending = await store.list_tasks(status=TaskStatus.PENDING)
    assert all(t.status == TaskStatus.PENDING for t in pending)

    agent_tasks = await store.list_tasks(agent="default")
    assert len(agent_tasks) >= 1

    # list_dispatchable_tasks — approved task should be dispatchable
    dispatchable = await store.list_dispatchable_tasks()
    assert len(dispatchable) == 1
    assert dispatchable[0].id == "tr-1"
    assert dispatchable[0].status == TaskStatus.APPROVED

    # count_running — no running tasks yet
    count = await store.count_running()
    assert count == 0


# ---------------------------------------------------------------------------
# AssetRepository
# ---------------------------------------------------------------------------


async def test_store_satisfies_asset_repository(store: Store) -> None:
    """Store should implement all AssetRepository methods."""
    # create_asset
    asset = {
        "id": "a-1",
        "asset_type": "image",
        "file_path": "/tmp/test.png",
        "title": "Test Image",
        "tags": ["test"],
    }
    await store.create_asset(asset)

    # get_asset
    fetched = await store.get_asset("a-1")
    assert fetched is not None
    assert fetched["id"] == "a-1"

    # list_assets
    assets = await store.list_assets()
    assert len(assets) >= 1

    assets_typed = await store.list_assets(asset_type="image")
    assert all(a["asset_type"] == "image" for a in assets_typed)

    assets_tagged = await store.list_assets(tags_contain=["test"])
    assert len(assets_tagged) >= 1


# ---------------------------------------------------------------------------
# BudgetRepository
# ---------------------------------------------------------------------------


async def test_store_satisfies_budget_repository(store: Store) -> None:
    """Store should implement all BudgetRepository methods."""
    # record_spend
    await store.record_spend("2026-03-23", 1.50)

    # get_daily_spend
    spend = await store.get_daily_spend("2026-03-23")
    assert spend == 1.50

    # Accumulation
    await store.record_spend("2026-03-23", 0.75)
    spend = await store.get_daily_spend("2026-03-23")
    assert spend == 2.25

    # No spend for another day
    spend_other = await store.get_daily_spend("2026-03-24")
    assert spend_other == 0.0
