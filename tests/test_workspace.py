"""Tests for WorkspaceManager."""

from __future__ import annotations

import json
import pathlib

import pytest

from maestro.workspace import WorkspaceManager


@pytest.fixture
def wm(tmp_path: pathlib.Path) -> WorkspaceManager:
    """Return a WorkspaceManager rooted in a temp directory."""
    return WorkspaceManager(tmp_path)


class TestCreateWorkspace:
    """test_create_workspace: creates directory structure."""

    def test_creates_all_directories(self, wm: WorkspaceManager) -> None:
        ws_path = wm.create_workspace("test-agent")

        assert ws_path.is_dir()
        assert (ws_path / "knowledge").is_dir()
        assert (ws_path / "skills").is_dir()
        assert (ws_path / "sessions" / "pending").is_dir()
        assert (ws_path / ".claude").is_dir()

    def test_creates_claude_md(self, wm: WorkspaceManager) -> None:
        ws_path = wm.create_workspace("my-agent")
        claude_md = (ws_path / "CLAUDE.md").read_text()

        assert "# my-agent Agent" in claude_md
        assert "maestro-store" in claude_md

    def test_creates_mcp_json(self, wm: WorkspaceManager) -> None:
        ws_path = wm.create_workspace("my-agent")
        mcp = json.loads((ws_path / ".claude" / "mcp.json").read_text())

        assert "mcpServers" in mcp
        assert "maestro-store" in mcp["mcpServers"]
        assert mcp["mcpServers"]["maestro-store"]["command"] == "python"

    def test_creates_settings_json(self, wm: WorkspaceManager) -> None:
        ws_path = wm.create_workspace("my-agent")
        settings = json.loads((ws_path / ".claude" / "settings.json").read_text())

        assert "permissions" in settings

    def test_custom_claude_md(self, wm: WorkspaceManager) -> None:
        ws_path = wm.create_workspace("custom", claude_md="# Custom Agent\n")
        claude_md = (ws_path / "CLAUDE.md").read_text()

        assert claude_md == "# Custom Agent\n"

    def test_custom_mcp_json(self, wm: WorkspaceManager) -> None:
        custom_mcp = {"mcpServers": {"my-tool": {"command": "node"}}}
        ws_path = wm.create_workspace("custom", mcp_json=custom_mcp)
        mcp = json.loads((ws_path / ".claude" / "mcp.json").read_text())

        assert "my-tool" in mcp["mcpServers"]

    def test_raises_on_existing_workspace(self, wm: WorkspaceManager) -> None:
        wm.create_workspace("dupe")
        with pytest.raises(FileExistsError):
            wm.create_workspace("dupe")


class TestListWorkspaces:
    """test_list_workspaces: lists existing workspaces."""

    def test_empty_when_no_workspaces(self, wm: WorkspaceManager) -> None:
        assert wm.list_workspaces() == []

    def test_lists_created_workspaces(self, wm: WorkspaceManager) -> None:
        wm.create_workspace("alpha")
        wm.create_workspace("beta")

        names = wm.list_workspaces()
        assert names == ["alpha", "beta"]

    def test_excludes_base_dir(self, wm: WorkspaceManager) -> None:
        wm.ensure_base_knowledge()
        wm.create_workspace("agent-1")

        names = wm.list_workspaces()
        assert "_base" not in names
        assert "agent-1" in names

    def test_excludes_hidden_dirs(self, wm: WorkspaceManager) -> None:
        (wm.workspaces_dir / ".hidden").mkdir(parents=True)
        wm.create_workspace("visible")

        names = wm.list_workspaces()
        assert ".hidden" not in names
        assert "visible" in names


class TestValidateWorkspace:
    """test_validate_workspace: warns on missing CLAUDE.md."""

    def test_valid_workspace_no_warnings(self, wm: WorkspaceManager) -> None:
        wm.create_workspace("good")
        warnings = wm.validate_workspace("good")
        assert warnings == []

    def test_missing_claude_md(self, wm: WorkspaceManager) -> None:
        wm.create_workspace("broken")
        (wm.get_workspace_path("broken") / "CLAUDE.md").unlink()

        warnings = wm.validate_workspace("broken")
        assert any("CLAUDE.md" in w for w in warnings)

    def test_missing_knowledge_dir(self, wm: WorkspaceManager) -> None:
        wm.create_workspace("broken")
        import shutil
        shutil.rmtree(wm.get_workspace_path("broken") / "knowledge")

        warnings = wm.validate_workspace("broken")
        assert any("knowledge" in w for w in warnings)

    def test_missing_mcp_json(self, wm: WorkspaceManager) -> None:
        wm.create_workspace("broken")
        (wm.get_workspace_path("broken") / ".claude" / "mcp.json").unlink()

        warnings = wm.validate_workspace("broken")
        assert any("mcp.json" in w for w in warnings)

    def test_nonexistent_workspace(self, wm: WorkspaceManager) -> None:
        warnings = wm.validate_workspace("nope")
        assert len(warnings) == 1
        assert "does not exist" in warnings[0]


class TestWorkspaceExists:
    """test_workspace_exists: returns True/False correctly."""

    def test_exists_after_creation(self, wm: WorkspaceManager) -> None:
        assert not wm.workspace_exists("agent")
        wm.create_workspace("agent")
        assert wm.workspace_exists("agent")

    def test_not_exists_for_missing(self, wm: WorkspaceManager) -> None:
        assert not wm.workspace_exists("ghost")


class TestEnsureBaseKnowledge:
    """Tests for the _base/ shared knowledge setup."""

    def test_creates_base_knowledge(self, wm: WorkspaceManager) -> None:
        base_dir = wm.ensure_base_knowledge()

        assert base_dir.is_dir()
        assert (base_dir / "product.md").exists()
        assert (base_dir / "brand.md").exists()

    def test_idempotent(self, wm: WorkspaceManager) -> None:
        wm.ensure_base_knowledge()
        # Write custom content
        product = wm.workspaces_dir / "_base" / "knowledge" / "product.md"
        product.write_text("Custom content")

        # Call again - should not overwrite
        wm.ensure_base_knowledge()
        assert product.read_text() == "Custom content"
