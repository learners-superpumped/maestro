"""
Workspace Manager for Maestro.

Manages workspace directories for agents. Each workspace is a directory
containing CLAUDE.md, knowledge/, skills/, sessions/, and .claude/ config.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_DEFAULT_CLAUDE_MD = textwrap.dedent("""\
    # {name} Agent

    ## Role
    Describe this agent's role and responsibilities.

    ## Knowledge
    Read these files for context:
    - ../_base/knowledge/product.md
    - ./knowledge/

    ## Available Tools
    - maestro-store: Task management, history search, approval workflow

    ## Workflow
    1. Analyze the instruction
    2. Execute the task
    3. Submit results via maestro-store tools

    ## Rules
    - Follow the instruction precisely
    - Report results via maestro_task_submit_result
    - Request approval via maestro_approval_submit for external actions
""")

_DEFAULT_MCP_JSON = {
    "mcpServers": {
        "maestro-store": {
            "command": "python",
            "args": ["-m", "maestro.mcp_store"],
            "env": {
                "MAESTRO_DAEMON_PORT": "${MAESTRO_DAEMON_PORT}",
            },
        },
    },
}

_DEFAULT_SETTINGS_JSON = {
    "permissions": {
        "allow": [
            "Bash(*)",
            "Read(*)",
            "Write(*)",
        ],
        "deny": [],
    },
}


# ---------------------------------------------------------------------------
# WorkspaceManager
# ---------------------------------------------------------------------------

class WorkspaceManager:
    """Manages workspace directories for Maestro agents."""

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path
        self._workspaces_dir = base_path / "workspaces"

    @property
    def workspaces_dir(self) -> Path:
        return self._workspaces_dir

    def list_workspaces(self) -> list[str]:
        """List workspace names (directory names under workspaces/).

        Excludes hidden directories and the _base shared workspace.
        """
        if not self._workspaces_dir.exists():
            return []
        return sorted(
            d.name
            for d in self._workspaces_dir.iterdir()
            if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
        )

    def workspace_exists(self, name: str) -> bool:
        """Check if workspace directory exists."""
        return (self._workspaces_dir / name).is_dir()

    def get_workspace_path(self, name: str) -> Path:
        """Get absolute path to workspace directory."""
        return (self._workspaces_dir / name).resolve()

    def validate_workspace(self, name: str) -> list[str]:
        """Validate workspace has required files. Return list of warnings."""
        warnings: list[str] = []
        ws_path = self._workspaces_dir / name

        if not ws_path.is_dir():
            warnings.append(f"Workspace directory does not exist: {ws_path}")
            return warnings

        if not (ws_path / "CLAUDE.md").exists():
            warnings.append("Missing CLAUDE.md")

        if not (ws_path / "knowledge").is_dir():
            warnings.append("Missing knowledge/ directory")

        if not (ws_path / ".claude" / "mcp.json").exists():
            warnings.append("Missing .claude/mcp.json")

        return warnings

    def create_workspace(
        self,
        name: str,
        template: str = "default",
        *,
        claude_md: str | None = None,
        mcp_json: dict | None = None,
    ) -> Path:
        """Create a new workspace from template.

        Args:
            name: Workspace name (used as directory name).
            template: Template name (currently only 'default').
            claude_md: Custom CLAUDE.md content. If None, uses default template.
            mcp_json: Custom .claude/mcp.json dict. If None, uses default.

        Returns:
            Path to the created workspace directory.

        Raises:
            FileExistsError: If workspace already exists.
        """
        ws_path = self._workspaces_dir / name
        if ws_path.exists():
            raise FileExistsError(f"Workspace already exists: {ws_path}")

        # Create directory structure
        ws_path.mkdir(parents=True)
        (ws_path / "knowledge").mkdir()
        (ws_path / "skills").mkdir()
        (ws_path / "sessions" / "pending").mkdir(parents=True)
        (ws_path / ".claude").mkdir()

        # Write CLAUDE.md
        content = claude_md if claude_md is not None else _DEFAULT_CLAUDE_MD.format(name=name)
        (ws_path / "CLAUDE.md").write_text(content, encoding="utf-8")

        # Write .claude/mcp.json
        mcp = mcp_json if mcp_json is not None else _DEFAULT_MCP_JSON
        (ws_path / ".claude" / "mcp.json").write_text(
            json.dumps(mcp, indent=2) + "\n", encoding="utf-8"
        )

        # Write .claude/settings.json
        (ws_path / ".claude" / "settings.json").write_text(
            json.dumps(_DEFAULT_SETTINGS_JSON, indent=2) + "\n", encoding="utf-8"
        )

        return ws_path

    def ensure_base_knowledge(self) -> Path:
        """Create the _base/ shared knowledge directory with placeholder files.

        Returns:
            Path to the _base/knowledge/ directory.
        """
        base_dir = self._workspaces_dir / "_base" / "knowledge"
        base_dir.mkdir(parents=True, exist_ok=True)

        product_md = base_dir / "product.md"
        if not product_md.exists():
            product_md.write_text(
                "# Product Overview\n\nDescribe the product here.\n",
                encoding="utf-8",
            )

        brand_md = base_dir / "brand.md"
        if not brand_md.exists():
            brand_md.write_text(
                "# Brand Guidelines\n\nDescribe brand voice and style here.\n",
                encoding="utf-8",
            )

        return base_dir
