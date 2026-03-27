from unittest.mock import AsyncMock, MagicMock


async def test_drive_status_not_connected(aiohttp_client):
    """Drive status returns disconnected when no provider."""
    from maestro.api import create_api_app

    app = create_api_app(
        store=AsyncMock(),
        config=MagicMock(drive=MagicMock(enabled=False)),
    )
    app["drive_provider"] = None
    app["asset_manager"] = AsyncMock()
    client = await aiohttp_client(app)
    resp = await client.get("/api/internal/drive/status")
    assert resp.status == 200
    data = await resp.json()
    assert data["connected"] is False


async def test_drive_status_connected(aiohttp_client):
    """Drive status returns connected when provider exists."""
    from maestro.api import create_api_app

    app = create_api_app(
        store=AsyncMock(),
        config=MagicMock(drive=MagicMock(enabled=True, drive_id="", root_folder_id="")),
    )
    app["drive_provider"] = MagicMock(available=True)
    app["asset_manager"] = AsyncMock()
    client = await aiohttp_client(app)
    resp = await client.get("/api/internal/drive/status")
    assert resp.status == 200
    data = await resp.json()
    assert data["connected"] is True


async def test_asset_download_missing_asset_id(aiohttp_client):
    """asset_id 없으면 400 반환."""
    from maestro.api import create_api_app

    app = create_api_app(store=AsyncMock(), config=MagicMock())
    app["drive_provider"] = None
    am = AsyncMock()
    app["asset_manager"] = am
    client = await aiohttp_client(app)
    resp = await client.post("/api/internal/asset/download", json={})
    assert resp.status == 400


async def test_asset_download_not_found(aiohttp_client):
    """에셋 없으면 404 반환."""
    from maestro.api import create_api_app

    app = create_api_app(store=AsyncMock(), config=MagicMock())
    app["drive_provider"] = None
    am = AsyncMock()
    am.download_asset = AsyncMock(return_value=None)
    app["asset_manager"] = am
    client = await aiohttp_client(app)
    resp = await client.post("/api/internal/asset/download", json={"asset_id": "abc"})
    assert resp.status == 404


async def test_asset_download_success(aiohttp_client, tmp_path):
    """에셋 다운로드 성공 시 local_path 반환."""
    from maestro.api import create_api_app

    app = create_api_app(store=AsyncMock(), config=MagicMock())
    app["drive_provider"] = None
    am = AsyncMock()
    am.download_asset = AsyncMock(return_value=tmp_path / "test.pdf")
    app["asset_manager"] = am
    client = await aiohttp_client(app)
    resp = await client.post("/api/internal/asset/download", json={"asset_id": "abc"})
    assert resp.status == 200
    data = await resp.json()
    assert "local_path" in data
    assert data["asset_id"] == "abc"


async def test_asset_share_not_found(aiohttp_client):
    """Drive URL 없으면 404 반환."""
    from maestro.api import create_api_app

    app = create_api_app(store=AsyncMock(), config=MagicMock())
    app["drive_provider"] = None
    am = AsyncMock()
    am.share_asset = AsyncMock(return_value=None)
    app["asset_manager"] = am
    client = await aiohttp_client(app)
    resp = await client.post("/api/internal/asset/share", json={"asset_id": "abc"})
    assert resp.status == 404


async def test_asset_share_success(aiohttp_client):
    """Drive 공유 링크 생성 성공."""
    from maestro.api import create_api_app

    app = create_api_app(store=AsyncMock(), config=MagicMock())
    app["drive_provider"] = None
    am = AsyncMock()
    am.share_asset = AsyncMock(return_value="https://drive.google.com/file/d/abc/view")
    app["asset_manager"] = am
    client = await aiohttp_client(app)
    resp = await client.post("/api/internal/asset/share", json={"asset_id": "abc"})
    assert resp.status == 200
    data = await resp.json()
    assert data["drive_url"] == "https://drive.google.com/file/d/abc/view"


async def test_asset_send_slack_not_available(aiohttp_client):
    """Slack 없으면 503 반환."""
    from maestro.api import create_api_app

    app = create_api_app(store=AsyncMock(), config=MagicMock())
    app["drive_provider"] = None
    am = AsyncMock()
    am.send_asset = AsyncMock(
        return_value={"asset": {"title": "test"}, "local_path": None, "drive_url": None}
    )
    app["asset_manager"] = am
    app["slack_adapter"] = None  # Slack not available
    client = await aiohttp_client(app)
    resp = await client.post(
        "/api/internal/asset/send", json={"asset_id": "abc", "channel": "#general"}
    )
    assert resp.status == 503
