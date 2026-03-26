"""Tests for webhook endpoints in maestro.api."""

from __future__ import annotations

import pathlib

import pytest

from maestro.api import create_api_app
from maestro.models import TaskStatus
from maestro.store import Store

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def store(db_path: pathlib.Path) -> Store:
    s = Store(db_path)
    return s


@pytest.fixture
def app(store: Store):
    return create_api_app(store)


# ---------------------------------------------------------------------------
# Generic webhook
# ---------------------------------------------------------------------------


async def test_generic_webhook_creates_task(aiohttp_client, app, store) -> None:
    """POST /api/webhooks/generic should create a new task."""
    client = await aiohttp_client(app)

    resp = await client.post(
        "/api/webhooks/generic",
        json={
            "type": "create_post",
            "title": "New post needed",
            "instruction": "Write about the latest feature",
            "priority": 2,
            "approval_level": 2,
        },
    )
    assert resp.status == 201
    body = await resp.json()
    assert body["ok"] is True
    assert "task_id" in body

    # Verify task was persisted
    task = await store.get_task(body["task_id"])
    assert task is not None
    assert task.type == "create_post"
    assert task.title == "New post needed"
    assert task.instruction == "Write about the latest feature"
    assert task.priority == 2
    assert task.approval_level == 2
    assert task.status == TaskStatus.PENDING


async def test_generic_webhook_defaults(aiohttp_client, app, store) -> None:
    """Generic webhook uses default values for optional fields."""
    client = await aiohttp_client(app)

    resp = await client.post(
        "/api/webhooks/generic",
        json={
            "title": "Test task",
            "instruction": "Do something",
        },
    )
    assert resp.status == 201
    body = await resp.json()

    task = await store.get_task(body["task_id"])
    assert task is not None
    assert task.type == "generic"
    assert task.priority == 3
    assert task.approval_level == 2


async def test_generic_webhook_missing_fields(aiohttp_client, app) -> None:
    """Generic webhook returns 400 for missing required fields."""
    client = await aiohttp_client(app)

    resp = await client.post(
        "/api/webhooks/generic",
        json={"title": "test"},
    )
    assert resp.status == 400


async def test_generic_webhook_invalid_json(aiohttp_client, app) -> None:
    """Generic webhook returns 400 for invalid JSON."""
    client = await aiohttp_client(app)

    resp = await client.post(
        "/api/webhooks/generic",
        data=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


# ---------------------------------------------------------------------------
# Placeholder webhooks
# ---------------------------------------------------------------------------


async def test_slack_webhook_placeholder(aiohttp_client, app) -> None:
    """Slack webhook placeholder returns ok."""
    client = await aiohttp_client(app)
    resp = await client.post("/api/webhooks/slack", json={})
    assert resp.status == 200
    body = await resp.json()
    assert body["ok"] is True


async def test_linear_webhook_placeholder(aiohttp_client, app) -> None:
    """Linear webhook placeholder returns ok."""
    client = await aiohttp_client(app)
    resp = await client.post("/api/webhooks/linear", json={})
    assert resp.status == 200
    body = await resp.json()
    assert body["ok"] is True
