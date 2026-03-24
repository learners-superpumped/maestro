"""Tests for maestro.assets — Asset Manager."""

from __future__ import annotations

import pathlib

import pytest

from maestro.assets import AssetManager, detect_asset_type
from maestro.models import Task
from maestro.store import Store


# ---------------------------------------------------------------------------
# Type detection
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
# AssetManager
# ---------------------------------------------------------------------------


async def test_register_asset(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    store = Store(db_path)
    mgr = AssetManager(store, tmp_path / "assets")

    asset_id = await mgr.register_asset(
        path="/assets/hero.png",
        title="Hero Image",
        tags=["promo", "hero"],
        description="Main hero image for campaign",
    )

    assert asset_id is not None
    assert len(asset_id) == 12

    fetched = await mgr.get_asset(asset_id)
    assert fetched is not None
    assert fetched["title"] == "Hero Image"
    assert fetched["asset_type"] == "image"  # auto-detected from .png
    assert fetched["tags"] == ["promo", "hero"]
    assert fetched["description"] == "Main hero image for campaign"


async def test_register_asset_explicit_type(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    store = Store(db_path)
    mgr = AssetManager(store, tmp_path / "assets")

    asset_id = await mgr.register_asset(
        path="/assets/data.bin",
        title="Binary Data",
        asset_type="custom",
    )

    fetched = await mgr.get_asset(asset_id)
    assert fetched is not None
    assert fetched["asset_type"] == "custom"


async def test_list_assets(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    store = Store(db_path)
    mgr = AssetManager(store, tmp_path / "assets")

    await mgr.register_asset(path="/a/img.png", title="Image")
    await mgr.register_asset(path="/a/vid.mp4", title="Video")
    await mgr.register_asset(path="/a/doc.pdf", title="Document")

    images = await mgr.list_assets(asset_type="image")
    assert len(images) == 1
    assert images[0]["title"] == "Image"

    all_assets = await mgr.list_assets()
    assert len(all_assets) == 3


async def test_list_assets_by_tags(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    store = Store(db_path)
    mgr = AssetManager(store, tmp_path / "assets")

    await mgr.register_asset(path="/a/a.png", title="Summer", tags=["summer", "promo"])
    await mgr.register_asset(path="/a/b.png", title="Winter", tags=["winter", "promo"])
    await mgr.register_asset(path="/a/c.png", title="Internal", tags=["internal"])

    promo = await mgr.list_assets(tags=["promo"])
    assert len(promo) == 2

    internal = await mgr.list_assets(tags=["internal"])
    assert len(internal) == 1


async def test_record_usage(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    store = Store(db_path)
    mgr = AssetManager(store, tmp_path / "assets")

    # Need a task for FK constraint on action_history
    task = Task(
        id="task-usage",
        type="shell",
        workspace="/ws/test",
        title="Usage test",
        instruction="test",
    )
    await store.create_task(task)

    asset_id = await mgr.register_asset(path="/a/img.png", title="Image")

    await mgr.record_usage(asset_id=asset_id, task_id="task-usage", platform="twitter")

    history = await store.search_history()
    assert len(history) == 1
    assert history[0]["platform"] == "twitter"
    assert history[0]["action_type"] == "asset_usage"
    assert asset_id in history[0]["asset_ids"]


async def test_search_assets_placeholder(db_path: pathlib.Path, tmp_path: pathlib.Path) -> None:
    store = Store(db_path)
    mgr = AssetManager(store, tmp_path / "assets")

    result = await mgr.search_assets(query_embedding=[0.0] * 768)
    assert result == []
