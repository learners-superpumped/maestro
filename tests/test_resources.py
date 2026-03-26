"""Tests for maestro.resources — shared resource lock management."""

from __future__ import annotations

import pytest

from maestro.config import MaestroConfig, ProjectConfig, ResourceProfile
from maestro.resources import ResourceManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(
    resources: dict[str, dict[str, ResourceProfile]] | None = None,
) -> MaestroConfig:
    """Create a minimal MaestroConfig with optional resource declarations."""
    return MaestroConfig(
        project=ProjectConfig(name="test"),
        resources=resources or {},
    )


def _config_with_chrome() -> MaestroConfig:
    return _config(
        resources={
            "chrome-profiles": {
                "threads": ResourceProfile(
                    max_concurrent=1, path="./chrome-profiles/threads"
                ),
                "x": ResourceProfile(max_concurrent=1, path="./chrome-profiles/x"),
            },
        }
    )


# ---------------------------------------------------------------------------
# Acquire and release
# ---------------------------------------------------------------------------


class TestAcquireAndRelease:
    """Test basic acquire/release semantics."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        assert await rm.acquire("chrome-profiles/threads") is True
        assert rm.is_available("chrome-profiles/threads") is False

        await rm.release("chrome-profiles/threads")
        assert rm.is_available("chrome-profiles/threads") is True

    @pytest.mark.asyncio
    async def test_double_acquire_returns_false(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        assert await rm.acquire("chrome-profiles/threads") is True
        assert await rm.acquire("chrome-profiles/threads") is False

    @pytest.mark.asyncio
    async def test_acquire_different_resources_independent(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        assert await rm.acquire("chrome-profiles/threads") is True
        assert await rm.acquire("chrome-profiles/x") is True
        assert rm.is_available("chrome-profiles/threads") is False
        assert rm.is_available("chrome-profiles/x") is False


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    """Test availability checking."""

    def test_is_available_initially(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        assert rm.is_available("chrome-profiles/threads") is True

    def test_unknown_resource_is_available(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        # Unknown resources are considered available
        assert rm.is_available("nonexistent/resource") is True

    @pytest.mark.asyncio
    async def test_all_available(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        assert (
            rm.all_available(["chrome-profiles/threads", "chrome-profiles/x"]) is True
        )

        await rm.acquire("chrome-profiles/threads")
        assert (
            rm.all_available(["chrome-profiles/threads", "chrome-profiles/x"]) is False
        )
        assert rm.all_available(["chrome-profiles/x"]) is True


# ---------------------------------------------------------------------------
# Release unknown resource
# ---------------------------------------------------------------------------


class TestReleaseUnknown:
    """Test releasing resources that are not tracked."""

    @pytest.mark.asyncio
    async def test_release_unknown_resource_is_noop(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        # Should not raise, and all known resources remain available
        await rm.release("nonexistent/resource")
        assert rm.is_available("chrome-profiles/threads") is True

    @pytest.mark.asyncio
    async def test_release_without_acquire_is_noop(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)

        # Resource exists but was never acquired — should not raise
        await rm.release("chrome-profiles/threads")
        assert rm.is_available("chrome-profiles/threads") is True


# ---------------------------------------------------------------------------
# Workspace resource detection
# ---------------------------------------------------------------------------


class TestGetWorkspaceResources:
    """Test workspace-to-resource mapping (now always returns empty list)."""

    def test_always_returns_empty(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)
        assert rm.get_workspace_resources("sns-threads") == []

    def test_any_workspace_returns_empty(self) -> None:
        cfg = _config_with_chrome()
        rm = ResourceManager(cfg)
        assert rm.get_workspace_resources("any") == []
        assert rm.get_workspace_resources("") == []


# ---------------------------------------------------------------------------
# Empty config
# ---------------------------------------------------------------------------


class TestEmptyConfig:
    """Test behavior with no declared resources."""

    def test_no_resources_all_available(self) -> None:
        cfg = _config()
        rm = ResourceManager(cfg)

        assert rm.is_available("anything") is True

    @pytest.mark.asyncio
    async def test_acquire_undeclared_resource(self) -> None:
        cfg = _config()
        rm = ResourceManager(cfg)

        # Acquiring an undeclared resource creates it on the fly
        assert await rm.acquire("dynamic/resource") is True
        assert rm.is_available("dynamic/resource") is False
