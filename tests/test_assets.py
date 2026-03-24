"""Tests for maestro.assets -- Asset Manager."""

from __future__ import annotations

import pathlib

import pytest

from maestro.assets import AssetManager, detect_asset_type, _dot_path
from maestro.config import AssetsConfig
from maestro.models import Task
from maestro.store import Store
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def asset_manager(tmp_path: pathlib.Path) -> AssetManager:
    db_file = str(tmp_path / "test.db")
    store = Store(db_file)
    await store.init_db()
    config = MagicMock()
    config.assets = AssetsConfig()
    return AssetManager(store, None, config, tmp_path)


async def _ensure_task(store: Store, task_id: str) -> None:
    """Create a minimal task row to satisfy FK constraints."""
    task = Task(
        id=task_id,
        type="shell",
        workspace="/ws/test",
        title="test task",
        instruction="noop",
    )
    await store.create_task(task)


# ---------------------------------------------------------------------------
# _dot_path
# ---------------------------------------------------------------------------


def test_dot_path_simple() -> None:
    assert _dot_path({"a": 1}, "a") == 1


def test_dot_path_nested() -> None:
    assert _dot_path({"a": {"b": {"c": 42}}}, "a.b.c") == 42


def test_dot_path_missing() -> None:
    assert _dot_path({"a": 1}, "b") is None


def test_dot_path_partial_missing() -> None:
    assert _dot_path({"a": {"b": 1}}, "a.c") is None


def test_dot_path_non_dict_intermediate() -> None:
    assert _dot_path({"a": "string"}, "a.b") is None


# ---------------------------------------------------------------------------
# Type detection (kept from original)
# ---------------------------------------------------------------------------


def test_auto_detect_type_video() -> None:
    assert detect_asset_type("/path/to/clip.mp4") == "video"
    assert detect_asset_type("video.mov") == "video"
    assert detect_asset_type("video.avi") == "video"


def test_auto_detect_type_image() -> None:
    assert detect_asset_type("/assets/photo.png") == "image"
    assert detect_asset_type("banner.jpg") == "image"
    assert detect_asset_type("icon.gif") == "image"
    assert detect_asset_type("logo.webp") == "image"


def test_auto_detect_type_document() -> None:
    assert detect_asset_type("report.pdf") == "document"
    assert detect_asset_type("README.md") == "document"
    assert detect_asset_type("notes.txt") == "document"


def test_auto_detect_type_unknown() -> None:
    assert detect_asset_type("archive.zip") == "unknown"
    assert detect_asset_type("noext") == "unknown"


# ---------------------------------------------------------------------------
# AssetManager.register_asset
# ---------------------------------------------------------------------------


async def test_register_asset_basic(asset_manager: AssetManager) -> None:
    asset = await asset_manager.register_asset(
        asset_type="post",
        title="Test Post",
        content_json={"body": "hello"},
        tags=["promo", "test"],
        description="A test asset",
        workspace="sns-threads",
    )

    assert asset is not None
    assert len(asset["id"]) == 12
    assert asset["title"] == "Test Post"
    assert asset["asset_type"] == "post"
    assert asset["workspace"] == "sns-threads"
    assert asset["description"] == "A test asset"
    assert asset["tags"] == ["promo", "test"]
    assert asset["content_json"] == {"body": "hello"}
    assert asset["created_by"] == "human"


async def test_register_asset_default_ttl(asset_manager: AssetManager) -> None:
    """Default TTL from config is applied (research -> 7 days)."""
    asset = await asset_manager.register_asset(
        asset_type="research",
        title="Research Result",
    )

    assert asset["ttl_days"] == 7
    assert asset["expires_at"] is not None


async def test_register_asset_no_ttl_for_post(asset_manager: AssetManager) -> None:
    """Posts have None TTL by default -> no expiration."""
    asset = await asset_manager.register_asset(
        asset_type="post",
        title="Evergreen Post",
    )

    assert asset["ttl_days"] is None
    assert asset["expires_at"] is None


async def test_register_asset_with_file(
    asset_manager: AssetManager, tmp_path: pathlib.Path
) -> None:
    # Create a temp file to register
    src_file = tmp_path / "source" / "photo.png"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    asset = await asset_manager.register_asset(
        asset_type="image",
        title="Photo",
        file_path=str(src_file),
    )

    assert asset["file_path"] is not None
    assert asset["file_size"] == 108
    assert asset["media_type"] == "image/png"
    # Verify the file was actually copied
    managed = tmp_path / asset["file_path"]
    assert managed.exists()


