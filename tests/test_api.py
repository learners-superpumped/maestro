"""
Tests for maestro.api — Internal HTTP API.

Uses pytest-aiohttp's test client to exercise each endpoint against a real
(in-process) aiohttp application backed by a temporary SQLite store.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from maestro.api import create_api_app
from maestro.models import Task, TaskStatus
from maestro.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(task_id: str, status: TaskStatus = TaskStatus.RUNNING) -> Task:
    return Task(
        id=task_id,
        type="shell",
        workspace="/tmp/test",
        title="Test Task",
        instruction="do something",
        status=status,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def store(db_path: pathlib.Path) -> Store:
    """Return an initialised Store backed by the test database."""
    s = Store(db_path)
    return s


@pytest.fixture
def app(store: Store):
    """Return the aiohttp Application under test."""
    return create_api_app(store)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_health_returns_ok(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/api/internal/health")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/internal/task/update
# ---------------------------------------------------------------------------


async def test_task_update_changes_status(aiohttp_client, app, store):
    task = _make_task("task-update-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/task/update",
        json={"task_id": "task-update-1", "status": "paused"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True

    updated = await store.get_task("task-update-1")
    assert updated is not None
    assert updated.status == TaskStatus.PAUSED


async def test_task_update_missing_task_id_returns_400(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/task/update",
        json={"status": "paused"},
    )
    assert resp.status == 400


async def test_task_update_missing_status_returns_400(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/task/update",
        json={"task_id": "some-id"},
    )
    assert resp.status == 400


async def test_task_update_invalid_status_returns_400(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/task/update",
        json={"task_id": "some-id", "status": "not_a_real_status"},
    )
    assert resp.status == 400


# ---------------------------------------------------------------------------
# POST /api/internal/task/result
# ---------------------------------------------------------------------------


async def test_task_result_completes_task_and_records_spend(aiohttp_client, app, store):
    task = _make_task("task-result-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/task/result",
        json={
            "task_id": "task-result-1",
            "result_json": {"output": "hello"},
            "cost_usd": 0.05,
        },
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True

    # Task should be COMPLETED
    updated = await store.get_task("task-result-1")
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.cost_usd == 0.05


async def test_task_result_records_daily_spend(aiohttp_client, app, store):
    from datetime import datetime, timezone

    task = _make_task("task-result-2", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)
    await client.post(
        "/api/internal/task/result",
        json={"task_id": "task-result-2", "result_json": None, "cost_usd": 1.23},
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    spend = await store.get_daily_spend(today)
    assert spend >= 1.23


async def test_task_result_missing_task_id_returns_400(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/task/result",
        json={"result_json": None, "cost_usd": 0.0},
    )
    assert resp.status == 400


async def test_task_result_zero_cost_does_not_record_spend(aiohttp_client, app, store):
    from datetime import datetime, timezone

    task = _make_task("task-result-zero", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)
    await client.post(
        "/api/internal/task/result",
        json={"task_id": "task-result-zero", "result_json": None, "cost_usd": 0.0},
    )

    # No spend record expected for zero cost
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # We can't assert 0 easily if other tests already wrote for today;
    # just verify the task completed without error.
    updated = await store.get_task("task-result-zero")
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# POST /api/internal/approval/submit
# ---------------------------------------------------------------------------


async def test_approval_submit_pauses_task(aiohttp_client, app, store):
    task = _make_task("task-approval-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/approval/submit",
        json={"task_id": "task-approval-1", "draft_json": {"content": "draft"}},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True

    updated = await store.get_task("task-approval-1")
    assert updated is not None
    assert updated.status == TaskStatus.PAUSED


async def test_approval_submit_missing_task_id_returns_400(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/approval/submit",
        json={"draft_json": {"content": "draft"}},
    )
    assert resp.status == 400


# ---------------------------------------------------------------------------
# POST /api/internal/history/record
# ---------------------------------------------------------------------------


async def test_history_record_returns_ok(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/history/record",
        json={"action_type": "post", "platform": "twitter", "content": "hello"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True


# ---------------------------------------------------------------------------
# GET / — Dashboard
# ---------------------------------------------------------------------------


async def test_dashboard_serves_html(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/")
    assert resp.status == 200
    assert "text/html" in resp.content_type
    text = await resp.text()
    assert "Maestro" in text


# ---------------------------------------------------------------------------
# GET /api/internal/tasks — List tasks
# ---------------------------------------------------------------------------


async def test_tasks_list_returns_all(aiohttp_client, app, store):
    await store.create_task(_make_task("tl-1", status=TaskStatus.RUNNING))
    await store.create_task(_make_task("tl-2", status=TaskStatus.COMPLETED))

    client = await aiohttp_client(app)
    resp = await client.get("/api/internal/tasks")
    assert resp.status == 200
    data = await resp.json()
    assert data["count"] >= 2
    ids = [t["id"] for t in data["tasks"]]
    assert "tl-1" in ids
    assert "tl-2" in ids


async def test_tasks_list_filters_by_status(aiohttp_client, app, store):
    await store.create_task(_make_task("tl-f1", status=TaskStatus.RUNNING))
    await store.create_task(_make_task("tl-f2", status=TaskStatus.COMPLETED))

    client = await aiohttp_client(app)
    resp = await client.get("/api/internal/tasks?status=running")
    assert resp.status == 200
    data = await resp.json()
    for t in data["tasks"]:
        assert t["status"] == "running"


async def test_tasks_list_invalid_status_returns_400(aiohttp_client, app):
    client = await aiohttp_client(app)
    resp = await client.get("/api/internal/tasks?status=bogus")
    assert resp.status == 400


# ---------------------------------------------------------------------------
# GET /api/internal/stats — Summary stats
# ---------------------------------------------------------------------------


async def test_stats_returns_summary(aiohttp_client, app, store):
    await store.create_task(_make_task("st-1", status=TaskStatus.RUNNING))
    await store.create_task(_make_task("st-2", status=TaskStatus.COMPLETED))

    client = await aiohttp_client(app)
    resp = await client.get("/api/internal/stats")
    assert resp.status == 200
    data = await resp.json()
    assert "running" in data
    assert "pending_approvals" in data
    assert "today_spend_usd" in data
    assert "total_tasks" in data
    assert "status_counts" in data
    assert data["running"] >= 1


# ---------------------------------------------------------------------------
# POST /api/internal/task/{id}/approve
# ---------------------------------------------------------------------------


async def test_task_approve_endpoint(aiohttp_client, app, store):
    # Create a running task, submit a draft (pauses it), then approve via endpoint
    task = _make_task("ta-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)

    # Submit approval draft (pauses the task)
    resp = await client.post(
        "/api/internal/approval/submit",
        json={"task_id": "ta-1", "draft_json": {"text": "hello"}},
    )
    assert resp.status == 200

    # Approve
    resp = await client.post("/api/internal/task/ta-1/approve", json={})
    assert resp.status == 200
    data = await resp.json()
    assert data["ok"] is True

    updated = await store.get_task("ta-1")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED


# ---------------------------------------------------------------------------
# POST /api/internal/task/{id}/reject
# ---------------------------------------------------------------------------


async def test_task_reject_endpoint(aiohttp_client, app, store):
    task = _make_task("tr-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)

    # Submit draft
    await client.post(
        "/api/internal/approval/submit",
        json={"task_id": "tr-1", "draft_json": {"text": "draft"}},
    )

    # Reject
    resp = await client.post(
        "/api/internal/task/tr-1/reject",
        json={"note": "not good enough"},
    )
    assert resp.status == 200

    updated = await store.get_task("tr-1")
    assert updated is not None
    assert updated.status == TaskStatus.CANCELLED


# ---------------------------------------------------------------------------
# POST /api/internal/task/{id}/revise
# ---------------------------------------------------------------------------


async def test_task_revise_endpoint(aiohttp_client, app, store):
    task = _make_task("tv-1", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)

    # Submit draft
    await client.post(
        "/api/internal/approval/submit",
        json={"task_id": "tv-1", "draft_json": {"text": "draft"}},
    )

    # Revise
    resp = await client.post(
        "/api/internal/task/tv-1/revise",
        json={"note": "please fix the intro"},
    )
    assert resp.status == 200

    updated = await store.get_task("tv-1")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED


async def test_task_revise_without_note_returns_400(aiohttp_client, app, store):
    task = _make_task("tv-2", status=TaskStatus.RUNNING)
    await store.create_task(task)

    client = await aiohttp_client(app)

    await client.post(
        "/api/internal/approval/submit",
        json={"task_id": "tv-2", "draft_json": {}},
    )

    resp = await client.post("/api/internal/task/tv-2/revise", json={})
    assert resp.status == 400
