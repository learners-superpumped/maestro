from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from maestro.assets import AssetManager


def _make_asset_manager(drive_enabled=True):
    store = AsyncMock()
    store.create_asset = AsyncMock(return_value=None)
    store.get_asset = AsyncMock(
        return_value={
            "id": "abc123",
            "title": "test",
            "drive_url": "https://drive.google.com/file/d/f1/view",
        }
    )
    store.store_embedding = AsyncMock()
    store.record_asset_usage = AsyncMock()

    embedding = AsyncMock()
    embedding.embed_asset = AsyncMock(return_value=[0.1] * 3072)

    config = MagicMock()
    config.assets.default_ttl = {}
    config.assets.gemini_api_key = "fake"
    config.drive.enabled = drive_enabled
    config.drive.cache_max_bytes = 1_073_741_824

    drive = AsyncMock()
    drive.available = True
    drive.upload = AsyncMock(
        return_value=MagicMock(
            id="drive-file-1",
            web_view_link="https://drive.google.com/file/d/drive-file-1/view",
        )
    )
    drive.get_or_create_folder = AsyncMock(return_value="folder-123")
    drive.download = AsyncMock(return_value=Path("/tmp/cached.pdf"))

    am = AssetManager(store, embedding, config, Path("/tmp/base"))
    if drive_enabled:
        am._drive = drive
    return am, store, drive


class TestRegisterWithDrive:
    @pytest.mark.asyncio
    async def test_register_uploads_to_drive(self, tmp_path):
        test_file = tmp_path / "report.pdf"
        test_file.write_bytes(b"PDF content")

        am, store, drive = _make_asset_manager()
        await am.register_asset(
            asset_type="document",
            title="Report",
            file_path=str(test_file),
            task_id="MAE-1",
        )

        drive.get_or_create_folder.assert_called_once()
        drive.upload.assert_called_once()
        # Verify drive fields passed to store
        call_args = store.create_asset.call_args[0][0]
        assert call_args["drive_file_id"] == "drive-file-1"
        assert "drive.google.com" in call_args["drive_url"]
        assert call_args["source"] == "drive"  # Drive 업로드 성공 시 "drive"


class TestDownloadAsset:
    @pytest.mark.asyncio
    async def test_download_uses_cache(self, tmp_path):
        am, store, drive = _make_asset_manager()
        cache_dir = tmp_path / "cache" / "assets"
        cache_dir.mkdir(parents=True)
        cached_file = cache_dir / "drive-file-1"
        cached_file.write_bytes(b"cached")
        am._cache_dir = cache_dir

        store.get_asset = AsyncMock(
            return_value={
                "id": "abc",
                "drive_file_id": "drive-file-1",
                "file_path": None,
            }
        )

        path = await am.download_asset("abc")
        assert path == cached_file
        drive.download.assert_not_called()

    @pytest.mark.asyncio
    async def test_download_fetches_from_drive(self, tmp_path):
        am, store, drive = _make_asset_manager()
        cache_dir = tmp_path / "cache" / "assets"
        cache_dir.mkdir(parents=True)
        am._cache_dir = cache_dir

        store.get_asset = AsyncMock(
            return_value={
                "id": "abc",
                "drive_file_id": "drive-file-1",
                "file_path": None,
            }
        )

        path = await am.download_asset("abc")
        drive.download.assert_called_once()


class TestSendAsset:
    @pytest.mark.asyncio
    async def test_send_asset_returns_info(self, tmp_path):
        am, store, drive = _make_asset_manager()
        cache_dir = tmp_path / "cache" / "assets"
        cache_dir.mkdir(parents=True)
        cached_file = cache_dir / "drive-file-1"
        cached_file.write_bytes(b"cached")
        am._cache_dir = cache_dir

        store.get_asset = AsyncMock(
            return_value={
                "id": "abc",
                "drive_file_id": "drive-file-1",
                "file_path": None,
                "drive_url": "https://drive.google.com/file/d/drive-file-1/view",
            }
        )

        result = await am.send_asset("abc")
        assert result is not None
        assert result["local_path"] is not None
        assert result["drive_url"] is not None

    @pytest.mark.asyncio
    async def test_send_asset_not_found(self):
        am, store, drive = _make_asset_manager()
        store.get_asset = AsyncMock(return_value=None)
        result = await am.send_asset("nonexistent")
        assert result is None


class TestShareAsset:
    @pytest.mark.asyncio
    async def test_share_returns_url(self):
        am, store, drive = _make_asset_manager()
        drive.share = AsyncMock(
            return_value="https://drive.google.com/file/d/drive-file-1/view?sharing=true"
        )

        store.get_asset = AsyncMock(
            return_value={
                "id": "abc",
                "drive_file_id": "drive-file-1",
                "drive_url": None,
            }
        )
        store.update_asset = AsyncMock()

        url = await am.share_asset("abc")
        assert url is not None
        assert "drive.google.com" in url
        drive.share.assert_called_once_with("drive-file-1")

    @pytest.mark.asyncio
    async def test_share_no_drive_file_id_returns_none(self):
        am, store, drive = _make_asset_manager()
        store.get_asset = AsyncMock(
            return_value={"id": "abc", "drive_file_id": None, "drive_url": None}
        )
        url = await am.share_asset("abc")
        assert url is None
