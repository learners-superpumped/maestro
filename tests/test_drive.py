"""Tests for maestro.drive -- Google Drive async wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from maestro.drive import DriveFile, DriveProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    drive_id: str = "",
    root_folder_id: str = "",
) -> DriveProvider:
    """Build a DriveProvider with a mocked Google API service."""
    with patch("maestro.drive.DriveProvider.__init__", lambda self, *a, **kw: None):
        provider = DriveProvider.__new__(DriveProvider)

    provider._drive_id = drive_id
    provider._root_folder_id = root_folder_id
    provider._folder_cache = {}
    provider._service = MagicMock()
    return provider


def _mock_execute(return_value: dict | list):
    """Return a mock that responds to ``.execute()``."""
    m = MagicMock()
    m.execute.return_value = return_value
    return m


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_available_with_service(self):
        p = _make_provider()
        assert p.available is True

    def test_not_available_without_service(self):
        p = _make_provider()
        p._service = None
        assert p.available is False

    def test_drive_params_without_shared_drive(self):
        p = _make_provider()
        params = p._drive_params()
        assert params == {"supportsAllDrives": True}

    def test_drive_params_with_shared_drive(self):
        p = _make_provider(drive_id="shared123")
        params = p._drive_params()
        assert params["supportsAllDrives"] is True
        assert params["driveId"] == "shared123"
        assert params["corpora"] == "drive"

    def test_parent_id_root_folder(self):
        p = _make_provider(root_folder_id="folder1", drive_id="drive1")
        assert p._parent_id() == "folder1"

    def test_parent_id_drive(self):
        p = _make_provider(drive_id="drive1")
        assert p._parent_id() == "drive1"

    def test_parent_id_default(self):
        p = _make_provider()
        assert p._parent_id() == "root"


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


class TestUpload:
    @pytest.fixture
    def provider(self):
        return _make_provider()

    async def test_upload_returns_drive_file(self, provider, tmp_path):
        test_file = tmp_path / "hello.txt"
        test_file.write_text("content")

        mock_result = {
            "id": "file123",
            "name": "hello.txt",
            "mimeType": "text/plain",
            "webViewLink": "https://drive.google.com/file/d/file123/view",
            "size": "7",
            "parents": ["root"],
        }

        create_req = _mock_execute(mock_result)
        provider._service.files.return_value.create.return_value = create_req

        with patch("googleapiclient.http.MediaFileUpload"):
            result = await provider.upload(test_file)

        assert isinstance(result, DriveFile)
        assert result.id == "file123"
        assert result.name == "hello.txt"
        assert result.size == 7

    async def test_upload_custom_name(self, provider, tmp_path):
        test_file = tmp_path / "hello.txt"
        test_file.write_text("content")

        mock_result = {
            "id": "file456",
            "name": "custom.txt",
            "mimeType": "text/plain",
            "webViewLink": "https://drive.google.com/file/d/file456/view",
            "size": "7",
            "parents": ["root"],
        }

        create_req = _mock_execute(mock_result)
        provider._service.files.return_value.create.return_value = create_req

        with patch("googleapiclient.http.MediaFileUpload"):
            result = await provider.upload(test_file, name="custom.txt")

        assert result.name == "custom.txt"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


class TestDownload:
    async def test_download_writes_file(self, tmp_path):
        provider = _make_provider()
        dest = tmp_path / "out" / "file.bin"

        get_media_req = MagicMock()
        provider._service.files.return_value.get_media.return_value = get_media_req

        with patch("googleapiclient.http.MediaIoBaseDownload") as mock_dl_cls:
            instance = MagicMock()
            # Simulate two chunks: first not done, second done
            instance.next_chunk.side_effect = [(None, False), (None, True)]
            mock_dl_cls.return_value = instance

            result = await provider.download("file123", dest)

        assert result == dest
        assert dest.parent.exists()


# ---------------------------------------------------------------------------
# get_or_create_folder
# ---------------------------------------------------------------------------


class TestGetOrCreateFolder:
    async def test_existing_folder(self):
        provider = _make_provider()

        list_req = _mock_execute({"files": [{"id": "existing1", "name": "myfolder"}]})
        provider._service.files.return_value.list.return_value = list_req

        folder_id = await provider.get_or_create_folder("myfolder")

        assert folder_id == "existing1"
        # Should be cached
        assert provider._folder_cache.get("root:myfolder") == "existing1"

    async def test_create_missing_folder(self):
        provider = _make_provider()

        list_req = _mock_execute({"files": []})
        provider._service.files.return_value.list.return_value = list_req

        create_req = _mock_execute({"id": "new1"})
        provider._service.files.return_value.create.return_value = create_req

        folder_id = await provider.get_or_create_folder("newfolder")

        assert folder_id == "new1"

    async def test_nested_path(self):
        provider = _make_provider()

        # First call finds "a", second finds nothing and creates "b"
        list_req_found = _mock_execute({"files": [{"id": "a_id", "name": "a"}]})
        list_req_empty = _mock_execute({"files": []})
        provider._service.files.return_value.list.side_effect = [
            list_req_found,
            list_req_empty,
        ]

        create_req = _mock_execute({"id": "b_id"})
        provider._service.files.return_value.create.return_value = create_req

        folder_id = await provider.get_or_create_folder("a/b")

        assert folder_id == "b_id"

    async def test_cached_folder(self):
        provider = _make_provider()
        provider._folder_cache[":myfolder"] = "cached123"

        folder_id = await provider.get_or_create_folder("myfolder")
        assert folder_id == "cached123"


# ---------------------------------------------------------------------------
# Share
# ---------------------------------------------------------------------------


class TestShare:
    async def test_share_creates_permission(self):
        provider = _make_provider()

        perm_req = _mock_execute({})
        provider._service.permissions.return_value.create.return_value = perm_req

        get_req = _mock_execute(
            {"webViewLink": "https://drive.google.com/file/d/f1/view"}
        )
        provider._service.files.return_value.get.return_value = get_req

        link = await provider.share("f1")

        assert link == "https://drive.google.com/file/d/f1/view"
        provider._service.permissions.return_value.create.assert_called_once()

    async def test_share_without_anyone_link(self):
        provider = _make_provider()

        get_req = _mock_execute(
            {"webViewLink": "https://drive.google.com/file/d/f1/view"}
        )
        provider._service.files.return_value.get.return_value = get_req

        link = await provider.share("f1", anyone_with_link=False)

        assert link == "https://drive.google.com/file/d/f1/view"
        provider._service.permissions.return_value.create.assert_not_called()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDelete:
    async def test_delete_trashes_file(self):
        provider = _make_provider()

        update_req = _mock_execute({})
        provider._service.files.return_value.update.return_value = update_req

        await provider.delete("f1")
        provider._service.files.return_value.update.assert_called_once()


# ---------------------------------------------------------------------------
# get_metadata
# ---------------------------------------------------------------------------


class TestGetMetadata:
    async def test_get_metadata(self):
        provider = _make_provider()

        get_req = _mock_execute(
            {
                "id": "f1",
                "name": "test.pdf",
                "mimeType": "application/pdf",
                "webViewLink": "https://drive.google.com/file/d/f1/view",
                "size": "1024",
                "parents": ["root"],
            }
        )
        provider._service.files.return_value.get.return_value = get_req

        result = await provider.get_metadata("f1")
        assert isinstance(result, DriveFile)
        assert result.id == "f1"
        assert result.size == 1024


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    async def test_search_returns_files(self):
        provider = _make_provider()

        list_req = _mock_execute(
            {
                "files": [
                    {
                        "id": "s1",
                        "name": "result.png",
                        "mimeType": "image/png",
                        "webViewLink": "https://drive.google.com/file/d/s1/view",
                        "size": "500",
                        "parents": ["root"],
                    }
                ]
            }
        )
        provider._service.files.return_value.list.return_value = list_req

        results = await provider.search("name contains 'result'")
        assert len(results) == 1
        assert results[0].name == "result.png"


# ---------------------------------------------------------------------------
# list_shared_drives / list_folders
# ---------------------------------------------------------------------------


class TestListDrives:
    async def test_list_shared_drives(self):
        provider = _make_provider()

        list_req = _mock_execute({"drives": [{"id": "d1", "name": "Team Drive"}]})
        provider._service.drives.return_value.list.return_value = list_req

        drives = await provider.list_shared_drives()
        assert len(drives) == 1
        assert drives[0]["name"] == "Team Drive"


class TestListFolders:
    async def test_list_folders(self):
        provider = _make_provider()

        list_req = _mock_execute({"files": [{"id": "f1", "name": "Folder A"}]})
        provider._service.files.return_value.list.return_value = list_req

        folders = await provider.list_folders(parent_id="root")
        assert len(folders) == 1
        assert folders[0]["name"] == "Folder A"
