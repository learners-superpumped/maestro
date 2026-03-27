"""Tests for WorktreeManager."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from maestro.worktree import WorktreeManager


class TestWorktreeManager:
    """Tests for git worktree management."""

    def setup_method(self) -> None:
        """Create a temporary git repo with an initial commit."""
        self.tmpdir = tempfile.mkdtemp()
        self.root = Path(self.tmpdir)
        subprocess.run(
            ["git", "init"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        self.mgr = WorktreeManager(self.root)

    def teardown_method(self) -> None:
        """Clean up worktrees before removing the temp directory."""
        import shutil

        # Remove any worktrees first to avoid git lock issues
        for name in self.mgr.list_worktrees():
            self.mgr.remove_worktree(name)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # is_git_repo
    # ------------------------------------------------------------------

    def test_is_git_repo_true(self) -> None:
        assert self.mgr.is_git_repo() is True

    def test_is_git_repo_false(self) -> None:
        non_git = Path(tempfile.mkdtemp())
        mgr = WorktreeManager(non_git)
        assert mgr.is_git_repo() is False

    # ------------------------------------------------------------------
    # ensure_worktree
    # ------------------------------------------------------------------

    def test_ensure_worktree_creates_and_returns_path(self) -> None:
        path = self.mgr.ensure_worktree("agent-1")
        assert path.exists()
        assert path == self.root / ".maestro" / "worktrees" / "agent-1"
        # Should be a git worktree (has .git file, not directory)
        assert (path / ".git").exists()

    def test_ensure_worktree_idempotent(self) -> None:
        path1 = self.mgr.ensure_worktree("agent-1")
        path2 = self.mgr.ensure_worktree("agent-1")
        assert path1 == path2
        assert path1.exists()

    def test_ensure_worktree_creates_branch(self) -> None:
        self.mgr.ensure_worktree("feature-x")
        result = subprocess.run(
            ["git", "branch", "--list", "maestro/feature-x"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        assert "maestro/feature-x" in result.stdout

    # ------------------------------------------------------------------
    # remove_worktree
    # ------------------------------------------------------------------

    def test_remove_worktree_cleans_up(self) -> None:
        self.mgr.ensure_worktree("doomed")
        assert (self.root / ".maestro" / "worktrees" / "doomed").exists()

        self.mgr.remove_worktree("doomed")
        assert not (self.root / ".maestro" / "worktrees" / "doomed").exists()

        # Branch should also be deleted
        result = subprocess.run(
            ["git", "branch", "--list", "maestro/doomed"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        assert "maestro/doomed" not in result.stdout

    def test_remove_nonexistent_worktree_no_error(self) -> None:
        # Should not raise
        self.mgr.remove_worktree("ghost")

    # ------------------------------------------------------------------
    # list_worktrees
    # ------------------------------------------------------------------

    def test_list_worktrees_empty(self) -> None:
        assert self.mgr.list_worktrees() == []

    def test_list_worktrees_returns_names(self) -> None:
        self.mgr.ensure_worktree("alpha")
        self.mgr.ensure_worktree("beta")
        names = self.mgr.list_worktrees()
        assert names == ["alpha", "beta"]

    # ------------------------------------------------------------------
    # has_changes
    # ------------------------------------------------------------------

    def test_has_changes_clean(self) -> None:
        self.mgr.ensure_worktree("clean")
        assert self.mgr.has_changes("clean") is False

    def test_has_changes_with_new_file(self) -> None:
        path = self.mgr.ensure_worktree("dirty")
        (path / "newfile.txt").write_text("hello")
        assert self.mgr.has_changes("dirty") is True

    def test_has_changes_nonexistent(self) -> None:
        assert self.mgr.has_changes("nope") is False

    # ------------------------------------------------------------------
    # branch reuse after remove
    # ------------------------------------------------------------------

    def test_branch_reuse_after_remove(self) -> None:
        """After removing a worktree, ensure_worktree reuses branch."""
        path = self.mgr.ensure_worktree("reuse-me")
        # Write a file and commit so the branch has unique content
        (path / "marker.txt").write_text("exists")
        subprocess.run(
            ["git", "add", "marker.txt"],
            cwd=path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "add marker"],
            cwd=path,
            check=True,
            capture_output=True,
        )

        # Remove worktree only (not the branch) by just removing the directory
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(path)],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
        assert not path.exists()

        # Branch should still exist
        result = subprocess.run(
            ["git", "branch", "--list", "maestro/reuse-me"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        assert "maestro/reuse-me" in result.stdout

        # Re-create worktree — should reuse the existing branch
        path2 = self.mgr.ensure_worktree("reuse-me")
        assert path2.exists()
        # The committed file should still be there
        assert (path2 / "marker.txt").exists()
