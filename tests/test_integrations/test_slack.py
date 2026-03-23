"""Tests for maestro.integrations.slack — Slack notifier."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maestro.integrations.slack import SlackNotifier


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_available_with_url() -> None:
    notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
    assert notifier.available is True


def test_unavailable_without_url() -> None:
    notifier = SlackNotifier(webhook_url=None)
    # Ensure env var is also absent
    with patch.dict("os.environ", {}, clear=True):
        n = SlackNotifier()
        assert n.available is False


def test_available_from_env() -> None:
    with patch.dict("os.environ", {"MAESTRO_SLACK_WEBHOOK": "https://hooks.slack.com/env"}):
        notifier = SlackNotifier()
        assert notifier.available is True


# ---------------------------------------------------------------------------
# send()
# ---------------------------------------------------------------------------


async def test_send_unavailable_returns_false() -> None:
    notifier = SlackNotifier(webhook_url=None)
    with patch.dict("os.environ", {}, clear=True):
        n = SlackNotifier()
        result = await n.send("hello")
        assert result is False


async def test_send_success(aiohttp_server) -> None:
    """send() returns True on HTTP 200."""
    from aiohttp import web

    received = []

    async def handler(request: web.Request) -> web.Response:
        body = await request.json()
        received.append(body)
        return web.Response(status=200)

    app = web.Application()
    app.router.add_post("/webhook", handler)
    server = await aiohttp_server(app)

    url = f"http://127.0.0.1:{server.port}/webhook"
    notifier = SlackNotifier(webhook_url=url)
    result = await notifier.send("test message")

    assert result is True
    assert len(received) == 1
    assert received[0]["text"] == "test message"


async def test_send_with_channel(aiohttp_server) -> None:
    """send() includes channel in payload when provided."""
    from aiohttp import web

    received = []

    async def handler(request: web.Request) -> web.Response:
        body = await request.json()
        received.append(body)
        return web.Response(status=200)

    app = web.Application()
    app.router.add_post("/webhook", handler)
    server = await aiohttp_server(app)

    url = f"http://127.0.0.1:{server.port}/webhook"
    notifier = SlackNotifier(webhook_url=url)
    await notifier.send("msg", channel="#ops")

    assert received[0]["channel"] == "#ops"


async def test_send_failure_returns_false(aiohttp_server) -> None:
    """send() returns False on non-200 status."""
    from aiohttp import web

    async def handler(request: web.Request) -> web.Response:
        return web.Response(status=500)

    app = web.Application()
    app.router.add_post("/webhook", handler)
    server = await aiohttp_server(app)

    url = f"http://127.0.0.1:{server.port}/webhook"
    notifier = SlackNotifier(webhook_url=url)
    result = await notifier.send("fail")

    assert result is False


# ---------------------------------------------------------------------------
# Formatted messages
# ---------------------------------------------------------------------------


async def test_approval_request_format(aiohttp_server) -> None:
    from aiohttp import web

    received = []

    async def handler(request: web.Request) -> web.Response:
        body = await request.json()
        received.append(body)
        return web.Response(status=200)

    app = web.Application()
    app.router.add_post("/webhook", handler)
    server = await aiohttp_server(app)

    url = f"http://127.0.0.1:{server.port}/webhook"
    notifier = SlackNotifier(webhook_url=url)
    result = await notifier.send_approval_request("t1", "My Task", "draft content here")

    assert result is True
    text = received[0]["text"]
    assert "Approval Required" in text
    assert "My Task" in text
    assert "t1" in text
    assert "draft content here" in text


async def test_completion_format(aiohttp_server) -> None:
    from aiohttp import web

    received = []

    async def handler(request: web.Request) -> web.Response:
        body = await request.json()
        received.append(body)
        return web.Response(status=200)

    app = web.Application()
    app.router.add_post("/webhook", handler)
    server = await aiohttp_server(app)

    url = f"http://127.0.0.1:{server.port}/webhook"
    notifier = SlackNotifier(webhook_url=url)
    result = await notifier.send_completion("t2", "Done Task")

    assert result is True
    text = received[0]["text"]
    assert "Task Completed" in text
    assert "Done Task" in text
    assert "t2" in text
