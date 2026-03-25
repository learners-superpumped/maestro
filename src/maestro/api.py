"""
Maestro Internal HTTP API.

Exposes lightweight endpoints for worker agents and internal tooling to:
- Report health status
- Update task status
- Submit task results (including cost tracking)
- Submit approval drafts (pauses a task)
- Record action history (placeholder)
- Serve the web dashboard
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import datetime, timezone

from aiohttp import web

from maestro.models import Task, TaskStatus
from maestro.store import Store
from maestro.workspace import WorkspaceManager

logger = logging.getLogger(__name__)

_WEB_DIST = pathlib.Path(__file__).resolve().parent.parent.parent / "web" / "dist"


@web.middleware
async def spa_fallback_middleware(request, handler):
    """Serve index.html for non-API, non-WS routes (SPA routing)."""
    try:
        return await handler(request)
    except web.HTTPNotFound:
        if not request.path.startswith(("/api/", "/ws")):
            index = _WEB_DIST / "index.html"
            if index.exists():
                return web.FileResponse(index)
        raise


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

    # 부모가 completed이지만 자식이 아직 활성이면 effective_status를 running으로
    effective_status = task.status.value
    if task.status == TaskStatus.COMPLETED:
        active_children = await store.count_active_children(task_id)
        if active_children > 0:
            effective_status = "running"

    return web.json_response(
        {
            "id": task.id,
            "type": task.type,
            "workspace": task.workspace,
            "title": task.title,
            "instruction": task.instruction,
            "status": task.status.value,
            "effective_status": effective_status,
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
        }
    )


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
    from maestro.approval import ApprovalManager

    store: Store = request.app["store"]
    mgr = ApprovalManager(store)

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    task_id: str | None = body.get("task_id")
    if not task_id:
        raise web.HTTPBadRequest(reason="'task_id' is required")

    draft_json = json.dumps(body.get("draft_json", {}))
    approval_id = await mgr.submit_draft(task_id, draft_json)

    # Send Slack notification if configured
    slack = request.app.get("slack")
    if slack and slack.available:
        task = await store.get_task(task_id)
        title = task.title if task else task_id
        await slack.send_approval_request(task_id, title, draft_json[:500])

    return web.json_response({"ok": True, "approval_id": approval_id})


async def approval_get_handler(request: web.Request) -> web.Response:
    """GET /api/internal/approval/{task_id} — get approval details for a task."""
    from maestro.approval import ApprovalManager

    store: Store = request.app["store"]
    mgr = ApprovalManager(store)
    task_id = request.match_info["task_id"]

    approval = await mgr.get_approval(task_id)
    if approval is None:
        raise web.HTTPNotFound(reason=f"No approval found for task: {task_id}")

    return web.json_response(approval, dumps=lambda obj: json.dumps(obj, default=str))


async def approvals_pending_handler(request: web.Request) -> web.Response:
    """GET /api/internal/approvals/pending — list pending approvals."""
    from maestro.approval import ApprovalManager

    store: Store = request.app["store"]
    mgr = ApprovalManager(store)

    pending = await mgr.get_pending_approvals()
    return web.json_response(
        {"approvals": pending, "count": len(pending)},
        dumps=lambda obj: json.dumps(obj, default=str),
    )


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
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    if not data.get("asset_type") or not data.get("title"):
        raise web.HTTPBadRequest(reason="'asset_type' and 'title' are required")

    am = request.app.get("asset_manager")
    if am is None:
        raise web.HTTPServiceUnavailable(reason="AssetManager not available")

    asset = await am.register_asset(
        asset_type=data["asset_type"],
        title=data["title"],
        content_json=data.get("content_json"),
        file_path=data.get("file_path"),
        tags=data.get("tags"),
        description=data.get("description"),
        ttl_days=data.get("ttl_days"),
        workspace=data.get("workspace", "_shared"),
        created_by=data.get("created_by", "agent"),
        task_id=data.get("task_id"),
    )
    return web.json_response(asset, dumps=lambda obj: json.dumps(obj, default=str))


async def asset_search_handler(request: web.Request) -> web.Response:
    """POST /api/internal/asset/search — search assets with vector similarity."""
    try:
        data = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    if not data.get("query"):
        raise web.HTTPBadRequest(reason="'query' is required")

    am = request.app.get("asset_manager")
    if am is None:
        raise web.HTTPServiceUnavailable(reason="AssetManager not available")

    results = await am.search(
        query=data["query"],
        workspace=data.get("workspace"),
        asset_type=data.get("asset_type"),
        tags=data.get("tags"),
        since=data.get("since"),
        limit=data.get("limit", 10),
        include_content=data.get("include_content", True),
    )
    return web.json_response(results, dumps=lambda obj: json.dumps(obj, default=str))


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
    workspace = request.query.get("workspace")
    tags_str = request.query.get("tags")
    tags = [t.strip() for t in tags_str.split(",")] if tags_str else None

    assets = await store.list_assets_filtered(
        asset_type=asset_type,
        workspace=workspace,
        tags=tags,
    )

    return web.json_response(
        {"assets": assets, "count": len(assets)},
        dumps=lambda obj: json.dumps(obj, default=str),
    )


# ---------------------------------------------------------------------------
# Dashboard & new read endpoints
# ---------------------------------------------------------------------------


async def tasks_list_handler(request: web.Request) -> web.Response:
    """GET /api/internal/tasks — list all tasks with optional filters."""
    store: Store = request.app["store"]

    status_str = request.query.get("status")
    workspace = request.query.get("workspace")
    root_only = request.query.get("root_only", "").lower() == "true"

    status = None
    if status_str:
        try:
            status = TaskStatus(status_str)
        except ValueError:
            raise web.HTTPBadRequest(reason=f"Unknown status: '{status_str}'")

    tasks = await store.list_tasks(
        status=status, workspace=workspace, root_only=root_only
    )

    if root_only:
        # store returns dicts with children_summary when root_only=True
        return web.json_response(
            {"tasks": tasks, "count": len(tasks)},
            dumps=lambda obj: json.dumps(obj, default=str),
        )

    return web.json_response(
        {
            "tasks": [
                {
                    "id": t.id,
                    "type": t.type,
                    "workspace": t.workspace,
                    "title": t.title,
                    "status": t.status.value,
                    "priority": t.priority,
                    "approval_level": t.approval_level,
                    "attempt": t.attempt,
                    "max_retries": t.max_retries,
                    "budget_usd": t.budget_usd,
                    "cost_usd": t.cost_usd,
                    "error": t.error,
                    "session_id": t.session_id,
                    "parent_task_id": t.parent_task_id,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tasks
            ],
            "count": len(tasks),
        },
        dumps=lambda obj: json.dumps(obj, default=str),
    )


async def stats_handler(request: web.Request) -> web.Response:
    """GET /api/internal/stats — summary statistics for the dashboard."""
    store: Store = request.app["store"]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    running_count = await store.count_running()
    pending_approvals = await store.list_approvals(status="pending")
    daily_spend = await store.get_daily_spend(today)

    # Count tasks by status
    all_tasks = await store.list_tasks()
    status_counts: dict[str, int] = {}
    for t in all_tasks:
        status_counts[t.status.value] = status_counts.get(t.status.value, 0) + 1

    return web.json_response(
        {
            "running": running_count,
            "pending_approvals": len(pending_approvals),
            "today_spend_usd": daily_spend,
            "total_tasks": len(all_tasks),
            "status_counts": status_counts,
            "date": today,
        }
    )


async def task_approve_handler(request: web.Request) -> web.Response:
    """POST /api/internal/task/{task_id}/approve — approve a pending task."""
    from maestro.approval import ApprovalManager

    store: Store = request.app["store"]
    mgr = ApprovalManager(store)
    task_id = request.match_info["task_id"]

    task = await store.get_task(task_id)
    if task is None:
        raise web.HTTPNotFound(reason=f"Task not found: {task_id}")

    note = None
    try:
        body = await request.json()
        note = body.get("note")
    except (json.JSONDecodeError, ValueError):
        pass

    approval = await mgr.get_approval(task_id)
    if approval and approval["status"] == "pending":
        await mgr.approve(task_id)
    else:
        await store.update_task_status(task_id, TaskStatus.APPROVED, actor="human")

    return web.json_response({"ok": True})


async def task_reject_handler(request: web.Request) -> web.Response:
    """POST /api/internal/task/{task_id}/reject — reject a pending task."""
    from maestro.approval import ApprovalManager

    store: Store = request.app["store"]
    mgr = ApprovalManager(store)
    task_id = request.match_info["task_id"]

    task = await store.get_task(task_id)
    if task is None:
        raise web.HTTPNotFound(reason=f"Task not found: {task_id}")

    note = None
    try:
        body = await request.json()
        note = body.get("note")
    except (json.JSONDecodeError, ValueError):
        pass

    approval = await mgr.get_approval(task_id)
    if approval and approval["status"] == "pending":
        await mgr.reject(task_id, note=note)
    else:
        await store.update_task_status(task_id, TaskStatus.CANCELLED, actor="human")

    return web.json_response({"ok": True})


async def task_revise_handler(request: web.Request) -> web.Response:
    """POST /api/internal/task/{task_id}/revise — request revision on a task."""
    from maestro.approval import ApprovalManager

    store: Store = request.app["store"]
    mgr = ApprovalManager(store)
    task_id = request.match_info["task_id"]

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    note = body.get("note")
    if not note:
        raise web.HTTPBadRequest(reason="'note' is required for revision")

    revised_content = body.get("revised_content")

    try:
        await mgr.revise(task_id, note=note, revised_content=revised_content)
    except ValueError as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc

    return web.json_response({"ok": True})


# ---------------------------------------------------------------------------
# Task create & children
# ---------------------------------------------------------------------------


async def task_create_handler(request: web.Request) -> web.Response:
    """POST /api/internal/task — create a new task."""
    store: Store = request.app["store"]
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc
    for field in ("workspace", "title", "instruction"):
        if not body.get(field):
            raise web.HTTPBadRequest(reason=f"'{field}' is required")
    import uuid

    # Parse priority/approval_level safely (frontend may send strings)
    try:
        priority = int(body.get("priority", 3))
    except (ValueError, TypeError):
        priority = 3
    try:
        approval_level = int(body.get("approval_level", 2))
    except (ValueError, TypeError):
        approval_level = 2

    task = Task(
        id=uuid.uuid4().hex[:8],
        type=body.get("type", "claude"),
        workspace=body["workspace"],
        title=body["title"],
        instruction=body["instruction"],
        priority=priority,
        approval_level=approval_level,
        parent_task_id=body.get("parent_task_id"),
        goal_id=body.get("goal_id"),
        budget_usd=float(body.get("budget_usd", 5.0)),
    )
    await store.create_task(task)
    return web.json_response({"ok": True, "task_id": task.id}, status=201)


async def task_children_handler(request: web.Request) -> web.Response:
    """GET /api/internal/task/{task_id}/children — list child tasks."""
    store: Store = request.app["store"]
    task_id = request.match_info["task_id"]
    children = await store.list_children(task_id)
    return web.json_response(
        {
            "children": [
                {
                    "id": c.id,
                    "type": c.type,
                    "title": c.title,
                    "status": c.status.value,
                    "priority": c.priority,
                    "cost_usd": c.cost_usd,
                    "result_json": c.result_json,
                    "parent_task_id": c.parent_task_id,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in children
            ]
        },
        dumps=lambda obj: json.dumps(obj, default=str),
    )


# ---------------------------------------------------------------------------
# Task events & logs
# ---------------------------------------------------------------------------


async def task_events_handler(request: web.Request) -> web.Response:
    """GET /api/internal/task/{task_id}/events"""
    store: Store = request.app["store"]
    task_id = request.match_info["task_id"]
    events = await store.get_task_events(task_id, include_children=True)
    return web.json_response({"events": events})


async def task_logs_handler(request: web.Request) -> web.Response:
    """GET /api/internal/task/{task_id}/logs"""
    store: Store = request.app["store"]
    task_id = request.match_info["task_id"]
    logs = await store.get_task_logs(task_id)
    return web.json_response({"logs": logs})


async def task_log_detail_handler(request: web.Request) -> web.Response:
    """GET /api/internal/task/{task_id}/logs/{log_id}"""
    store: Store = request.app["store"]
    task_id = request.match_info["task_id"]
    log_id = int(request.match_info["log_id"])
    log = await store.get_task_log(task_id, log_id)
    if not log:
        raise web.HTTPNotFound(reason="Log not found")
    return web.json_response(log)


async def task_logs_delete_handler(request: web.Request) -> web.Response:
    """DELETE /api/internal/task/{task_id}/logs"""
    store: Store = request.app["store"]
    task_id = request.match_info["task_id"]
    async with store._db() as db:
        cursor = await db.execute(
            "DELETE FROM task_logs WHERE task_id = :tid", {"tid": task_id}
        )
        await db.commit()
    return web.json_response({"deleted": cursor.rowcount})


async def logs_cleanup_handler(request: web.Request) -> web.Response:
    """POST /api/internal/logs/cleanup"""
    store: Store = request.app["store"]
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc
    days = int(body.get("older_than_days", 30))
    count = await store.cleanup_logs(days)
    return web.json_response({"deleted": count})


# ---------------------------------------------------------------------------
# Schedule CRUD
# ---------------------------------------------------------------------------


async def schedules_list_handler(request: web.Request) -> web.Response:
    """GET /api/internal/schedules — list all schedules."""
    store: Store = request.app["store"]
    schedules = await store.list_schedules()
    return web.json_response(
        {"schedules": schedules, "count": len(schedules)},
        dumps=lambda obj: json.dumps(obj, default=str),
    )


async def schedule_create_handler(request: web.Request) -> web.Response:
    """POST /api/internal/schedule — create a new schedule."""
    store: Store = request.app["store"]
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc
    for field in ("name", "workspace", "task_type"):
        if not body.get(field):
            raise web.HTTPBadRequest(reason=f"'{field}' is required")
    await store.create_schedule(
        name=body["name"],
        workspace=body["workspace"],
        task_type=body["task_type"],
        cron=body.get("cron"),
        interval_ms=body.get("interval_ms"),
        approval_level=body.get("approval_level", 0),
    )
    return web.json_response({"ok": True})


async def schedule_delete_handler(request: web.Request) -> web.Response:
    """DELETE /api/internal/schedule/{name} — delete a schedule."""
    store: Store = request.app["store"]
    name = request.match_info["name"]
    await store.delete_schedule(name)
    return web.json_response({"ok": True})


async def schedule_enable_handler(request: web.Request) -> web.Response:
    """POST /api/internal/schedule/{name}/enable — enable a schedule."""
    store: Store = request.app["store"]
    name = request.match_info["name"]
    await store.update_schedule(name, enabled=True)
    return web.json_response({"ok": True})


async def schedule_disable_handler(request: web.Request) -> web.Response:
    """POST /api/internal/schedule/{name}/disable — disable a schedule."""
    store: Store = request.app["store"]
    name = request.match_info["name"]
    await store.update_schedule(name, enabled=False)
    return web.json_response({"ok": True})


# ---------------------------------------------------------------------------
# Goal CRUD
# ---------------------------------------------------------------------------


async def goals_list_handler(request: web.Request) -> web.Response:
    """GET /api/internal/goals — list all goals."""
    store: Store = request.app["store"]
    goals = await store.list_goals()
    return web.json_response(
        {"goals": goals, "count": len(goals)},
        dumps=lambda obj: json.dumps(obj, default=str),
    )


async def goal_get_handler(request: web.Request) -> web.Response:
    """GET /api/internal/goal/{id} — get a goal with state."""
    store: Store = request.app["store"]
    goal_id = request.match_info["id"]
    goal = await store.get_goal(goal_id)
    if goal is None:
        raise web.HTTPNotFound(reason=f"Goal not found: {goal_id}")
    return web.json_response(goal, dumps=lambda obj: json.dumps(obj, default=str))


async def goal_create_handler(request: web.Request) -> web.Response:
    """POST /api/internal/goal — create a new goal."""
    store: Store = request.app["store"]
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc
    for field in ("id", "workspace"):
        if not body.get(field):
            raise web.HTTPBadRequest(reason=f"'{field}' is required")
    await store.create_goal(
        id=body["id"],
        workspace=body["workspace"],
        description=body.get("description", ""),
        metrics=json.dumps(body["metrics"])
        if isinstance(body.get("metrics"), dict)
        else body.get("metrics", "{}"),
        cooldown_hours=body.get("cooldown_hours", 24),
    )
    return web.json_response({"ok": True})


async def goal_delete_handler(request: web.Request) -> web.Response:
    """DELETE /api/internal/goal/{id} — delete a goal."""
    store: Store = request.app["store"]
    goal_id = request.match_info["id"]
    await store.delete_goal(goal_id)
    return web.json_response({"ok": True})


async def goal_enable_handler(request: web.Request) -> web.Response:
    """POST /api/internal/goal/{id}/enable — enable a goal."""
    store: Store = request.app["store"]
    goal_id = request.match_info["id"]
    await store.update_goal(goal_id, enabled=True)
    return web.json_response({"ok": True})


async def goal_disable_handler(request: web.Request) -> web.Response:
    """POST /api/internal/goal/{id}/disable — disable a goal."""
    store: Store = request.app["store"]
    goal_id = request.match_info["id"]
    await store.update_goal(goal_id, enabled=False)
    return web.json_response({"ok": True})


# ---------------------------------------------------------------------------
# Rule CRUD
# ---------------------------------------------------------------------------


async def rules_list_handler(request: web.Request) -> web.Response:
    """GET /api/internal/rules — list extract rules."""
    store: Store = request.app["store"]
    workspace = request.query.get("workspace")
    rules = await store.list_extract_rules(workspace=workspace)
    return web.json_response(
        {"rules": rules, "count": len(rules)},
        dumps=lambda obj: json.dumps(obj, default=str),
    )


async def rule_create_handler(request: web.Request) -> web.Response:
    """POST /api/internal/rule — create an extract rule."""
    store: Store = request.app["store"]
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc
    for field in ("workspace", "task_type", "asset_type"):
        if not body.get(field):
            raise web.HTTPBadRequest(reason=f"'{field}' is required")
    await store.create_extract_rule(
        workspace=body["workspace"],
        task_type=body["task_type"],
        asset_type=body["asset_type"],
        title_field=body.get("title_field"),
        iterate=body.get("iterate"),
        tags_from=body.get("tags_from"),
    )
    return web.json_response({"ok": True})


async def rule_delete_handler(request: web.Request) -> web.Response:
    """DELETE /api/internal/rule/{workspace}/{task_type} — delete an extract rule."""
    store: Store = request.app["store"]
    workspace = request.match_info["workspace"]
    task_type = request.match_info["task_type"]
    await store.delete_extract_rule(workspace, task_type)
    return web.json_response({"ok": True})


# ---------------------------------------------------------------------------
# Asset delete / archive / cleanup
# ---------------------------------------------------------------------------


async def asset_delete_handler(request: web.Request) -> web.Response:
    """DELETE /api/internal/asset/{asset_id} — delete an asset."""
    store: Store = request.app["store"]
    asset_id = request.match_info["asset_id"]
    asset = await store.get_asset(asset_id)
    if asset is None:
        raise web.HTTPNotFound(reason=f"Asset not found: {asset_id}")
    await store.delete_asset(asset_id)
    return web.json_response({"ok": True})


async def asset_archive_handler(request: web.Request) -> web.Response:
    """POST /api/internal/asset/{asset_id}/archive — archive an asset."""
    store: Store = request.app["store"]
    asset_id = request.match_info["asset_id"]
    asset = await store.get_asset(asset_id)
    if asset is None:
        raise web.HTTPNotFound(reason=f"Asset not found: {asset_id}")
    await store.update_asset(asset_id, archived=1)
    return web.json_response({"ok": True})


async def assets_cleanup_handler(request: web.Request) -> web.Response:
    """POST /api/internal/assets/cleanup — archive expired and purge old assets."""
    store: Store = request.app["store"]
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    grace = int(body.get("grace_days", 30))
    archived = await store.archive_expired_assets()
    purged = await store.purge_archived_assets(grace_days=grace)
    return web.json_response({"archived": archived, "purged": purged})


# ---------------------------------------------------------------------------
# Workspace handlers
# ---------------------------------------------------------------------------


async def handle_workspace_list(request: web.Request) -> web.Response:
    """GET /api/internal/workspaces — list all workspaces."""
    root: pathlib.Path = request.app["project_root"]
    wm = WorkspaceManager(root)
    names = wm.list_workspaces()
    result = []
    for name in names:
        warnings = wm.validate_workspace(name)
        result.append(
            {
                "name": name,
                "valid": len(warnings) == 0,
                "warnings": warnings,
            }
        )
    return web.json_response({"workspaces": result, "count": len(result)})


async def handle_workspace_create(request: web.Request) -> web.Response:
    """POST /api/internal/workspace — create a workspace."""
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    name = body.get("name", "").strip()
    template = body.get("template", "default")
    if not name:
        raise web.HTTPBadRequest(reason="'name' is required")

    root: pathlib.Path = request.app["project_root"]
    wm = WorkspaceManager(root)
    wm.ensure_base_knowledge()

    try:
        ws_path = wm.create_workspace(name, template=template)
    except FileExistsError:
        raise web.HTTPConflict(reason=f"workspace '{name}' already exists")
    except ValueError as exc:
        raise web.HTTPBadRequest(reason=str(exc)) from exc

    warnings = wm.validate_workspace(name)
    return web.json_response(
        {
            "name": name,
            "path": str(ws_path),
            "template": template,
            "valid": len(warnings) == 0,
            "warnings": warnings,
        }
    )


async def handle_workspace_validate(request: web.Request) -> web.Response:
    """GET /api/internal/workspace/{name}/validate — validate a workspace."""
    name = request.match_info["name"]
    root: pathlib.Path = request.app["project_root"]
    wm = WorkspaceManager(root)

    if not wm.workspace_exists(name):
        raise web.HTTPNotFound(reason=f"workspace '{name}' not found")

    warnings = wm.validate_workspace(name)
    return web.json_response(
        {
            "name": name,
            "valid": len(warnings) == 0,
            "warnings": warnings,
        }
    )


# ---------------------------------------------------------------------------
# Webhook handlers
# ---------------------------------------------------------------------------


async def webhook_generic_handler(request: web.Request) -> web.Response:
    """POST /api/webhooks/generic — create a task from an external system."""
    store: Store = request.app["store"]

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(reason=f"Invalid JSON: {exc}") from exc

    workspace = body.get("workspace")
    task_type = body.get("type")
    title = body.get("title")
    instruction = body.get("instruction")

    if not workspace or not title or not instruction:
        raise web.HTTPBadRequest(
            reason="'workspace', 'title', and 'instruction' are required"
        )

    import uuid

    task = Task(
        id=uuid.uuid4().hex[:12],
        type=task_type or "generic",
        workspace=workspace,
        title=title,
        instruction=instruction,
        priority=int(body.get("priority", 3)),
        approval_level=int(body.get("approval_level", 2)),
    )

    await store.create_task(task)
    logger.info("Webhook created task %s: %s", task.id, title)

    return web.json_response({"ok": True, "task_id": task.id}, status=201)


async def webhook_slack_handler(request: web.Request) -> web.Response:
    """POST /api/webhooks/slack — receive Slack slash commands (placeholder)."""
    # Future: parse Slack slash command payloads
    return web.json_response({"ok": True, "message": "Slack webhook received"})


async def webhook_linear_handler(request: web.Request) -> web.Response:
    """POST /api/webhooks/linear — receive Linear webhook events (placeholder)."""
    # Future: parse Linear webhook payloads and create/update tasks
    return web.json_response({"ok": True, "message": "Linear webhook received"})


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_api_app(
    store: Store,
    slack: object | None = None,
    project_root: pathlib.Path | None = None,
) -> web.Application:
    """Create and configure the aiohttp Application.

    Args:
        store: The data store instance.
        slack: Optional SlackNotifier instance for sending notifications.
        project_root: Root directory of the Maestro project (used by workspace
            endpoints).  When *None* the workspace endpoints will raise a
            ``KeyError`` at request time, so callers should supply this.
    """
    app = web.Application(middlewares=[spa_fallback_middleware])
    app["store"] = store
    if slack is not None:
        app["slack"] = slack
    if project_root is not None:
        app["project_root"] = project_root

    # SPA static assets
    if _WEB_DIST.exists():
        app.router.add_static("/assets", _WEB_DIST / "assets", follow_symlinks=True)
        app.router.add_get("/", lambda r: web.FileResponse(_WEB_DIST / "index.html"))

    # Health
    app.router.add_get("/api/internal/health", health_handler)

    # Tasks — list & detail
    app.router.add_get("/api/internal/tasks", tasks_list_handler)
    app.router.add_get("/api/internal/task/{task_id}", task_get_handler)

    # Tasks — mutations
    app.router.add_post("/api/internal/task/update", task_update_handler)
    app.router.add_post("/api/internal/task/result", task_result_handler)
    app.router.add_post("/api/internal/task/{task_id}/approve", task_approve_handler)
    app.router.add_post("/api/internal/task/{task_id}/reject", task_reject_handler)
    app.router.add_post("/api/internal/task/{task_id}/revise", task_revise_handler)

    # Stats
    app.router.add_get("/api/internal/stats", stats_handler)

    # Approvals
    app.router.add_post("/api/internal/approval/submit", approval_submit_handler)
    app.router.add_get("/api/internal/approval/{task_id}", approval_get_handler)
    app.router.add_get("/api/internal/approvals/pending", approvals_pending_handler)

    # History
    app.router.add_post("/api/internal/history/record", history_record_handler)

    # Assets
    app.router.add_post("/api/internal/asset/register", asset_register_handler)
    app.router.add_post("/api/internal/asset/search", asset_search_handler)
    app.router.add_get("/api/internal/asset/{asset_id}", asset_get_handler)
    app.router.add_get("/api/internal/assets", asset_list_handler)

    # Task create + children
    app.router.add_post("/api/internal/task", task_create_handler)
    app.router.add_get("/api/internal/task/{task_id}/children", task_children_handler)

    # Task events & logs
    app.router.add_get("/api/internal/task/{task_id}/events", task_events_handler)
    app.router.add_get("/api/internal/task/{task_id}/logs", task_logs_handler)
    app.router.add_get(
        "/api/internal/task/{task_id}/logs/{log_id}", task_log_detail_handler
    )
    app.router.add_delete("/api/internal/task/{task_id}/logs", task_logs_delete_handler)
    app.router.add_post("/api/internal/logs/cleanup", logs_cleanup_handler)

    # Schedules
    app.router.add_get("/api/internal/schedules", schedules_list_handler)
    app.router.add_post("/api/internal/schedule", schedule_create_handler)
    app.router.add_delete("/api/internal/schedule/{name}", schedule_delete_handler)
    app.router.add_post("/api/internal/schedule/{name}/enable", schedule_enable_handler)
    app.router.add_post(
        "/api/internal/schedule/{name}/disable", schedule_disable_handler
    )

    # Goals
    app.router.add_get("/api/internal/goals", goals_list_handler)
    app.router.add_post("/api/internal/goal", goal_create_handler)
    app.router.add_get("/api/internal/goal/{id}", goal_get_handler)
    app.router.add_delete("/api/internal/goal/{id}", goal_delete_handler)
    app.router.add_post("/api/internal/goal/{id}/enable", goal_enable_handler)
    app.router.add_post("/api/internal/goal/{id}/disable", goal_disable_handler)

    # Rules
    app.router.add_get("/api/internal/rules", rules_list_handler)
    app.router.add_post("/api/internal/rule", rule_create_handler)
    app.router.add_delete(
        "/api/internal/rule/{workspace}/{task_type}", rule_delete_handler
    )

    # Asset delete/archive/cleanup
    app.router.add_delete("/api/internal/asset/{asset_id}", asset_delete_handler)
    app.router.add_post("/api/internal/asset/{asset_id}/archive", asset_archive_handler)
    app.router.add_post("/api/internal/assets/cleanup", assets_cleanup_handler)

    # Workspaces (require project_root)
    if project_root is not None:
        app.router.add_get("/api/internal/workspaces", handle_workspace_list)
        app.router.add_post("/api/internal/workspace", handle_workspace_create)
        app.router.add_get(
            "/api/internal/workspace/{name}/validate", handle_workspace_validate
        )

    # Webhooks
    app.router.add_post("/api/webhooks/generic", webhook_generic_handler)
    app.router.add_post("/api/webhooks/slack", webhook_slack_handler)
    app.router.add_post("/api/webhooks/linear", webhook_linear_handler)

    return app


# Convenience alias used by tests and tooling.
create_app = create_api_app
