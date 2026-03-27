"""
WorktreeManager for Maestro.

Manages git worktrees for agent isolation. Each agent gets its own
worktree under .maestro/worktrees/<name>, branched from the default branch.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class WorktreeManager:
    """git worktree 생성, 조회, 정리를 담당."""

    def __init__(self, project_root: Path) -> None:
        self._root = project_root
        self._worktrees_dir = project_root / ".maestro" / "worktrees"

    @property
    def worktrees_dir(self) -> Path:
        return self._worktrees_dir

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _git(
        self,
        *args: str,
        cwd: Path | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command and return the result."""
        cmd = ["git", *args]
        return subprocess.run(
            cmd,
            cwd=cwd or self._root,
            capture_output=True,
            text=True,
            check=check,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_git_repo(self) -> bool:
        """git rev-parse --is-inside-work-tree로 확인.

        worktree 내부(.git 파일)도 감지.
        """
        result = self._git(
            "rev-parse",
            "--is-inside-work-tree",
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _default_branch(self) -> str:
        """origin/HEAD에서 기본 branch명 추출. fallback: main -> master -> HEAD."""
        # Try origin/HEAD
        result = self._git(
            "symbolic-ref",
            "refs/remotes/origin/HEAD",
            check=False,
        )
        if result.returncode == 0:
            # e.g. "refs/remotes/origin/main" -> "main"
            ref = result.stdout.strip()
            return ref.rsplit("/", 1)[-1]

        # Fallback: check if main or master branch exists locally
        for candidate in ("main", "master"):
            result = self._git(
                "rev-parse",
                "--verify",
                candidate,
                check=False,
            )
            if result.returncode == 0:
                return candidate

        return "HEAD"

    def ensure_worktree(self, name: str) -> Path:
        """worktree가 없으면 생성, 있으면 경로 반환.

        항상 default branch에서 분기. branch가 이미 존재하면 재사용.
        """
        wt_path = self._worktrees_dir / name

        # Already exists — return immediately
        if wt_path.exists():
            return wt_path

        # Ensure parent directory
        self._worktrees_dir.mkdir(parents=True, exist_ok=True)

        branch = f"maestro/{name}"
        base = self._default_branch()

        # Check if branch already exists
        result = self._git("rev-parse", "--verify", branch, check=False)
        branch_exists = result.returncode == 0

        if branch_exists:
            self._git("worktree", "add", str(wt_path), branch)
        else:
            self._git("worktree", "add", str(wt_path), "-b", branch, base)

        return wt_path

    def remove_worktree(self, name: str) -> None:
        """worktree 삭제 및 branch 정리."""
        wt_path = self._worktrees_dir / name
        branch = f"maestro/{name}"

        # Remove the worktree
        self._git("worktree", "remove", "--force", str(wt_path), check=False)

        # Clean up the branch
        self._git("branch", "-D", branch, check=False)

    def list_worktrees(self) -> list[str]:
        """활성 worktree 이름 목록."""
        if not self._worktrees_dir.exists():
            return []
        return sorted(d.name for d in self._worktrees_dir.iterdir() if d.is_dir())

    def has_changes(self, name: str) -> bool:
        """worktree에 변경이 있는지 확인 (uncommitted + committed ahead of default)."""
        wt_path = self._worktrees_dir / name
        if not wt_path.exists():
            return False

        # Check uncommitted changes
        result = self._git("status", "--porcelain", cwd=wt_path, check=False)
        if result.stdout.strip():
            return True

        # Check if branch has commits ahead of default branch
        branch = f"maestro/{name}"
        base = self._default_branch()
        result = self._git("rev-list", "--count", f"{base}..{branch}", check=False)
        if result.returncode == 0 and result.stdout.strip() not in ("", "0"):
            return True

        return False
