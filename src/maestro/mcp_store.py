"""
MCP server for Maestro store operations.

Runs as: python -m maestro.mcp_store

Communicates with the Maestro daemon via its internal HTTP API.
Exposes tools that Claude Code sessions can call for task management,
history search, and approval workflows.

Protocol: JSON-RPC 2.0 over stdin/stdout (MCP standard).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import aiohttp

from maestro.store import Store

logger = logging.getLogger("maestro.mcp_store")


# ---------------------------------------------------------------------------
# Daemon HTTP client
# ---------------------------------------------------------------------------


def _daemon_base_url() -> str:
    """Return the base URL for the Maestro daemon's internal API.

    Resolution order:
    1. MAESTRO_DAEMON_PORT env var (set by daemon when spawning agents)
    2. .maestro/maestro.port file relative to MAESTRO_BASE_PATH
    3. .maestro/maestro.port file relative to cwd (fallback)
    """

    port = os.environ.get("MAESTRO_DAEMON_PORT", "")
    if port:
        return f"http://127.0.0.1:{port}"

    base = os.environ.get("MAESTRO_BASE_PATH", "")
    if base:
        port_file = Path(base) / ".maestro" / "maestro.port"
    else:
        port_file = Path(".maestro/maestro.port")
    port = port_file.read_text().strip() if port_file.exists() else "0"
    return f"http://127.0.0.1:{port}"


async def _daemon_get(path: str) -> dict[str, Any]:
    """Send a GET request to the daemon API."""
    url = f"{_daemon_base_url()}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()


async def _daemon_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Send a POST request to the daemon API."""
    url = f"{_daemon_base_url()}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=body) as resp:
            resp.raise_for_status()
            return await resp.json()


# ---------------------------------------------------------------------------
# Store helper
# ---------------------------------------------------------------------------


def _store() -> Store:
    """Return a Store instance using the configured DB path."""
    db_path = os.environ.get("MAESTRO_DB_PATH", "./store/maestro.db")
    return Store(db_path)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def maestro_task_get(task_id: str) -> dict[str, Any]:
    """Fetch task details from the daemon."""
    return await _daemon_get(f"/api/internal/task/{task_id}")


async def maestro_task_update_status(task_id: str, status: str) -> dict[str, Any]:
    """Update task status."""
    return await _daemon_post(
        "/api/internal/task/update",
        {
            "task_id": task_id,
            "status": status,
        },
    )


