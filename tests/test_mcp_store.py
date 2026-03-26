"""Tests for the MCP store server.

Tests the HTTP client functions (tool implementations) by mocking the
daemon's internal HTTP API with aioresponses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aioresponses import aioresponses

from maestro.mcp_store import (
    TOOLS,
    dispatch_tool,
    handle_message,
    maestro_approval_check,
    maestro_approval_submit,
    maestro_history_record,
    maestro_history_search,
    maestro_task_get,
    maestro_task_update_status,
)


@pytest.fixture(autouse=True)
def set_daemon_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Write maestro.port file for all tests."""
    maestro_dir = tmp_path / ".maestro"
    maestro_dir.mkdir(parents=True)
    (maestro_dir / "maestro.port").write_text("19876")
    monkeypatch.chdir(tmp_path)


BASE = "http://127.0.0.1:19876"


# ---------------------------------------------------------------------------
# Tool function tests (with mocked HTTP)
# ---------------------------------------------------------------------------


class TestTaskGet:
    async def test_returns_task(self) -> None:
        task_data = {
            "id": "abc123",
            "type": "claude",
            "status": "running",
            "agent": "default",
            "title": "Test task",
        }
        with aioresponses() as m:
            m.get(f"{BASE}/api/internal/task/abc123", payload=task_data)
            result = await maestro_task_get("abc123")
        assert result["id"] == "abc123"
        assert result["status"] == "running"


class TestTaskUpdateStatus:
    async def test_updates_status(self) -> None:
        with aioresponses() as m:
            m.post(f"{BASE}/api/internal/task/update", payload={"ok": True})
            result = await maestro_task_update_status("abc123", "completed")
        assert result["ok"] is True


class TestHistorySearch:
    async def test_returns_empty_results(self) -> None:
        result = await maestro_history_search("post")
        assert result["results"] == []
        assert result["query"] == "post"

    async def test_respects_limit(self) -> None:
        result = await maestro_history_search("q", limit=5)
        assert result["limit"] == 5


class TestHistoryRecord:
    async def test_records_action(self) -> None:
        with aioresponses() as m:
            m.post(f"{BASE}/api/internal/history/record", payload={"ok": True})
            result = await maestro_history_record({"type": "post", "content": "hello"})
        assert result["ok"] is True


class TestApprovalCheck:
    async def test_checks_approval_approved(self) -> None:
        with aioresponses() as m:
            m.get(
                f"{BASE}/api/internal/task/t1",
                payload={"id": "t1", "status": "approved"},
            )
            result = await maestro_approval_check("t1")
        assert result["approved"] is True
        assert result["status"] == "approved"

    async def test_checks_approval_pending(self) -> None:
        with aioresponses() as m:
            m.get(
                f"{BASE}/api/internal/task/t1",
                payload={"id": "t1", "status": "paused"},
            )
            result = await maestro_approval_check("t1")
        assert result["approved"] is False


class TestApprovalSubmit:
    async def test_submits_approval(self) -> None:
        with aioresponses() as m:
            m.post(f"{BASE}/api/internal/approval/submit", payload={"ok": True})
            result = await maestro_approval_submit("t1", {"draft": "content"})
        assert result["ok"] is True


# ---------------------------------------------------------------------------
# JSON-RPC message handler tests
# ---------------------------------------------------------------------------


class TestHandleMessage:
    async def test_initialize(self) -> None:
        resp = await handle_message(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            }
        )
        assert resp is not None
        assert resp["id"] == 1
        assert "maestro-store" in resp["result"]["serverInfo"]["name"]

    async def test_tools_list(self) -> None:
        resp = await handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )
        assert resp is not None
        tools = resp["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        assert "maestro_task_get" in tool_names
        assert "maestro_approval_submit" in tool_names
        assert len(tools) == len(TOOLS)

    async def test_tools_call_success(self) -> None:
        with aioresponses() as m:
            m.get(
                f"{BASE}/api/internal/task/x1",
                payload={"id": "x1", "status": "running"},
            )
            resp = await handle_message(
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "maestro_task_get",
                        "arguments": {"task_id": "x1"},
                    },
                }
            )
        assert resp is not None
        assert resp["id"] == 3
        content = resp["result"]["content"][0]
        assert content["type"] == "text"
        data = json.loads(content["text"])
        assert data["id"] == "x1"

    async def test_tools_call_error(self) -> None:
        resp = await handle_message(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "unknown_tool",
                    "arguments": {},
                },
            }
        )
        assert resp is not None
        assert resp["result"]["isError"] is True

    async def test_ping(self) -> None:
        resp = await handle_message(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "ping",
            }
        )
        assert resp is not None
        assert resp["id"] == 5

    async def test_notification_no_response(self) -> None:
        resp = await handle_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )
        assert resp is None

    async def test_unknown_method(self) -> None:
        resp = await handle_message(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "nonexistent/method",
            }
        )
        assert resp is not None
        assert "error" in resp
        assert resp["error"]["code"] == -32601


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------


class TestDispatchTool:
    async def test_dispatch_unknown_tool(self) -> None:
        with pytest.raises(ValueError, match="Unknown tool"):
            await dispatch_tool("not_real", {})

    async def test_dispatch_task_get(self) -> None:
        with aioresponses() as m:
            m.get(f"{BASE}/api/internal/task/t2", payload={"id": "t2"})
            result = await dispatch_tool("maestro_task_get", {"task_id": "t2"})
        assert result["id"] == "t2"
