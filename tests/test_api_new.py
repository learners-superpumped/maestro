"""
Tests for new API endpoints: schedule CRUD, rule CRUD, task create,
asset delete/archive/cleanup, and task children.
"""

from __future__ import annotations

import pytest

from maestro.api import create_api_app
from maestro.models import Task
from maestro.store import Store


@pytest.fixture
async def client(aiohttp_client, tmp_path):
    store = Store(str(tmp_path / "test.db"))
    await store.init_db()
    app = create_api_app(store)
    return await aiohttp_client(app), store


async def test_task_create(client):
    c, store = client
    resp = await c.post(
        "/api/internal/task",
        json={
            "workspace": "test-ws",
            "type": "claude",
            "title": "Test Task",
            "instruction": "Do something",
            "priority": 2,
        },
    )
    assert resp.status == 201
    body = await resp.json()
    assert body["ok"]
    task = await store.get_task(body["task_id"])
    assert task is not None
    assert task.title == "Test Task"


async def test_schedule_crud(client):
    c, store = client
    resp = await c.post(
        "/api/internal/schedule",
        json={
            "name": "test-sched",
            "workspace": "w",
            "task_type": "claude",
            "cron": "0 * * * *",
        },
    )
    assert resp.status == 200

    resp = await c.get("/api/internal/schedules")
    body = await resp.json()
    assert any(s["name"] == "test-sched" for s in body["schedules"])

    resp = await c.post("/api/internal/schedule/test-sched/disable")
    assert resp.status == 200

    resp = await c.delete("/api/internal/schedule/test-sched")
    assert resp.status == 200


async def test_rule_crud(client):
    c, store = client
    resp = await c.post(
        "/api/internal/rule",
        json={
            "workspace": "w",
            "task_type": "claude",
            "asset_type": "post",
        },
    )
    assert resp.status == 200

    resp = await c.get("/api/internal/rules")
    body = await resp.json()
    assert body["count"] >= 1

    resp = await c.delete("/api/internal/rule/w/claude")
    assert resp.status == 200


async def test_asset_delete(client):
    c, store = client
    await store.create_asset(
        {
            "id": "a-del-01",
            "asset_type": "doc",
            "title": "T",
            "workspace": "_shared",
            "created_by": "test",
        }
    )
    resp = await c.delete("/api/internal/asset/a-del-01")
    assert resp.status == 200
    assert await store.get_asset("a-del-01") is None


async def test_asset_archive(client):
    c, store = client
    await store.create_asset(
        {
            "id": "a-arc-01",
            "asset_type": "doc",
            "title": "T",
            "workspace": "_shared",
            "created_by": "test",
        }
    )
    resp = await c.post("/api/internal/asset/a-arc-01/archive")
    assert resp.status == 200
    a = await store.get_asset("a-arc-01")
    assert a["archived"] == 1


async def test_task_children(client):
    c, store = client
    parent = Task(id="p1", type="test", workspace="w", title="Parent", instruction="I")
    child = Task(
        id="c1",
        type="test",
        workspace="w",
        title="Child",
        instruction="I",
        parent_task_id="p1",
    )
    await store.create_task(parent)
    await store.create_task(child)
    resp = await c.get("/api/internal/task/p1/children")
    body = await resp.json()
    assert len(body["children"]) == 1
    assert body["children"][0]["id"] == "c1"