async def maestro_history_search(
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search past completed/failed tasks by keyword.

    Returns matching tasks ranked by relevance and recency.
    Use this to find if similar work was done before.
    """
    return await _daemon_get(
        f"/api/internal/history/search?query={query}&limit={limit}"
    )


async def maestro_history_record(action: dict[str, Any]) -> dict[str, Any]:
    """Record an action to history."""
    return await _daemon_post("/api/internal/history/record", action)


async def maestro_approval_check(task_id: str) -> dict[str, Any]:
    """Check approval status for a task."""
    try:
        approval = await _daemon_get(f"/api/internal/approval/{task_id}")
        return {
            "task_id": task_id,
            "approval_status": approval.get("status"),
            "approved": approval.get("status") == "approved",
            "reviewer_note": approval.get("reviewer_note"),
            "revised_content": approval.get("revised_content"),
        }
    except Exception:
        # Fallback to task status check if no approval record
        task = await _daemon_get(f"/api/internal/task/{task_id}")
        return {
            "task_id": task_id,
            "status": task.get("status"),
            "approved": task.get("status") == "approved",
        }


async def maestro_approval_submit(
    task_id: str,
    draft_json: Any,
) -> dict[str, Any]:
    """Submit a draft for approval, pausing the task."""
    return await _daemon_post(
        "/api/internal/approval/submit",
        {
            "task_id": task_id,
            "draft_json": draft_json,
        },
    )


# ---------------------------------------------------------------------------
# Conductor tool implementations
# ---------------------------------------------------------------------------


async def maestro_goal_create(
    id: str,
    description: str = "",
    metrics: dict | None = None,
    cooldown_hours: int = 24,
) -> dict[str, Any]:
    """Create a new Goal."""
    return await _daemon_post(
        "/api/internal/goal",
        {
            "id": id,
            "description": description,
            "metrics": metrics or {},
            "cooldown_hours": cooldown_hours,
        },
    )


async def maestro_goal_list() -> dict[str, Any]:
    """List all goals."""
    return await _daemon_get("/api/internal/goals")


async def maestro_goal_update(
    id: str,
    description: str | None = None,
    metrics: dict | None = None,
    cooldown_hours: int | None = None,
) -> dict[str, Any]:
    """Update an existing goal."""
    body: dict[str, Any] = {}
    if description is not None:
        body["description"] = description
    if metrics is not None:
        body["metrics"] = metrics
    if cooldown_hours is not None:
        body["cooldown_hours"] = cooldown_hours
    url = f"{_daemon_base_url()}/api/internal/goal/{id}"
    async with aiohttp.ClientSession() as sess:
        async with sess.put(url, json=body) as resp:
            resp.raise_for_status()
            return await resp.json()


async def maestro_goal_trigger(goal_id: str) -> dict[str, Any]:
    """Trigger a goal -- runs the planner immediately."""
    return await _daemon_post(f"/api/internal/goal/{goal_id}/trigger", {})


async def maestro_task_create(
    title: str,
    instruction: str,
    agent: str = "default",
    priority: int = 3,
    approval_level: int = 2,
    budget_usd: float = 5.0,
    goal_id: str | None = None,
) -> dict[str, Any]:
    """Create a new task."""
    body: dict[str, Any] = {
        "title": title,
        "instruction": instruction,
        "agent": agent,
        "priority": priority,
        "approval_level": approval_level,
        "budget_usd": budget_usd,
    }
    if goal_id is not None:
        body["goal_id"] = goal_id
    return await _daemon_post("/api/internal/task", body)


async def maestro_task_list(status: str | None = None) -> dict[str, Any]:
    """List tasks, optionally filtered by status."""
    path = "/api/internal/tasks"
    if status:
        path = f"{path}?status={status}"
    return await _daemon_get(path)


async def maestro_task_cancel(task_id: str) -> dict[str, Any]:
    """Cancel a task."""
    return await _daemon_post(f"/api/internal/task/{task_id}/cancel", {})


async def maestro_task_update_priority(task_id: str, priority: int) -> dict[str, Any]:
    """Update a task's priority."""
    return await _daemon_post(
        f"/api/internal/task/{task_id}/priority",
        {"priority": priority},
    )


async def maestro_budget_status() -> dict[str, Any]:
    """Get current daily budget status."""
    return await _daemon_get("/api/internal/budget/status")


async def maestro_system_status() -> dict[str, Any]:
    """Get system-wide status snapshot."""
    return await _daemon_get("/api/internal/system/status")


async def maestro_reminder_create(
    user_id: str,
    message: str,
    trigger_at: str,
) -> dict[str, Any]:
    """Create a one-shot reminder."""
    return await _daemon_post(
        "/api/internal/reminder",
        {
            "user_id": user_id,
            "message": message,
            "trigger_at": trigger_at,
        },
    )


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict[str, Any]] = {
    "maestro_task_get": {
        "description": "Get task details by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
            },
            "required": ["task_id"],
        },
    },
    "maestro_task_update_status": {
        "description": "Update the status of a task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "status": {
                    "type": "string",
                    "description": (
                        "New status (pending, approved, running,"
                        " paused, completed, failed, cancelled)"
                    ),
                },
            },
            "required": ["task_id", "status"],
        },
    },
    "maestro_history_search": {
        "description": (
            "Search past completed/failed tasks by keyword. "
            "Returns matching tasks ranked by relevance and recency. "
            "Use this to find if similar work was done before."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keywords (natural language)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    "maestro_history_record": {
        "description": "Record an action to history",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "object",
                    "description": "Action data to record",
                },
            },
            "required": ["action"],
        },
    },
    "maestro_approval_check": {
        "description": "Check approval status for a task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
            },
            "required": ["task_id"],
        },
    },
    "maestro_approval_submit": {
        "description": "Submit a draft for approval (pauses the task)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "draft_json": {"description": "Draft data for review"},
            },
            "required": ["task_id", "draft_json"],
        },
    },
    "maestro_goal_create": {
        "description": "Create a new Goal for the planner to decompose into tasks",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique goal ID"},
                "description": {"type": "string", "description": "Goal description"},
                "metrics": {
                    "type": "object",
                    "description": "Success metrics (JSON object)",
                },
                "cooldown_hours": {
                    "type": "integer",
                    "description": "Hours between re-evaluations",
                    "default": 24,
                },
            },
            "required": ["id"],
        },
    },
    "maestro_goal_list": {
        "description": "List all active goals",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "maestro_goal_update": {
        "description": "Update or modify an existing goal",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Goal ID to update"},
                "description": {"type": "string", "description": "New description"},
                "metrics": {"type": "object", "description": "Updated metrics"},
                "cooldown_hours": {
                    "type": "integer",
                    "description": "Updated cooldown hours",
                },
            },
            "required": ["id"],
        },
    },
    "maestro_goal_trigger": {
        "description": (
            "Trigger a goal immediately — runs the planner for this goal,"
            " bypassing cooldown, and creates tasks automatically."
            " Use this when the user wants to 'execute' or 'run' a goal."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal_id": {"type": "string", "description": "Goal ID to trigger"},
            },
            "required": ["goal_id"],
        },
    },
    "maestro_task_create": {
        "description": "Create a new task directly",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Task title"},
                "instruction": {"type": "string", "description": "Task instruction"},
                "agent": {
                    "type": "string",
                    "description": "Agent definition name",
                    "default": "default",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority 1 (urgent) to 5 (low)",
                    "default": 3,
                },
                "approval_level": {
                    "type": "integer",
                    "description": "0=auto, 1=post-notify, 2=pre-approve",
                    "default": 2,
                },
                "budget_usd": {
                    "type": "number",
                    "description": "Max budget in USD",
                    "default": 5.0,
                },
                "goal_id": {"type": "string", "description": "Parent goal ID"},
            },
            "required": ["title", "instruction"],
        },
    },
    "maestro_task_list": {
        "description": "List tasks, optionally filtered by status",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": (
                        "Filter by status (pending, approved, running,"
                        " completed, failed, cancelled)"
                    ),
                },
            },
        },
    },
    "maestro_task_cancel": {
        "description": "Cancel a task",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID to cancel"},
            },
            "required": ["task_id"],
        },
    },
    "maestro_task_update_priority": {
        "description": "Update a task's priority",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "priority": {
                    "type": "integer",
                    "description": "New priority 1 (urgent) to 5 (low)",
                },
            },
            "required": ["task_id", "priority"],
        },
    },
    "maestro_budget_status": {
        "description": "Get current daily budget status (spend, limit, remaining)",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "maestro_system_status": {
        "description": (
            "Get system-wide status snapshot: running tasks, pending approvals,"
            " today's spend, active goals, and recent completions"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    "maestro_reminder_create": {
        "description": "Create a one-shot reminder that triggers at a specified time",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User ID for the reminder",
                    "default": "default",
                },
                "message": {
                    "type": "string",
                    "description": "Reminder message",
                },
                "trigger_at": {
                    "type": "string",
                    "description": "ISO timestamp when to trigger",
                },
            },
            "required": ["message", "trigger_at"],
        },
    },
}


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


