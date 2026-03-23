"""
Maestro Asset Manager.

Manages asset registration, metadata, and embedding lifecycle.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

from maestro.store import Store

# ---------------------------------------------------------------------------
# Type detection
# ---------------------------------------------------------------------------

_EXT_TYPE_MAP: dict[str, str] = {
    # Video
    ".mp4": "video",
    ".mov": "video",
    ".avi": "video",
    ".mkv": "video",
    ".webm": "video",
    # Image
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".svg": "image",
    # Document
    ".pdf": "document",
    ".md": "document",
    ".txt": "document",
    ".docx": "document",
    ".csv": "document",
}


def detect_asset_type(path: str) -> str:
    """Auto-detect asset type from file extension. Returns 'unknown' if unrecognized."""
    ext = Path(path).suffix.lower()
    return _EXT_TYPE_MAP.get(ext, "unknown")


# ---------------------------------------------------------------------------
# AssetManager
# ---------------------------------------------------------------------------


class AssetManager:
    """Manages asset registration, metadata, and usage tracking."""

    def __init__(self, store: Store, assets_dir: Path) -> None:
        self._store = store
        self._assets_dir = assets_dir

    async def register_asset(
        self,
        path: str,
        title: str,
        asset_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Register an asset file.

        Auto-detects type from extension if not provided.
        Returns the generated asset_id.
        """
        if asset_type is None:
            asset_type = detect_asset_type(path)

        asset_id = uuid.uuid4().hex[:12]

        asset = {
            "id": asset_id,
            "type": asset_type,
            "path": path,
            "title": title,
            "description": description,
            "tags": tags or [],
        }

        await self._store.create_asset(asset)
        return asset_id

    async def get_asset(self, asset_id: str) -> Optional[dict[str, Any]]:
        """Get asset by ID."""
        return await self._store.get_asset(asset_id)

    async def list_assets(
        self,
        asset_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        unused_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List assets with optional filters.

        If unused_only is True, only returns assets with no task_assets references.
        (Currently unused_only is a placeholder — always returns all matching.)
        """
        return await self._store.list_assets(
            asset_type=asset_type,
            tags_contain=tags,
        )

    async def search_assets(
        self,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Vector similarity search (placeholder).

        Returns empty list until sqlite-vec is set up.
        """
        return []

    async def record_usage(
        self,
        asset_id: str,
        task_id: str,
        platform: str,
    ) -> None:
        """Record that an asset was used in a task on a platform."""
        action_id = uuid.uuid4().hex[:12]
        await self._store.record_action(
            {
                "id": action_id,
                "task_id": task_id,
                "workspace": "",  # Filled by caller if needed
                "action_type": "asset_usage",
                "platform": platform,
                "asset_ids": [asset_id],
            }
        )
