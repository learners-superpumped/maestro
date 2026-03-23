"""
Workspace Manager for Maestro.

Manages workspace directories for agents. Each workspace is a directory
containing CLAUDE.md, knowledge/, skills/, sessions/, and .claude/ config.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# MCP server definitions (shared across templates)
# ---------------------------------------------------------------------------

_MCP_MAESTRO_STORE = {
    "command": "python",
    "args": ["-m", "maestro.mcp_store"],
    "env": {
        "MAESTRO_DAEMON_PORT": "${MAESTRO_DAEMON_PORT}",
    },
}

# NOTE: SNS workspaces use agent-browser CLI via Bash, not an MCP server.
# agent-browser is invoked directly by the Claude Code session.

_MCP_MAESTRO_EMBEDDING = {
    "command": "python",
    "args": ["-m", "maestro.mcp_embedding"],
    "env": {
        "MAESTRO_DAEMON_PORT": "${MAESTRO_DAEMON_PORT}",
    },
}


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

_SNS_CLAUDE_MD = textwrap.dedent("""\
    # {name} Social Media Agent

    ## Role
    Manage {name} social presence. Create, schedule, and manage posts
    following brand voice guidelines and engagement strategies.

    ## Knowledge
    Read these files for context:
    - ../_base/knowledge/product.md
    - ../_base/knowledge/brand.md
    - ./knowledge/tone.md
    - ./knowledge/strategy.md
    - ./knowledge/guidelines.md

    ## Available Tools
    - maestro-store: Task management, history search, approval workflow
    - agent-browser: Bash CLI로 브라우저 조작 (로그인 세션 유지됨)

    ## Browser (agent-browser)
    플랫폼 조작은 `agent-browser` CLI를 Bash 도구로 사용한다.

    ```bash
    agent-browser open <url>              # 페이지 이동
    agent-browser snapshot --compact      # 페이지 구조 (AI용)
    agent-browser click @<ref>            # 요소 클릭
    agent-browser type @<ref> "텍스트"     # 텍스트 입력
    agent-browser scroll down 500         # 스크롤
    agent-browser screenshot              # 스크린샷
    agent-browser wait 2000               # 대기
    ```

    패턴: snapshot → @ref 확인 → 액션 → snapshot으로 결과 확인

    ## Workflow
    1. knowledge/ 파일 읽기 (톤, 전략)
    2. agent-browser로 플랫폼 탐색
    3. 초안 작성 → sessions/pending/에 JSON 저장
    4. 승인 필요 액션은 대기
    5. 승인 후 agent-browser로 실행
    6. 결과 보고

    ## Rules
    - 승인 없이 게시/댓글/좋아요 실행 금지
    - snapshot으로 확인한 @ref만 사용 (추측 금지)
    - 에러 시 screenshot 찍고 보고
""")

_SEO_CLAUDE_MD = textwrap.dedent("""\
    # SEO Agent

    ## Role
    Audit and optimize website SEO. Analyze site structure, content,
    metadata, and search performance to provide actionable recommendations.

    ## Knowledge
    Read these files for context:
    - ../_base/knowledge/product.md
    - ./knowledge/strategy.md
    - ./knowledge/guidelines.md

    ## Available Tools
    - maestro-store: Task management, history search, approval workflow

    ## Workflow
    1. Read the task instruction carefully
    2. Consult SEO strategy and technical guidelines
    3. Perform analysis or generate recommendations
    4. Submit results via maestro_task_submit_result

    ## Rules
    - Follow the instruction precisely
    - Base recommendations on current SEO best practices
    - Provide data-driven insights when possible
    - Report results via maestro_task_submit_result
    - Request approval via maestro_approval_submit for external actions
