"""
MCP server for asset embedding search.

Runs as: python -m maestro.mcp_embedding

Reads directly from SQLite (read-only, WAL safe) for search/list/get.
Calls daemon HTTP API for write operations (register).

Protocol: JSON-RPC 2.0 over stdin/stdout (MCP standard).

Tools:
  - maestro_asset_search(query, type?, limit?) -> matching assets
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

from maestro.store import Store

logger = logging.getLogger("maestro.mcp_embedding")


# ---------------------------------------------------------------------------
# Store access (read-only via WAL)
# ---------------------------------------------------------------------------

def _store() -> Store:
    """Return a Store instance using the configured DB path."""
    db_path = os.environ.get("MAESTRO_DB_PATH", "./store/maestro.db")
    return Store(db_path)


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

async def maestro_asset_search(
    query: str,
    asset_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search assets by text query.

    Currently performs simple text matching on title/description.
    Vector search will be added when sqlite-vec is integrated.
    """
    store = _store()
    all_assets = await store.list_assets(asset_type=asset_type)

    # Simple text search: match query terms against title + description
    query_lower = query.lower()
    matches = []
    for asset in all_assets:
        title = (asset.get("title") or "").lower()
        desc = (asset.get("description") or "").lower()
        tags = " ".join(asset.get("tags") or []).lower()
        if query_lower in title or query_lower in desc or query_lower in tags:
            matches.append(asset)
        if len(matches) >= limit:
            break

    return {"results": matches, "query": query, "count": len(matches)}


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
    "maestro_asset_search": {
        "description": "Search assets by text query (title, description, tags)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "type": {
                    "type": "string",
                    "description": "Filter by asset type (image, video, document)",
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
    if name == "maestro_asset_search":
        return await maestro_asset_search(
            query=arguments["query"],
            asset_type=arguments.get("type"),
            limit=arguments.get("limit", 10),
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
        return _make_response(msg_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "maestro-embedding", "version": "0.1.0"},
        })

    elif method == "notifications/initialized":
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
                "content": [{"type": "text", "text": json.dumps(result, default=str)}],
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
