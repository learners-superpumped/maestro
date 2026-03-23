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
from typing import Any

import aiohttp

logger = logging.getLogger("maestro.mcp_store")


# ---------------------------------------------------------------------------
# Daemon HTTP client
# ---------------------------------------------------------------------------

def _daemon_base_url() -> str:
    """Return the base URL for the Maestro daemon's internal API."""
    port = os.environ.get("MAESTRO_DAEMON_PORT", "0")
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
# Tool implementations
# ---------------------------------------------------------------------------

async def maestro_task_get(task_id: str) -> dict[str, Any]:
    """Fetch task details from the daemon."""
    return await _daemon_get(f"/api/internal/task/{task_id}")


async def maestro_task_update_status(task_id: str, status: str) -> dict[str, Any]:
    """Update task status."""
    return await _daemon_post("/api/internal/task/update", {
        "task_id": task_id,
        "status": status,
    })


async def maestro_task_submit_result(
    task_id: str,
    result_json: Any,
    cost_usd: float = 0.0,
) -> dict[str, Any]:
    """Submit task result and mark as completed."""
    return await _daemon_post("/api/internal/task/result", {
        "task_id": task_id,
        "result_json": result_json,
        "cost_usd": cost_usd,
    })


async def maestro_history_search(
    workspace: str,
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search recent actions in workspace history.

    Note: history storage is a placeholder; returns empty results for now.
    """
    # The daemon's history endpoint is a placeholder.
    # We return an empty list until history persistence is implemented.
    return {"results": [], "query": query, "workspace": workspace, "limit": limit}


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
    return await _daemon_post("/api/internal/approval/submit", {
        "task_id": task_id,
        "draft_json": draft_json,
    })


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
                    "description": "New status (pending, approved, running, paused, completed, failed, cancelled)",
                },
            },
            "required": ["task_id", "status"],
        },
    },
    "maestro_task_submit_result": {
        "description": "Submit task result and mark as completed",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "result_json": {"description": "Structured result data"},
                "cost_usd": {
                    "type": "number",
                    "description": "Cost incurred in USD",
                    "default": 0.0,
                },
            },
            "required": ["task_id", "result_json"],
        },
    },
    "maestro_history_search": {
        "description": "Search recent actions in workspace history",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Workspace name"},
                "query": {"type": "string", "description": "Search query"},
                "limit": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 10,
                },
            },
            "required": ["workspace", "query"],
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
    elif name == "maestro_task_submit_result":
        return await maestro_task_submit_result(
            arguments["task_id"],
            arguments["result_json"],
            arguments.get("cost_usd", 0.0),
        )
    elif name == "maestro_history_search":
        return await maestro_history_search(
            arguments["workspace"],
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
        return _make_response(msg_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "maestro-store", "version": "0.1.0"},
        })

    elif method == "notifications/initialized":
        # Client acknowledgement — no response needed
        return None

    elif method == "tools/list":
        tool_list = [
            {"name": name, **info} for name, info in TOOLS.items()
        ]
        return _make_response(msg_id, {"tools": tool_list})

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = await dispatch_tool(tool_name, arguments)
            return _make_response(msg_id, {
                "content": [{"type": "text", "text": json.dumps(result)}],
            })
        except Exception as exc:
            return _make_response(msg_id, {
                "content": [{"type": "text", "text": json.dumps({"error": str(exc)})}],
                "isError": True,
            })

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