async def test_register_asset_records_usage(asset_manager: AssetManager) -> None:
    """When task_id is provided, usage is recorded."""
    await _ensure_task(asset_manager._store, "task-123")
    asset = await asset_manager.register_asset(
        asset_type="post",
        title="Task Asset",
        task_id="task-123",
    )
    # No assertion on usage table directly -- just ensure no error
    assert asset["task_id"] == "task-123"


# ---------------------------------------------------------------------------
# AssetManager.search
# ---------------------------------------------------------------------------


async def test_search_returns_results(asset_manager: AssetManager) -> None:
    """Without embedding, search falls back to filter-only."""
    await asset_manager.register_asset(
        asset_type="post",
        title="Alpha Post",
        workspace="ws1",
    )
    await asset_manager.register_asset(
        asset_type="image",
        title="Beta Image",
        workspace="ws1",
    )

    results = await asset_manager.search(query="anything", workspace="ws1")
    assert len(results) == 2


async def test_search_filter_by_type(asset_manager: AssetManager) -> None:
    await asset_manager.register_asset(
        asset_type="post",
        title="Post 1",
    )
    await asset_manager.register_asset(
        asset_type="image",
        title="Image 1",
    )

    results = await asset_manager.search(query="test", asset_type="post")
    assert len(results) == 1
    assert results[0]["title"] == "Post 1"


async def test_search_exclude_content(asset_manager: AssetManager) -> None:
    await asset_manager.register_asset(
        asset_type="post",
        title="Content Post",
        content_json={"body": "secret"},
    )

    results = await asset_manager.search(query="test", include_content=False)
    assert len(results) == 1
    assert "content_json" not in results[0]


async def test_search_empty_result(asset_manager: AssetManager) -> None:
    results = await asset_manager.search(query="nothing", asset_type="nonexistent")
    assert results == []


async def test_search_respects_limit(asset_manager: AssetManager) -> None:
    for i in range(5):
        await asset_manager.register_asset(
            asset_type="post",
            title=f"Post {i}",
        )

    results = await asset_manager.search(query="test", limit=3)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# AssetManager.auto_extract
# ---------------------------------------------------------------------------


async def test_auto_extract_with_iterate(asset_manager: AssetManager) -> None:
    await _ensure_task(asset_manager._store, "task-extract")
    result_json = {
        "topics": [
            {"name": "AI Trends", "category": "tech"},
            {"name": "Python Tips", "category": "dev"},
        ]
    }
    rules = {
        "asset_type": "research",
        "iterate": "topics",
        "title_field": "name",
        "tags_from": ["category"],
    }

    assets = await asset_manager.auto_extract(
        task_id="task-extract",
        workspace="ws1",
        result_json=result_json,
        rules=rules,
    )

    assert len(assets) == 2
    assert assets[0]["title"] == "AI Trends"
    assert assets[0]["tags"] == ["tech"]
    assert assets[1]["title"] == "Python Tips"
    assert assets[1]["tags"] == ["dev"]
    assert all(a["created_by"] == "daemon" for a in assets)
    assert all(a["asset_type"] == "research" for a in assets)


async def test_auto_extract_skips_duplicates(asset_manager: AssetManager) -> None:
    await _ensure_task(asset_manager._store, "task-dup")
    result_json = {
        "topics": [{"name": "Topic A"}]
    }
    rules = {
        "asset_type": "research",
        "iterate": "topics",
        "title_field": "name",
    }

    # First extraction
    first = await asset_manager.auto_extract(
        task_id="task-dup",
        workspace="ws1",
        result_json=result_json,
        rules=rules,
    )
    assert len(first) == 1

    # Second extraction with same task_id + asset_type -> skip
    second = await asset_manager.auto_extract(
        task_id="task-dup",
        workspace="ws1",
        result_json=result_json,
        rules=rules,
    )
    assert second == []


async def test_auto_extract_without_iterate(asset_manager: AssetManager) -> None:
    """When no 'iterate' key, treat result_json itself as a single item."""
    await _ensure_task(asset_manager._store, "task-single")
    result_json = {"name": "Single Item", "category": "misc"}
    rules = {
        "asset_type": "post",
        "title_field": "name",
    }

    assets = await asset_manager.auto_extract(
        task_id="task-single",
        workspace="ws1",
        result_json=result_json,
        rules=rules,
    )

    assert len(assets) == 1
    assert assets[0]["title"] == "Single Item"
