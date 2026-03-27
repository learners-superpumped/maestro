"""Google Drive API v3 async wrapper for Maestro."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class DriveFile:
    """Lightweight representation of a Google Drive file."""

    id: str
    name: str
    mime_type: str
    web_view_link: str
    size: int = 0
    parent_id: str = ""


class DriveProvider:
    """Async wrapper around the Google Drive API v3.

    All Google API calls are dispatched to a thread-pool via
    ``asyncio.get_event_loop().run_in_executor`` so they never block the
    event-loop.
    """

    FOLDER_MIME = "application/vnd.google-apps.folder"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        drive_id: str = "",
        root_folder_id: str = "",
    ) -> None:
        self._drive_id = drive_id
        self._root_folder_id = root_folder_id
        self._folder_cache: dict[str, str] = {}
        self._service: Any | None = None

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
            )
            self._service = build("drive", "v3", credentials=creds)
        except Exception:
            log.exception("Failed to initialise Google Drive service")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return *True* if the Drive service was initialised successfully."""
        return self._service is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drive_params(self) -> dict[str, Any]:
        """Return common parameters needed for shared-drive support."""
        params: dict[str, Any] = {"supportsAllDrives": True}
        if self._drive_id:
            params["driveId"] = self._drive_id
            params["corpora"] = "drive"
            params["includeItemsFromAllDrives"] = True
        return params

    def _parent_id(self) -> str:
        """Return the effective root folder id."""
        return self._root_folder_id or self._drive_id or "root"

    @staticmethod
    def _to_drive_file(meta: dict[str, Any]) -> DriveFile:
        parents = meta.get("parents", [])
        return DriveFile(
            id=meta["id"],
            name=meta.get("name", ""),
            mime_type=meta.get("mimeType", ""),
            web_view_link=meta.get("webViewLink", ""),
            size=int(meta.get("size", 0)),
            parent_id=parents[0] if parents else "",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def upload(
        self,
        file_path: str | Path,
        folder_id: str | None = None,
        name: str | None = None,
    ) -> DriveFile:
        """Upload a local file to Google Drive and return its metadata."""
        import mimetypes as _mt

        from googleapiclient.http import MediaFileUpload

        file_path = Path(file_path)
        upload_name = name or file_path.name
        mime, _ = _mt.guess_type(str(file_path))
        mime = mime or "application/octet-stream"

        body: dict[str, Any] = {
            "name": upload_name,
            "parents": [folder_id or self._parent_id()],
        }
        media = MediaFileUpload(str(file_path), mimetype=mime, resumable=True)

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                self._service.files()
                .create(
                    body=body,
                    media_body=media,
                    fields="id,name,mimeType,webViewLink,size,parents",
                    supportsAllDrives=True,
                )
                .execute
            ),
        )
        return self._to_drive_file(result)

    async def download(self, file_id: str, dest_path: str | Path) -> Path:
        """Download a Drive file to *dest_path* and return the path."""
        from googleapiclient.http import MediaIoBaseDownload

        dest_path = Path(dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        def _do_download() -> None:
            request = self._service.files().get_media(
                fileId=file_id, supportsAllDrives=True
            )
            with open(dest_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _do_download)
        return dest_path

    async def get_or_create_folder(
        self, path: str, parent_id: str | None = None
    ) -> str:
        """Ensure *path* (e.g. ``"a/b/c"``) exists and return the leaf folder id.

        Intermediate folders are created as needed.  Results are cached so
        repeated calls for the same path do not hit the API.
        """
        cache_key = f"{parent_id or ''}:{path}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        current_parent = parent_id or self._parent_id()
        parts = [p for p in path.split("/") if p]

        for part in parts:
            part_key = f"{current_parent}:{part}"
            if part_key in self._folder_cache:
                current_parent = self._folder_cache[part_key]
                continue

            # Search for existing folder
            q = (
                f"name='{part}' and mimeType='{self.FOLDER_MIME}' "
                f"and '{current_parent}' in parents and trashed=false"
            )
            params: dict[str, Any] = {
                "q": q,
                "fields": "files(id,name)",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }

            loop = asyncio.get_running_loop()
            resp = await loop.run_in_executor(
                None,
                partial(self._service.files().list(**params).execute),
            )
            files = resp.get("files", [])

            if files:
                folder_id = files[0]["id"]
            else:
                # Create new folder
                body: dict[str, Any] = {
                    "name": part,
                    "mimeType": self.FOLDER_MIME,
                    "parents": [current_parent],
                }
                created = await loop.run_in_executor(
                    None,
                    partial(
                        self._service.files()
                        .create(
                            body=body,
                            fields="id",
                            supportsAllDrives=True,
                        )
                        .execute
                    ),
                )
                folder_id = created["id"]

            self._folder_cache[part_key] = folder_id
            current_parent = folder_id

        self._folder_cache[cache_key] = current_parent
        return current_parent

    async def share(self, file_id: str, anyone_with_link: bool = True) -> str:
        """Share a file and return its ``webViewLink``."""
        loop = asyncio.get_running_loop()

        if anyone_with_link:
            perm = {"type": "anyone", "role": "reader"}
            await loop.run_in_executor(
                None,
                partial(
                    self._service.permissions()
                    .create(
                        fileId=file_id,
                        body=perm,
                        supportsAllDrives=True,
                    )
                    .execute
                ),
            )

        meta = await loop.run_in_executor(
            None,
            partial(
                self._service.files()
                .get(
                    fileId=file_id,
                    fields="webViewLink",
                    supportsAllDrives=True,
                )
                .execute
            ),
        )
        return meta.get("webViewLink", "")

    async def delete(self, file_id: str) -> None:
        """Trash a file (soft-delete)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._service.files()
                .update(
                    fileId=file_id,
                    body={"trashed": True},
                    supportsAllDrives=True,
                )
                .execute
            ),
        )

    async def get_metadata(self, file_id: str) -> DriveFile:
        """Return metadata for a single file."""
        loop = asyncio.get_running_loop()
        meta = await loop.run_in_executor(
            None,
            partial(
                self._service.files()
                .get(
                    fileId=file_id,
                    fields="id,name,mimeType,webViewLink,size,parents",
                    supportsAllDrives=True,
                )
                .execute
            ),
        )
        return self._to_drive_file(meta)

    async def search(self, query: str, folder_id: str | None = None) -> list[DriveFile]:
        """Run a Drive query and return matching files."""
        q = query
        if folder_id:
            q = f"'{folder_id}' in parents and ({query})"

        params: dict[str, Any] = {
            "q": q,
            "fields": "files(id,name,mimeType,webViewLink,size,parents)",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "pageSize": 100,
        }
        if self._drive_id:
            params["driveId"] = self._drive_id
            params["corpora"] = "drive"

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            partial(self._service.files().list(**params).execute),
        )
        return [self._to_drive_file(f) for f in resp.get("files", [])]

    async def list_shared_drives(self) -> list[dict[str, Any]]:
        """Return a list of shared drives accessible by the service account."""
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            partial(
                self._service.drives()
                .list(fields="drives(id,name)", pageSize=100)
                .execute
            ),
        )
        return resp.get("drives", [])

    async def list_folders(
        self, drive_id: str = "", parent_id: str = ""
    ) -> list[dict[str, Any]]:
        """List folders under *parent_id* (or the drive root).

        Useful for building a folder-browser UI in the settings page.
        """
        parent = parent_id or drive_id or "root"
        q = f"'{parent}' in parents and mimeType='{self.FOLDER_MIME}' and trashed=false"
        params: dict[str, Any] = {
            "q": q,
            "fields": "files(id,name)",
            "supportsAllDrives": True,
            "includeItemsFromAllDrives": True,
            "pageSize": 200,
        }
        if drive_id:
            params["driveId"] = drive_id
            params["corpora"] = "drive"

        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(
            None,
            partial(self._service.files().list(**params).execute),
        )
        return resp.get("files", [])
