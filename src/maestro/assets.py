"""Asset Manager for Maestro -- registration, search pipeline, auto-extraction."""

from __future__ import annotations

import json
import mimetypes
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Type detection (kept for backward compatibility)
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
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dot_path(data: dict, path: str) -> Any:
    """Extract value from nested dict using dot-path notation.

    ``"a.b.c"`` -> ``data["a"]["b"]["c"]``
    """
    keys = path.split(".")
    current: Any = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


# ---------------------------------------------------------------------------
# AssetManager
# ---------------------------------------------------------------------------


class AssetManager:
    """Manages asset registration, search, and lifecycle."""

    def __init__(self, store: Any, embedding: Any, config: Any, base_path: Path) -> None:
        self._store = store
        self._embedding = embedding  # EmbeddingClient or None
        self._config = config        # MaestroConfig (has .assets: AssetsConfig)
        self._base_path = base_path

    async def register_asset(
        self,
        *,
        asset_type: str,
        title: str,
        content_json: Optional[dict] = None,
        file_path: Optional[str] = None,
        tags: Optional[list[str]] = None,
        description: Optional[str] = None,
        ttl_days: Optional[int] = None,
        workspace: str = "_shared",
        created_by: str = "human",
        task_id: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> dict:
        """Register a new asset. Returns the created asset dict."""
        asset_id = secrets.token_hex(6)

        # Default TTL from config
        if ttl_days is None and hasattr(self._config, "assets"):
            ttl_days = self._config.assets.default_ttl.get(asset_type)

        # Calculate expires_at
        expires_at: Optional[str] = None
        if ttl_days is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()

        # Detect media type for file-based assets
        if not media_type and file_path:
            media_type = mimetypes.guess_type(file_path)[0]

        # Copy binary file to managed location
        managed_path: Optional[str] = None
        file_size: Optional[int] = None
        if file_path:
            src = Path(file_path)
            if src.exists():
                dest_dir = self._base_path / "assets" / workspace / datetime.now().strftime("%Y-%m")
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest = dest_dir / f"{asset_id}_{src.name}"
                shutil.copy2(src, dest)
                managed_path = str(dest.relative_to(self._base_path))
                file_size = src.stat().st_size

        asset_data: dict[str, Any] = {
            "id": asset_id,
            "task_id": task_id,
            "workspace": workspace,
            "created_by": created_by,
            "asset_type": asset_type,
            "media_type": media_type,
            "title": title,
            "description": description,
            "tags": tags,
            "content_json": content_json,
            "file_path": managed_path,
            "file_size": file_size,
            "ttl_days": ttl_days,
            "expires_at": expires_at,
        }

        await self._store.create_asset(asset_data)

        # Embed asynchronously (best-effort)
        if self._embedding:
            try:
                embed_input = dict(asset_data)
                # Pass raw content for embedding, not JSON string
                if content_json:
                    embed_input["content_json"] = content_json
                embedding = await self._embedding.embed_asset(embed_input)
                if any(v != 0.0 for v in embedding):
                    await self._store.store_embedding(asset_id, embedding)
            except Exception:
                pass  # Deferred embedding -- daemon will retry

        # Record usage
        if task_id:
            await self._store.record_asset_usage(asset_id, task_id, "created")

        return await self._store.get_asset(asset_id)

    async def search(
        self,
        *,
        query: str,
        workspace: Optional[str] = None,
        asset_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        since: Optional[str] = None,
        limit: int = 10,
        include_content: bool = True,
    ) -> list[dict]:
        """Search assets: structured filter -> vector similarity."""
        # Phase 1: structured filter
        candidates = await self._store.list_assets_filtered(
            workspace=workspace,
            asset_type=asset_type,
            tags=tags,
            limit=500,
        )
        if since:
            candidates = [a for a in candidates if a.get("created_at", "") >= since]

        if not candidates:
            return []

        candidate_ids = [a["id"] for a in candidates]

        # Phase 2: vector similarity (if embedding client available)
        if self._embedding:
            try:
                query_vec = await self._embedding.embed_query(query)
                vec_results = await self._store.vec_search(
                    query_vec,
                    candidate_ids=candidate_ids,
                    limit=limit,
                )
                ranked_ids = [r["asset_id"] for r in vec_results]
                id_to_asset = {a["id"]: a for a in candidates}
                results = [id_to_asset[aid] for aid in ranked_ids if aid in id_to_asset]
            except Exception:
                results = candidates[:limit]
        else:
            results = candidates[:limit]

        # Phase 3: clean response
        for r in results:
            if not include_content:
                r.pop("content_json", None)
            # Never expose embedding internals
            r.pop("embedded_at", None)
            r.pop("embedding_model", None)

        return results

    async def auto_extract(
        self,
        *,
        task_id: str,
        workspace: str,
        result_json: dict,
        rules: dict,
    ) -> list[dict]:
        """Extract assets from task result_json using config rules."""
        # Check for duplicates
        existing = await self._store.list_assets_filtered(
            task_id=task_id,
            asset_type=rules["asset_type"],
        )
        if existing:
            return []

        assets: list[dict] = []
        items: list = [result_json]
        if "iterate" in rules:
            items = _dot_path(result_json, rules["iterate"]) or []

        for item in items:
            title_val = (
                _dot_path(item, rules["title_field"]) if isinstance(item, dict) else str(item)
            )
            if not title_val:
                continue
            title = str(title_val)[:50]

            extracted_tags: list[str] = []
            for tag_path in rules.get("tags_from", []):
                val = _dot_path(item, tag_path) if isinstance(item, dict) else None
                if val:
                    extracted_tags.append(str(val)[:50])

            asset = await self.register_asset(
                asset_type=rules["asset_type"],
                title=title,
                content_json=item if isinstance(item, dict) else {"value": item},
                tags=extracted_tags or None,
                workspace=workspace,
                created_by="daemon",
                task_id=task_id,
            )
            assets.append(asset)

        return assets
