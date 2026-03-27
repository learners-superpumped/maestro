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
