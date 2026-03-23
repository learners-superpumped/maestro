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
    """POST /api/internal/history/record — placeholder for action history recording."""
    # Body is accepted but not yet persisted; reserved for future implementation.
    return web.json_response({"ok": True})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_api_app(store: Store) -> web.Application:
    """Create and configure the aiohttp Application."""
    app = web.Application()
    app["store"] = store
    app.router.add_get("/api/internal/health", health_handler)
    app.router.add_post("/api/internal/task/update", task_update_handler)
    app.router.add_post("/api/internal/task/result", task_result_handler)
    app.router.add_post("/api/internal/approval/submit", approval_submit_handler)
    app.router.add_post("/api/internal/history/record", history_record_handler)
    return app
