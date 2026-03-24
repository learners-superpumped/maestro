"""Tests for the Maestro CLI."""

from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from maestro.cli import main


class TestHelp:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Maestro" in result.output

    def test_task_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["task", "--help"])
        assert result.exit_code == 0
        assert "Manage tasks" in result.output

    def test_init_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0


class TestInit:
    def test_init_creates_config(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert Path("maestro.yaml").exists()
            assert Path("store").is_dir()
            assert Path("workspaces/_base/knowledge").is_dir()
            assert Path("logs").is_dir()
            assert "initialized" in result.output.lower()

    def test_init_copies_example(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Write an example config
            Path("maestro.yaml.example").write_text(
                'project:\n  name: "from-example"\n  store_path: ./store/maestro.db\n',
                encoding="utf-8",
            )
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            content = Path("maestro.yaml").read_text()
            assert "from-example" in content
            assert "copied from example" in result.output.lower()

    def test_init_skips_existing_config(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("maestro.yaml").write_text(
                'project:\n  name: "existing"\n  store_path: ./store/maestro.db\n',
                encoding="utf-8",
            )
            result = runner.invoke(main, ["init"])
            assert result.exit_code == 0
            assert "already exists" in result.output.lower()


class TestStatus:
    def test_status_no_daemon(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["status"])
            assert result.exit_code == 0
            assert "not running" in result.output.lower()

    def test_status_stale_pid(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            store_dir = Path("store")
            store_dir.mkdir()
            # Use a PID that almost certainly doesn't exist
            (store_dir / "maestro.pid").write_text("999999999")
            result = runner.invoke(main, ["status"])
            assert result.exit_code == 0
            assert "not running" in result.output.lower()


class TestStop:
    def test_stop_no_pid(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["stop"])
            assert result.exit_code == 0
            assert "not running" in result.output.lower()


class TestTaskCommands:
    def _init_project(self) -> None:
        """Helper: init project in the current isolated filesystem."""
        Path("maestro.yaml").write_text(
            'project:\n  name: "test"\n  store_path: ./store/maestro.db\n',
            encoding="utf-8",
        )
        runner = CliRunner()
        runner.invoke(main, ["init"])

    def test_task_create(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            result = runner.invoke(main, [
                "task", "create",
                "--workspace", "test-ws",
                "--type", "shell",
                "--title", "Test task",
                "--instruction", "echo hello",
            ])
            assert result.exit_code == 0
            assert "task created" in result.output.lower()

    def test_task_list_empty(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            result = runner.invoke(main, ["task", "list"])
            assert result.exit_code == 0
            assert "no tasks found" in result.output.lower()

    def test_task_create_and_list(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            runner.invoke(main, [
                "task", "create",
                "--workspace", "ws1",
                "--type", "shell",
                "--title", "My Task",
                "--instruction", "do stuff",
            ])
            result = runner.invoke(main, ["task", "list"])
            assert result.exit_code == 0
            assert "My Task" in result.output

    def test_task_get(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            create_result = runner.invoke(main, [
                "task", "create",
                "--workspace", "ws1",
                "--type", "claude",
                "--title", "Detail Task",
                "--instruction", "do things",
            ])
            # Extract task ID from output ("Task created: <id>")
            task_id = create_result.output.split("Task created: ")[1].split("\n")[0].strip()

            result = runner.invoke(main, ["task", "get", task_id])
            assert result.exit_code == 0
            assert "Detail Task" in result.output
            assert "pending" in result.output.lower()

    def test_task_get_not_found(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            result = runner.invoke(main, ["task", "get", "nonexist"])
            assert result.exit_code != 0

    def test_approve(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            create_result = runner.invoke(main, [
                "task", "create",
                "--workspace", "ws1",
                "--type", "shell",
                "--title", "Approve Me",
                "--instruction", "run it",
            ])
            task_id = create_result.output.split("Task created: ")[1].split("\n")[0].strip()

            result = runner.invoke(main, ["approve", task_id])
            assert result.exit_code == 0
            assert "approved" in result.output.lower()

    def test_reject(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            create_result = runner.invoke(main, [
                "task", "create",
                "--workspace", "ws1",
                "--type", "shell",
                "--title", "Reject Me",
                "--instruction", "bad task",
            ])
            task_id = create_result.output.split("Task created: ")[1].split("\n")[0].strip()

            result = runner.invoke(main, ["reject", task_id])
            assert result.exit_code == 0
            assert "rejected" in result.output.lower()

    def test_revise(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            create_result = runner.invoke(main, [
                "task", "create",
                "--workspace", "ws1",
                "--type", "shell",
                "--title", "Revise Me",
                "--instruction", "original instruction",
            ])
            task_id = create_result.output.split("Task created: ")[1].split("\n")[0].strip()

            result = runner.invoke(main, ["revise", task_id, "--note", "please fix X"])
            assert result.exit_code == 0
            assert "revised" in result.output.lower()

            # Verify the note was appended
            get_result = runner.invoke(main, ["task", "get", task_id])
            assert "please fix X" in get_result.output

    def test_task_list_limit(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            # Create 5 tasks
            for i in range(5):
                runner.invoke(main, [
                    "task", "create",
                    "--workspace", "ws1",
                    "--type", "shell",
                    "--title", f"Task-{i}",
                    "--instruction", f"do {i}",
                ])
            # Default limit=20 should show all 5
            result = runner.invoke(main, ["task", "list"])
            assert result.exit_code == 0
            for i in range(5):
                assert f"Task-{i}" in result.output

            # Limit to 3
            result = runner.invoke(main, ["task", "list", "--limit", "3"])
            assert result.exit_code == 0
            assert "Use --limit to show more" in result.output

    def test_task_list_filter_status(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            # Create two tasks
            runner.invoke(main, [
                "task", "create",
                "--workspace", "ws1", "--type", "shell",
                "--title", "T1", "--instruction", "a",
            ])
            create2 = runner.invoke(main, [
                "task", "create",
                "--workspace", "ws1", "--type", "shell",
                "--title", "T2", "--instruction", "b",
            ])
            task2_id = create2.output.split("Task created: ")[1].split("\n")[0].strip()
            # Approve second task
            runner.invoke(main, ["approve", task2_id])

            # Filter by approved
            result = runner.invoke(main, ["task", "list", "--status", "approved"])
            assert result.exit_code == 0
            assert "T2" in result.output
            assert "T1" not in result.output

    def test_task_list_limit_validation(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            result = runner.invoke(main, ["task", "list", "--limit", "0"])
            assert result.exit_code != 0
            assert "positive integer" in result.output.lower()

            result = runner.invoke(main, ["task", "list", "--limit", "-5"])
            assert result.exit_code != 0
            assert "positive integer" in result.output.lower()

    def test_task_list_limit_short_flag(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            for i in range(5):
                runner.invoke(main, [
                    "task", "create",
                    "--workspace", "ws1",
                    "--type", "shell",
                    "--title", f"Task-{i}",
                    "--instruction", f"do {i}",
                ])
            result = runner.invoke(main, ["task", "list", "-L", "3"])
            assert result.exit_code == 0
            assert "Use --limit to show more" in result.output

    def test_task_list_tree_limit(self) -> None:
        """Tree mode applies limit to root tasks, children always included."""
        import asyncio

        from maestro.config import load_config
        from maestro.models import Task, TaskStatus
        from maestro.store import Store

        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            # Create 3 root tasks via CLI
            root_ids = []
            for i in range(3):
                r = runner.invoke(main, [
                    "task", "create",
                    "--workspace", "ws1",
                    "--type", "shell",
                    "--title", f"Root-{i}",
                    "--instruction", f"root {i}",
                ])
                root_ids.append(r.output.split("Task created: ")[1].split("\n")[0].strip())

            # Create a child task via store directly (CLI has no --parent flag)
            cfg = load_config(Path("maestro.yaml"))
            store = Store(cfg.project.store_path)

            async def _add_child() -> None:
                await store.init_db()
                child = Task(
                    id="child-001",
                    type="shell",
                    status=TaskStatus.PENDING,
                    workspace="ws1",
                    title="Child-0",
                    instruction="child task",
                    parent_task_id=root_ids[-1],  # newest root, shown within limit
                )
                await store.create_task(child)

            asyncio.run(_add_child())

            # List with limit=2 — tree mode should activate
            result = runner.invoke(main, ["task", "list", "--limit", "2"])
            assert result.exit_code == 0
            # Child must appear even though limit cuts root count
            assert "Child-0" in result.output
            assert "root tasks" in result.output.lower()

    def test_asset_list_limit(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            # Register 5 assets via CLI
            for i in range(5):
                runner.invoke(main, [
                    "asset", "register",
                    "--workspace", "ws1",
                    "--type", "post",
                    "--title", f"Asset-{i}",
                    "--content", f'{{"body": "body {i}"}}',
                ])
            # Default limit=20 shows all 5
            result = runner.invoke(main, ["asset", "list"])
            assert result.exit_code == 0
            for i in range(5):
                assert f"Asset-{i}" in result.output

            # Limit to 3
            result = runner.invoke(main, ["asset", "list", "--limit", "3"])
            assert result.exit_code == 0
            assert "Use --limit to show more" in result.output

    def test_asset_list_limit_validation(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            self._init_project()
            result = runner.invoke(main, ["asset", "list", "--limit", "0"])
            assert result.exit_code != 0
            assert "positive integer" in result.output.lower()