async def dispatch_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch a tool call to the appropriate handler."""
    if name == "maestro_task_get":
        return await maestro_task_get(arguments["task_id"])
    elif name == "maestro_task_update_status":
        return await maestro_task_update_status(
            arguments["task_id"], arguments["status"]
        )
    elif name == "maestro_history_search":
        return await maestro_history_search(
            arguments["query"],
            arguments.get("limit", 10),
        )
    elif name == "maestro_history_record":
        return await maestro_history_record(arguments["action"])
    elif name == "maestro_approval_check":
        return await maestro_approval_check(arguments["task_id"])
    elif name == "maestro_approval_submit":
        return await maestro_approval_submit(
            arguments["task_id"], arguments["draft_json"]
        )
    elif name == "maestro_goal_create":
        return await maestro_goal_create(
            id=arguments["id"],
            description=arguments.get("description", ""),
            metrics=arguments.get("metrics"),
            cooldown_hours=arguments.get("cooldown_hours", 24),
        )
    elif name == "maestro_goal_list":
        return await maestro_goal_list()
    elif name == "maestro_goal_update":
        return await maestro_goal_update(
            id=arguments["id"],
            description=arguments.get("description"),
            metrics=arguments.get("metrics"),
            cooldown_hours=arguments.get("cooldown_hours"),
        )
    elif name == "maestro_goal_trigger":
        return await maestro_goal_trigger(arguments["goal_id"])
    elif name == "maestro_task_create":
        return await maestro_task_create(
            title=arguments["title"],
            instruction=arguments["instruction"],
            agent=arguments.get("agent", "default"),
            priority=arguments.get("priority", 3),
            approval_level=arguments.get("approval_level", 2),
            budget_usd=arguments.get("budget_usd", 5.0),
            goal_id=arguments.get("goal_id"),
        )
    elif name == "maestro_task_list":
        return await maestro_task_list(status=arguments.get("status"))
    elif name == "maestro_task_cancel":
        return await maestro_task_cancel(arguments["task_id"])
    elif name == "maestro_task_update_priority":
        return await maestro_task_update_priority(
            arguments["task_id"], arguments["priority"]
        )
    elif name == "maestro_budget_status":
        return await maestro_budget_status()
    elif name == "maestro_system_status":
        return await maestro_system_status()
    elif name == "maestro_reminder_create":
        return await maestro_reminder_create(
            user_id=arguments.get("user_id", "default"),
            message=arguments["message"],
            trigger_at=arguments["trigger_at"],
        )
    else:
        raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 over stdin/stdout
# ---------------------------------------------------------------------------


def _make_response(id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _make_error(id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


async def handle_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Handle a single JSON-RPC message and return the response."""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        return _make_response(
            msg_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "maestro-store", "version": "0.1.0"},
            },
        )

    elif method == "notifications/initialized":
        # Client acknowledgement — no response needed
        return None

    elif method == "tools/list":
        tool_list = [{"name": name, **info} for name, info in TOOLS.items()]
        return _make_response(msg_id, {"tools": tool_list})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = await dispatch_tool(tool_name, arguments)
            return _make_response(
                msg_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                },
            )
        except Exception as exc:
            return _make_response(
                msg_id,
                {
                    "content": [
                        {"type": "text", "text": json.dumps({"error": str(exc)})}
                    ],
                    "isError": True,
                },
            )

    elif method == "ping":
        return _make_response(msg_id, {})

    else:
        if msg_id is not None:
            return _make_error(msg_id, -32601, f"Method not found: {method}")
        return None  # Notification — no response for unknown notifications


async def main_loop() -> None:
    """Read JSON-RPC messages from stdin and write responses to stdout."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    # We write directly to stdout buffer for binary output
    writer = sys.stdout

    buffer = b""
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break  # EOF

        buffer += chunk

        # Process complete lines (JSON-RPC messages are newline-delimited)
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received: %s", line[:200])
                continue

            response = await handle_message(msg)
            if response is not None:
                output = json.dumps(response) + "\n"
                writer.write(output)
                writer.flush()


def main() -> None:
    """Entry point for `python -m maestro.mcp_store`."""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
