"""Tests for maestro.integrations.linear — Linear client."""

from __future__ import annotations

from unittest.mock import patch

from maestro.integrations.linear import LinearClient

# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_available_with_both() -> None:
    client = LinearClient(api_key="lin_key", project_slug="my-project")
    assert client.available is True


def test_unavailable_without_key() -> None:
    with patch.dict("os.environ", {}, clear=True):
        client = LinearClient(api_key=None, project_slug="my-project")
        assert client.available is False


def test_unavailable_without_slug() -> None:
    client = LinearClient(api_key="lin_key", project_slug=None)
    assert client.available is False


def test_unavailable_returns_empty() -> None:
    with patch.dict("os.environ", {}, clear=True):
        client = LinearClient()
        assert client.available is False


async def test_fetch_issues_unavailable_returns_empty() -> None:
    with patch.dict("os.environ", {}, clear=True):
        client = LinearClient()
        result = await client.fetch_issues()
        assert result == []


async def test_update_issue_unavailable_returns_false() -> None:
    with patch.dict("os.environ", {}, clear=True):
        client = LinearClient()
        result = await client.update_issue_state("issue-1", "Done")
        assert result is False


# ---------------------------------------------------------------------------
# Mock API
# ---------------------------------------------------------------------------


async def test_fetch_issues_success(aiohttp_server) -> None:
    """fetch_issues() parses Linear GraphQL response."""
    from aiohttp import web

    async def handler(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "data": {
                    "project": {
                        "issues": {
                            "nodes": [
                                {
                                    "id": "issue-1",
                                    "identifier": "PRJ-1",
                                    "title": "Fix bug",
                                    "description": "There is a bug",
                                    "state": {"name": "Todo"},
                                    "priority": 1,
                                },
                                {
                                    "id": "issue-2",
                                    "identifier": "PRJ-2",
                                    "title": "Add feature",
                                    "description": None,
                                    "state": {"name": "In Progress"},
                                    "priority": 2,
                                },
                            ]
                        }
                    }
                }
            }
        )

    app = web.Application()
    app.router.add_post("/graphql", handler)
    server = await aiohttp_server(app)

    client = LinearClient(api_key="test-key", project_slug="my-proj")
    client._endpoint = f"http://127.0.0.1:{server.port}/graphql"

    issues = await client.fetch_issues()

    assert len(issues) == 2
    assert issues[0]["id"] == "issue-1"
    assert issues[0]["title"] == "Fix bug"
    assert issues[0]["state"] == "Todo"
    assert issues[1]["identifier"] == "PRJ-2"


async def test_fetch_issues_empty_project(aiohttp_server) -> None:
    """fetch_issues() returns empty list when project not found."""
    from aiohttp import web

    async def handler(request: web.Request) -> web.Response:
        return web.json_response({"data": {"project": None}})

    app = web.Application()
    app.router.add_post("/graphql", handler)
    server = await aiohttp_server(app)

    client = LinearClient(api_key="test-key", project_slug="missing")
    client._endpoint = f"http://127.0.0.1:{server.port}/graphql"

    issues = await client.fetch_issues()
    assert issues == []


async def test_fetch_issues_api_error(aiohttp_server) -> None:
    """fetch_issues() returns empty list on API error."""
    from aiohttp import web

    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=500)

    app = web.Application()
    app.router.add_post("/graphql", handler)
    server = await aiohttp_server(app)

    client = LinearClient(api_key="test-key", project_slug="proj")
    client._endpoint = f"http://127.0.0.1:{server.port}/graphql"

    issues = await client.fetch_issues()
    assert issues == []