""")

_AD_CLAUDE_MD = textwrap.dedent("""\
    # Ad Campaign Agent

    ## Role
    Create and manage ad campaigns. Draft ad copy, select creative assets,
    define targeting parameters, and track campaign performance.

    ## Knowledge
    Read these files for context:
    - ../_base/knowledge/product.md
    - ../_base/knowledge/brand.md
    - ./knowledge/strategy.md
    - ./knowledge/guidelines.md

    ## Available Tools
    - maestro-store: Task management, history search, approval workflow
    - maestro-embedding: Search and retrieve creative assets

    ## Workflow
    1. Read the task instruction carefully
    2. Consult ad strategy and platform guidelines
    3. Search for relevant creative assets via maestro-embedding
    4. Draft ad copy and campaign parameters
    5. Submit draft for approval via maestro_approval_submit
    6. Once approved, execute the campaign setup
    7. Submit results via maestro_task_submit_result

    ## Rules
    - Follow the instruction precisely
    - Always align ad copy with brand voice
    - Submit campaign drafts for human approval
    - Report results via maestro_task_submit_result
    - Request approval via maestro_approval_submit for all external actions
    - Never launch campaigns without explicit approval
""")

_DEFAULT_MCP_JSON = {
    "mcpServers": {
        "maestro-store": _MCP_MAESTRO_STORE,
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
# Knowledge file templates
# ---------------------------------------------------------------------------

_KNOWLEDGE_TEMPLATES: dict[str, dict[str, str]] = {
    "tone.md": "# Tone of Voice\n\nDefine the brand's tone of voice here.\n",
    "strategy.md": "# Strategy\n\nDefine the strategy here.\n",
    "guidelines.md": "# Guidelines\n\nDefine platform guidelines and rules here.\n",
}


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, Any]] = {
    "default": {
        "claude_md": _DEFAULT_CLAUDE_MD,
        "knowledge_files": [],
        "mcp_servers": {
            "maestro-store": _MCP_MAESTRO_STORE,
        },
    },
    "sns": {
        "claude_md": _SNS_CLAUDE_MD,
        "knowledge_files": ["tone.md", "strategy.md", "guidelines.md"],
        "mcp_servers": {
            "maestro-store": _MCP_MAESTRO_STORE,
        },
    },
    "seo": {
        "claude_md": _SEO_CLAUDE_MD,
        "knowledge_files": ["strategy.md", "guidelines.md"],
        "mcp_servers": {
            "maestro-store": _MCP_MAESTRO_STORE,
        },
    },
    "ad": {
        "claude_md": _AD_CLAUDE_MD,
        "knowledge_files": ["strategy.md", "guidelines.md"],
        "mcp_servers": {
            "maestro-store": _MCP_MAESTRO_STORE,
            "maestro-embedding": _MCP_MAESTRO_EMBEDDING,
        },
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

    @staticmethod
    def available_templates() -> list[str]:
        """Return the list of available template names."""
        return sorted(TEMPLATES.keys())

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
            template: Template name ('default', 'sns', 'seo', 'ad').
            claude_md: Custom CLAUDE.md content. If None, uses template.
            mcp_json: Custom .claude/mcp.json dict. If None, uses template.

        Returns:
            Path to the created workspace directory.

        Raises:
            FileExistsError: If workspace already exists.
            ValueError: If template name is unknown.
        """
        if template not in TEMPLATES:
            valid = ", ".join(sorted(TEMPLATES.keys()))
            raise ValueError(
                f"Unknown template: {template!r}. Valid templates: {valid}"
            )

        tmpl = TEMPLATES[template]
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
        if claude_md is not None:
            content = claude_md
        else:
            content = tmpl["claude_md"].format(name=name)
        (ws_path / "CLAUDE.md").write_text(content, encoding="utf-8")

        # Write .claude/mcp.json
        if mcp_json is not None:
            mcp = mcp_json
        else:
            mcp = {"mcpServers": dict(tmpl["mcp_servers"])}
        (ws_path / ".claude" / "mcp.json").write_text(
            json.dumps(mcp, indent=2) + "\n", encoding="utf-8"
        )

        # Write .claude/settings.json
        (ws_path / ".claude" / "settings.json").write_text(
            json.dumps(_DEFAULT_SETTINGS_JSON, indent=2) + "\n", encoding="utf-8"
        )

        # Write knowledge files from template
        for filename in tmpl["knowledge_files"]:
            knowledge_content = _KNOWLEDGE_TEMPLATES.get(filename, f"# {filename}\n")
            (ws_path / "knowledge" / filename).write_text(
                knowledge_content, encoding="utf-8"
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
