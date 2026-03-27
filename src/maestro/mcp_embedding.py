"""
MCP server for asset embedding search.

Runs as: python -m maestro.mcp_embedding

Reads directly from SQLite (read-only, WAL safe) for search/list/get.
Calls daemon HTTP API for write operations (register, search with vectors).

Protocol: JSON-RPC 2.0 over stdin/stdout (MCP standard).

Tools:
  - maestro_asset_register(asset_type, title, ...) -> registered asset
  - maestro_asset_search(query, type?, ...) -> matching assets
  - maestro_asset_get(asset_id) -> asset details
  - maestro_asset_list(tags?, type?, unused_only?) -> asset list
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

logger = logging.getLogger("maestro.mcp_embedding")


# ---------------------------------------------------------------------------
# Store access (read-only via WAL)
# ---------------------------------------------------------------------------


def _store() -> Store:
    """Return a Store instance using the configured DB path."""
    db_path = os.environ.get("MAESTRO_DB_PATH", "./store/maestro.db")
    return Store(db_path)


def _daemon_port() -> int:
    """Resolve daemon port. Env var first, then port file."""
    port = os.environ.get("MAESTRO_DAEMON_PORT", "")
    if port:
        return int(port)

    base = os.environ.get("MAESTRO_BASE_PATH", "")
    if base:
        port_file = Path(base) / ".maestro" / "maestro.port"
    else:
        port_file = Path(".maestro/maestro.port")
    return int(port_file.read_text().strip()) if port_file.exists() else 0


async def _post(port: int, path: str, data: dict) -> dict:
    """POST to the daemon's internal HTTP API."""
    url = f"http://127.0.0.1:{port}{path}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as resp:
            return await resp.json()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def maestro_asset_register(
    asset_type: str,
    title: str,
    content_json: dict | None = None,
    file_path: str | None = None,
    tags: list[str] | None = None,
    description: str | None = None,
    ttl_days: int | None = None,
    created_by: str = "agent",
    task_id: str | None = None,
) -> dict[str, Any]:
    """Register a new asset via daemon HTTP API."""
    payload: dict[str, Any] = {
        "asset_type": asset_type,
        "title": title,
        "created_by": created_by,
    }
    if content_json is not None:
        payload["content_json"] = content_json
    if file_path is not None:
        payload["file_path"] = file_path
    if tags is not None:
        payload["tags"] = tags
    if description is not None:
        payload["description"] = description
    if ttl_days is not None:
        payload["ttl_days"] = ttl_days
    if task_id is not None:
        payload["task_id"] = task_id

    return await _post(_daemon_port(), "/api/internal/asset/register", payload)


async def maestro_asset_search(
    query: str,
    asset_type: str | None = None,
    tags: list[str] | None = None,
    since: str | None = None,
    limit: int = 10,
    include_content: bool = True,
) -> dict[str, Any]:
    """Search assets via daemon HTTP API (supports vector similarity)."""
    payload: dict[str, Any] = {
        "query": query,
        "limit": limit,
        "include_content": include_content,
    }
    if asset_type is not None:
        payload["asset_type"] = asset_type
    if tags is not None:
        payload["tags"] = tags
    if since is not None:
        payload["since"] = since

    result = await _post(_daemon_port(), "/api/internal/asset/search", payload)
    # Wrap in standard format if daemon returns a list directly
    if isinstance(result, list):
        return {"results": result, "query": query, "count": len(result)}
    return result


async def maestro_asset_get(asset_id: str) -> dict[str, Any]:
    """Get asset details by ID."""
    store = _store()
    asset = await store.get_asset(asset_id)
    if asset is None:
        return {"error": f"Asset not found: {asset_id}"}
    return asset


async def maestro_asset_list(
    tags: list[str] | None = None,
    asset_type: str | None = None,
    unused_only: bool = False,
) -> dict[str, Any]:
    """List assets with optional filters."""
    store = _store()
    assets = await store.list_assets(
        asset_type=asset_type,
        tags_contain=tags,
    )
    return {"assets": assets, "count": len(assets)}


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict[str, Any]] = {
    "maestro_asset_register": {
        "description": "Register a new asset (text, image, video, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "asset_type": {
                    "type": "string",
                    "description": (
                        "Asset type (post, image, video,"
                        " audio, document, research, engage)"
                    ),
                },
                "title": {"type": "string", "description": "Human-readable title"},
                "content_json": {
                    "type": "object",
                    "description": "Structured content (for text-based assets)",
                },
                "file_path": {
                    "type": "string",
                    "description": "Path to binary file (image, video, etc.)",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization",
                },
                "description": {"type": "string", "description": "Brief description"},
                "ttl_days": {
                    "type": "integer",
                    "description": "Days until auto-archival (null = permanent)",
                },
                "created_by": {
                    "type": "string",
                    "description": "Creator identifier",
                    "default": "agent",
                },
                "task_id": {
                    "type": "string",
                    "description": "Originating task ID",
                },
            },
            "required": ["asset_type", "title"],
        },
    },
    "maestro_asset_search": {
        "description": "Search assets by semantic query with optional filters",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "asset_type": {
                    "type": "string",
                    "description": "Filter by asset type",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags (any match)",
                },
                "since": {
                    "type": "string",
                    "description": "Only assets created after this ISO datetime",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 10,
                },
                "include_content": {
                    "type": "boolean",
                    "description": "Include content_json in results",
                    "default": True,
                },
            },
            "required": ["query"],
        },
    },
    "maestro_asset_get": {
        "description": "Get asset details by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset ID"},
            },
            "required": ["asset_id"],
        },
    },
    "maestro_asset_list": {
        "description": "List assets with optional filters",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by tags (any match)",
                },
                "type": {
                    "type": "string",
                    "description": "Filter by asset type",
                },
                "unused_only": {
                    "type": "boolean",
                    "description": "Only return unused assets",
                    "default": False,
                },
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------


async def dispatch_tool(name: str, arguments: dict[str, Any]) -> Any:
    """Dispatch a tool call to the appropriate handler."""
    if name == "maestro_asset_register":
        return await maestro_asset_register(
            asset_type=arguments["asset_type"],
            title=arguments["title"],
            content_json=arguments.get("content_json"),
            file_path=arguments.get("file_path"),
            tags=arguments.get("tags"),
            description=arguments.get("description"),
            ttl_days=arguments.get("ttl_days"),
            created_by=arguments.get("created_by", "agent"),
            task_id=arguments.get("task_id"),
        )
    elif name == "maestro_asset_search":
        return await maestro_asset_search(
            query=arguments["query"],
            asset_type=arguments.get("asset_type"),
            tags=arguments.get("tags"),
            since=arguments.get("since"),
            limit=arguments.get("limit", 10),
            include_content=arguments.get("include_content", True),
        )
    elif name == "maestro_asset_get":
        return await maestro_asset_get(arguments["asset_id"])
    elif name == "maestro_asset_list":
        return await maestro_asset_list(
            tags=arguments.get("tags"),
            asset_type=arguments.get("type"),
            unused_only=arguments.get("unused_only", False),
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
                "serverInfo": {"name": "maestro-embedding", "version": "0.1.0"},
            },
        )

    elif method == "notifications/initialized":
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
                    "content": [
                        {"type": "text", "text": json.dumps(result, default=str)}
                    ],
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
        return None


async def main_loop() -> None:
    """Read JSON-RPC messages from stdin and write responses to stdout."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

    writer = sys.stdout

    buffer = b""
    while True:
        chunk = await reader.read(65536)
        if not chunk:
            break

        buffer += chunk

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
    """Entry point for `python -m maestro.mcp_embedding`."""
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
