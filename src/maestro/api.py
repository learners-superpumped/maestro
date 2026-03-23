"""
Maestro Internal HTTP API.

Exposes lightweight endpoints for worker agents and internal tooling to:
- Report health status
- Update task status
- Submit task results (including cost tracking)
- Submit approval drafts (pauses a task)
- Record action history (placeholder)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from aiohttp import web

from maestro.models import TaskStatus
from maestro.store import Store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def health_handler(request: web.Request) -> web.Response:
    """GET /api/internal/health — liveness probe."""
    return web.json_response({"status": "ok"})


async def task_get_handler(request: web.Request) -> web.Response:
    """GET /api/internal/task/{task_id} — fetch task details."""
    store: Store = request.app["store"]
    task_id = request.match_info["task_id"]

    task = await store.get_task(task_id)
    if task is None:
        raise web.HTTPNotFound(reason=f"Task not found: {task_id}")

    return web.json_response({
        "id": task.id,
        "type": task.type,
        "workspace": task.workspace,
        "title": task.title,
        "instruction": task.instruction,
        "status": task.status.value,
        "priority": task.priority,
        "approval_level": task.approval_level,
        "attempt": task.attempt,
        "max_retries": task.max_retries,
        "budget_usd": task.budget_usd,
        "cost_usd": task.cost_usd,
        "result_json": task.result_json,
        "error": task.error,
        "session_id": task.session_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    })


async def task_update_handler(request: web.Request) -> web.Response:
    """POST /api/internal/task/update — change task status and optional fields."""
    store: Store = request.app["store"]

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    task_id: str | None = body.get("task_id")
    status_str: str | None = body.get("status")

    if not task_id:
        raise web.HTTPBadRequest(reason="'task_id' is required")
    if not status_str:
        raise web.HTTPBadRequest(reason="'status' is required")

    try:
        new_status = TaskStatus(status_str)
    except ValueError:
        raise web.HTTPBadRequest(reason=f"Unknown status value: '{status_str}'")

    # Any extra keys (session_id, attempt, error, etc.) are passed through.
    allowed_extra = {
        "session_id", "attempt", "error", "cost_usd", "result_json",
        "started_at", "completed_at", "timeout_at", "scheduled_at",
    }
    extra = {k: v for k, v in body.items() if k in allowed_extra}

    await store.update_task_status(task_id, new_status, **extra)
    return web.json_response({"ok": True})


async def task_result_handler(request: web.Request) -> web.Response:
    """POST /api/internal/task/result — complete a task and record daily spend."""
    store: Store = request.app["store"]

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    task_id: str | None = body.get("task_id")
    result_json = body.get("result_json")
    cost_usd: float = float(body.get("cost_usd", 0.0))

    if not task_id:
        raise web.HTTPBadRequest(reason="'task_id' is required")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    await store.update_task_status(
        task_id,
        TaskStatus.COMPLETED,
        result_json=json.dumps(result_json) if result_json is not None else None,
        cost_usd=cost_usd,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )

    if cost_usd > 0:
        await store.record_spend(today, cost_usd)

    return web.json_response({"ok": True})


async def approval_submit_handler(request: web.Request) -> web.Response:
    """POST /api/internal/approval/submit — pause a task pending human approval."""
    store: Store = request.app["store"]

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    task_id: str | None = body.get("task_id")
    if not task_id:
        raise web.HTTPBadRequest(reason="'task_id' is required")

    await store.update_task_status(task_id, TaskStatus.PAUSED)
    return web.json_response({"ok": True})


async def history_record_handler(request: web.Request) -> web.Response:
    """POST /api/internal/history/record — record an action to history."""
    store: Store = request.app["store"]

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    import uuid

    action = {
        "id": body.get("id", uuid.uuid4().hex[:12]),
        "task_id": body.get("task_id", ""),
        "workspace": body.get("workspace", ""),
        "action_type": body.get("action_type", "unknown"),
        "platform": body.get("platform", "unknown"),
        "content": body.get("content"),
        "target_url": body.get("target_url"),
        "asset_ids": body.get("asset_ids"),
        "result_url": body.get("result_url"),
        "metrics": body.get("metrics"),
    }

    try:
        await store.record_action(action)
    except Exception as exc:
        logger.warning("Failed to record action: %s", exc)

    return web.json_response({"ok": True})


# ---------------------------------------------------------------------------
# Asset handlers
# ---------------------------------------------------------------------------


async def asset_register_handler(request: web.Request) -> web.Response:
    """POST /api/internal/asset/register — register a new asset."""
    store: Store = request.app["store"]

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    path = body.get("path")
    title = body.get("title")
    if not path or not title:
        raise web.HTTPBadRequest(reason="'path' and 'title' are required")

    from maestro.assets import AssetManager

    mgr = AssetManager(store, request.app.get("assets_dir", "."))

    asset_id = await mgr.register_asset(
        path=path,
        title=title,
        asset_type=body.get("type"),
        tags=body.get("tags"),
        description=body.get("description"),
    )

    return web.json_response({"ok": True, "asset_id": asset_id})


async def asset_get_handler(request: web.Request) -> web.Response:
    """GET /api/internal/asset/{asset_id} — get asset details."""
    store: Store = request.app["store"]
    asset_id = request.match_info["asset_id"]

    asset = await store.get_asset(asset_id)
    if asset is None:
        raise web.HTTPNotFound(reason=f"Asset not found: {asset_id}")

    return web.json_response(asset, dumps=lambda obj: json.dumps(obj, default=str))


async def asset_list_handler(request: web.Request) -> web.Response:
    """GET /api/internal/assets — list assets."""
    store: Store = request.app["store"]

    asset_type = request.query.get("type")
    tags_str = request.query.get("tags")
    tags = [t.strip() for t in tags_str.split(",")] if tags_str else None

    assets = await store.list_assets(asset_type=asset_type, tags_contain=tags)

    return web.json_response(
        {"assets": assets, "count": len(assets)},
        dumps=lambda obj: json.dumps(obj, default=str),
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_api_app(store: Store) -> web.Application:
    """Create and configure the aiohttp Application."""
    app = web.Application()
    app["store"] = store
    app.router.add_get("/api/internal/health", health_handler)
    app.router.add_get("/api/internal/task/{task_id}", task_get_handler)
    app.router.add_post("/api/internal/task/update", task_update_handler)
    app.router.add_post("/api/internal/task/result", task_result_handler)
    app.router.add_post("/api/internal/approval/submit", approval_submit_handler)
    app.router.add_post("/api/internal/history/record", history_record_handler)
    app.router.add_post("/api/internal/asset/register", asset_register_handler)
    app.router.add_get("/api/internal/asset/{asset_id}", asset_get_handler)
    app.router.add_get("/api/internal/assets", asset_list_handler)
    return app
