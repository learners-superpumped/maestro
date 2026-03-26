"""Tests for the Maestro Daemon."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

import pytest

from maestro.config import (
    AgentConfig,
    AgentDefinition,
    BudgetConfig,
    ConcurrencyConfig,
    DaemonConfig,
    LoggingConfig,
    MaestroConfig,
    ProjectConfig,
)
from maestro.daemon import Daemon
from maestro.models import Task, TaskResult, TaskStatus
from maestro.store import Store

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs) -> MaestroConfig:
    return MaestroConfig(
        project=ProjectConfig(name="test"),
        daemon=DaemonConfig(),
        concurrency=ConcurrencyConfig(),
        budget=BudgetConfig(),
        agent=AgentConfig(),
        logging=LoggingConfig(),
        **kwargs,
    )


def _make_task(
    task_id: str = "t1",
    approval_level: int = 0,
    status: TaskStatus = TaskStatus.PENDING,
    agent: str = "default",
    no_worktree: bool = False,
    goal_id: str | None = None,
) -> Task:
    return Task(
        id=task_id,
        type="claude",
        title="Test task",
        instruction="Do something",
        status=status,
        approval_level=approval_level,
        agent=agent,
        no_worktree=no_worktree,
        goal_id=goal_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_approve_level0(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A pending task with approval_level=0 should be auto-approved."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="auto-0", approval_level=0)
    await store.create_task(task)

    await daemon._auto_approve_pending()

    updated = await store.get_task("auto-0")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED


@pytest.mark.asyncio
async def test_auto_approve_level1(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A pending task with approval_level=1 should also be auto-approved."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="auto-1", approval_level=1)
    await store.create_task(task)

    await daemon._auto_approve_pending()

    updated = await store.get_task("auto-1")
    assert updated is not None
    assert updated.status == TaskStatus.APPROVED


@pytest.mark.asyncio
async def test_no_auto_approve_level2(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A pending task with approval_level=2 must NOT be auto-approved."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="manual-2", approval_level=2)
    await store.create_task(task)

    await daemon._auto_approve_pending()

    updated = await store.get_task("manual-2")
    assert updated is not None
    assert updated.status == TaskStatus.PENDING


@pytest.mark.asyncio
async def test_handle_result_success(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A successful TaskResult should transition the task to COMPLETED."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="ok-1", status=TaskStatus.RUNNING)
    # Need to insert as PENDING then transition through states in DB
    pending_task = _make_task(
        task_id="ok-1", status=TaskStatus.PENDING, approval_level=0
    )
    await store.create_task(pending_task)
    await store.update_task_status("ok-1", TaskStatus.APPROVED)
    await store.update_task_status("ok-1", TaskStatus.CLAIMED)
    await store.update_task_status("ok-1", TaskStatus.RUNNING)

    result = TaskResult(
        task_id="ok-1",
        success=True,
        session_id="sess-abc",
        cost_usd=0.05,
    )

    # Use the in-memory task object with RUNNING status
    task.status = TaskStatus.RUNNING
    await daemon._handle_result(task, result)

    updated = await store.get_task("ok-1")
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED
    assert updated.session_id == "sess-abc"
    assert updated.cost_usd == 0.05


@pytest.mark.asyncio
async def test_handle_result_failure_retries(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A failed TaskResult with retries remaining should queue a retry."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # Create task with attempt=0, max_retries=3
    pending_task = _make_task(
        task_id="retry-1", status=TaskStatus.PENDING, approval_level=0
    )
    await store.create_task(pending_task)
    await store.update_task_status("retry-1", TaskStatus.APPROVED)
    await store.update_task_status("retry-1", TaskStatus.CLAIMED)
    await store.update_task_status("retry-1", TaskStatus.RUNNING)

    task = _make_task(task_id="retry-1", status=TaskStatus.RUNNING)
    task.attempt = 0
    task.max_retries = 3

    result = TaskResult(
        task_id="retry-1",
        success=False,
        error="Something went wrong",
    )

    await daemon._handle_result(task, result)

    updated = await store.get_task("retry-1")
    assert updated is not None
    assert updated.status == TaskStatus.RETRY_QUEUED
    assert updated.attempt == 1
    assert updated.error == "Something went wrong"


@pytest.mark.asyncio
async def test_handle_result_failure_no_retries(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A failed TaskResult with no retries left should mark FAILED."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    pending_task = _make_task(
        task_id="fail-1", status=TaskStatus.PENDING, approval_level=0
    )
    await store.create_task(pending_task)
    await store.update_task_status("fail-1", TaskStatus.APPROVED)
    await store.update_task_status("fail-1", TaskStatus.CLAIMED)
    await store.update_task_status("fail-1", TaskStatus.RUNNING)

    task = _make_task(task_id="fail-1", status=TaskStatus.RUNNING)
    task.attempt = 2
    task.max_retries = 3  # attempt + 1 == max_retries -> no retry

    result = TaskResult(
        task_id="fail-1",
        success=False,
        error="Permanent failure",
    )

    await daemon._handle_result(task, result)

    updated = await store.get_task("fail-1")
    assert updated is not None
    assert updated.status == TaskStatus.FAILED
    assert updated.error == "Permanent failure"


@pytest.mark.asyncio
async def test_stop_sets_shutdown(
    tmp_path: pathlib.Path, db_path: pathlib.Path
) -> None:
    """Calling stop() should set the shutdown event."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    assert not daemon._shutdown.is_set()
    daemon.stop()
    assert daemon._shutdown.is_set()


@pytest.mark.asyncio
async def test_resume_approved_paused_task(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """An approved task with session_id should be picked up for resume."""
    from unittest.mock import AsyncMock

    store = Store(db_path)
    config = _make_config()

    daemon = Daemon(config, store, tmp_path)

    # Mock worktree manager so _resolve_cwd works without real git repo
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = False

    # Create task in PENDING state, advance to APPROVED, then set session_id
    task = _make_task(task_id="resume-1", approval_level=2, status=TaskStatus.PENDING)
    await store.create_task(task)

    # Simulate: task ran, got paused, then approved with a session_id
    await store.update_task_status("resume-1", TaskStatus.APPROVED)
    await store.update_task_status("resume-1", TaskStatus.CLAIMED)
    await store.update_task_status(
        "resume-1", TaskStatus.RUNNING, session_id="sess-resume-123"
    )
    await store.update_task_status("resume-1", TaskStatus.PAUSED)

    # Create an approval record
    await store.create_approval(
        {
            "id": "appr-resume-1",
            "task_id": "resume-1",
            "status": "pending",
            "draft_json": '{"content": "draft"}',
        }
    )

    # Now approve it
    from maestro.approval import ApprovalManager

    mgr = ApprovalManager(store)
    await mgr.approve("resume-1")

    # Verify task is APPROVED with session_id
    t = await store.get_task("resume-1")
    assert t is not None
    assert t.status == TaskStatus.APPROVED
    assert t.session_id == "sess-resume-123"

    # Call _resume_approved_tasks -- it should claim the task and spawn a resume
    # We mock the runner to avoid actually running CLI
    daemon._runner.resume = AsyncMock(
        return_value=TaskResult(
            task_id="resume-1",
            success=True,
            session_id="sess-resume-123",
            cost_usd=0.01,
        )
    )

    await daemon._resume_approved_tasks()

    # Task should be claimed (resume was spawned)
    t = await store.get_task("resume-1")
    assert t is not None
    assert t.status == TaskStatus.CLAIMED

    # Wait for the spawned asyncio task to complete
    if "resume-1" in daemon._running_procs:
        await daemon._running_procs["resume-1"]

    # Now it should be completed
    t = await store.get_task("resume-1")
    assert t is not None
    assert t.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_handle_result_level1_sends_notification(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """A completed Level 1 task should create a notification."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # Create a level-1 task
    pending_task = _make_task(
        task_id="lvl1-1", approval_level=1, status=TaskStatus.PENDING
    )
    pending_task.title = "Level 1 Task"
    await store.create_task(pending_task)
    await store.update_task_status("lvl1-1", TaskStatus.APPROVED)
    await store.update_task_status("lvl1-1", TaskStatus.CLAIMED)
    await store.update_task_status("lvl1-1", TaskStatus.RUNNING)

    task = _make_task(task_id="lvl1-1", approval_level=1, status=TaskStatus.RUNNING)
    task.title = "Level 1 Task"

    result = TaskResult(
        task_id="lvl1-1",
        success=True,
        cost_usd=0.02,
    )

    await daemon._handle_result(task, result)

    updated = await store.get_task("lvl1-1")
    assert updated is not None
    assert updated.status == TaskStatus.COMPLETED

    # Check notification was created
    notifications = await store.list_notifications()
    assert len(notifications) == 1
    assert notifications[0]["type"] == "task_completed"
    assert "Level 1 Task" in notifications[0]["message"]


@pytest.mark.asyncio
async def test_no_review_after_approve(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """approve된 태스크가 resume 후 완료 -> 리뷰에 재진입하지 않음."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # 1. 태스크 생성 (approval_level=2 -> 수동 승인 대상)
    task = _make_task(task_id="approved-skip-review", approval_level=2)
    await store.create_task(task)

    # 2. approval "approved" 기록 생성
    await store.create_approval(
        {
            "id": "appr-skip-1",
            "task_id": "approved-skip-review",
            "status": "approved",
            "draft_json": '{"result": "done"}',
        }
    )

    # 3. daemon._on_task_completed 호출
    result = TaskResult(
        task_id="approved-skip-review",
        success=True,
        result_json='{"output": "done"}',
    )
    await daemon._on_task_completed(task, result)

    # 4. store.list_tasks()에서 review 태스크가 없어야 함
    all_tasks = await store.list_tasks()
    review_tasks = [t for t in all_tasks if t.type == "review"]
    assert len(review_tasks) == 0


@pytest.mark.asyncio
async def test_review_created_on_first_run(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """첫 실행 완료 -> 리뷰 태스크 생성됨, parent_task_id가 원본 태스크 ID와 일치."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # 1. 태스크 생성 (approval_level=2)
    task = _make_task(task_id="first-run-task", approval_level=2)
    await store.create_task(task)

    # 2. daemon._on_task_completed 호출 (approval 기록 없음 -> 첫 실행)
    result = TaskResult(
        task_id="first-run-task",
        success=True,
        result_json='{"output": "first result"}',
    )
    await daemon._on_task_completed(task, result)

    # 3. store.list_tasks()에서 review 태스크가 1개 있어야 함
    all_tasks = await store.list_tasks()
    review_tasks = [t for t in all_tasks if t.type == "review"]
    assert len(review_tasks) == 1

    # 4. review 태스크의 parent_task_id가 원본 태스크 ID와 일치해야 함
    assert review_tasks[0].parent_task_id == "first-run-task"


# ---------------------------------------------------------------------------
# _extract_json tests
# ---------------------------------------------------------------------------


def test_extract_json_raw_list():
    result = Daemon._extract_json([{"a": 1}])
    assert result == [{"a": 1}]


def test_extract_json_string():
    result = Daemon._extract_json('[{"a": 1}]')
    assert result == [{"a": 1}]


def test_extract_json_markdown_wrapped():
    text = '```json\n[{"a": 1}]\n```'
    result = Daemon._extract_json(text)
    assert result == [{"a": 1}]


def test_extract_json_invalid():
    result = Daemon._extract_json("not json")
    assert result is None


# ---------------------------------------------------------------------------
# _resolve_cwd tests
# ---------------------------------------------------------------------------


def test_resolve_cwd_not_git_repo(tmp_path: pathlib.Path) -> None:
    """When not in a git repo, should return base_path."""
    config = _make_config()
    store = MagicMock()
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = False

    task = _make_task(task_id="t1")
    result = daemon._resolve_cwd(task)
    assert result == tmp_path


def test_resolve_cwd_no_worktree_flag(tmp_path: pathlib.Path) -> None:
    """When task.no_worktree is True, should return base_path."""
    config = _make_config()
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = True

    task = _make_task(task_id="t1", no_worktree=True)
    result = daemon._resolve_cwd(task)
    assert result == tmp_path


def test_resolve_cwd_agent_no_worktree(tmp_path: pathlib.Path) -> None:
    """When agent_def.no_worktree is True, should return base_path."""
    config = _make_config(
        agents={"planner": AgentDefinition(name="planner", no_worktree=True)}
    )
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = True

    task = _make_task(task_id="t1", agent="planner")
    result = daemon._resolve_cwd(task)
    assert result == tmp_path


def test_resolve_cwd_goal_worktree(tmp_path: pathlib.Path) -> None:
    """When task has goal_id, should use goal-based worktree."""
    config = _make_config()
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = True
    expected_path = tmp_path / ".maestro" / "worktrees" / "goal-g1"
    daemon._worktree_mgr.ensure_worktree.return_value = expected_path

    task = _make_task(task_id="t1", goal_id="g1")
    result = daemon._resolve_cwd(task)
    daemon._worktree_mgr.ensure_worktree.assert_called_once_with("goal-g1")
    assert result == expected_path


def test_resolve_cwd_task_worktree(tmp_path: pathlib.Path) -> None:
    """When task has no goal_id, should use task-based worktree."""
    config = _make_config()
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = True
    expected_path = tmp_path / ".maestro" / "worktrees" / "task-t1"
    daemon._worktree_mgr.ensure_worktree.return_value = expected_path

    task = _make_task(task_id="t1")
    result = daemon._resolve_cwd(task)
    daemon._worktree_mgr.ensure_worktree.assert_called_once_with("task-t1")
    assert result == expected_path


# ---------------------------------------------------------------------------
# _load_prompt tests
# ---------------------------------------------------------------------------


def test_load_prompt_unknown_agent(tmp_path: pathlib.Path) -> None:
    """Unknown agent name should return None."""
    config = _make_config()
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path

    result = daemon._load_prompt("nonexistent")
    assert result is None


def test_load_prompt_with_role(tmp_path: pathlib.Path) -> None:
    """Agent with role should include role in prompt."""
    config = _make_config(
        agents={"coder": AgentDefinition(name="coder", role="Expert coder")}
    )
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path

    result = daemon._load_prompt("coder")
    assert result is not None
    assert "# Role" in result
    assert "Expert coder" in result


def test_load_prompt_project_override(tmp_path: pathlib.Path) -> None:
    """Project override file should take precedence over builtin."""
    override_dir = tmp_path / ".maestro" / "prompts"
    override_dir.mkdir(parents=True)
    override_file = override_dir / "custom.md"
    override_file.write_text("Custom project prompt")

    config = _make_config(
        agents={
            "coder": AgentDefinition(
                name="coder",
                instructions=".maestro/prompts/custom.md",
            )
        }
    )
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path

    result = daemon._load_prompt("coder")
    assert result is not None
    assert "Custom project prompt" in result


def test_load_prompt_builtin_fallback(tmp_path: pathlib.Path) -> None:
    """When no project override, should fall back to builtin prompts."""
    config = _make_config(agents={"planner": AgentDefinition(name="planner")})
    daemon = Daemon.__new__(Daemon)
    daemon._config = config
    daemon._base_path = tmp_path

    result = daemon._load_prompt("planner")
    # planner.md exists in maestro.prompts package (created in Task 4)
    assert result is not None
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Worktree auto-cleanup tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_result_auto_cleanup_worktree(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Successful standalone task with no changes should have its worktree removed."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # Mock worktree manager
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = True
    daemon._worktree_mgr.list_worktrees.return_value = ["task-cleanup-1"]
    daemon._worktree_mgr.has_changes.return_value = False

    # Create and transition task
    pending_task = _make_task(
        task_id="cleanup-1", status=TaskStatus.PENDING, approval_level=0
    )
    await store.create_task(pending_task)
    await store.update_task_status("cleanup-1", TaskStatus.APPROVED)
    await store.update_task_status("cleanup-1", TaskStatus.CLAIMED)
    await store.update_task_status("cleanup-1", TaskStatus.RUNNING)

    task = _make_task(task_id="cleanup-1", status=TaskStatus.RUNNING)

    result = TaskResult(
        task_id="cleanup-1",
        success=True,
        cost_usd=0.01,
    )

    await daemon._handle_result(task, result)

    # Verify worktree was cleaned up
    daemon._worktree_mgr.has_changes.assert_called_once_with("task-cleanup-1")
    daemon._worktree_mgr.remove_worktree.assert_called_once_with("task-cleanup-1")


@pytest.mark.asyncio
async def test_handle_result_no_cleanup_with_changes(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Successful standalone task WITH changes should NOT have its worktree removed."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    # Mock worktree manager
    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = True
    daemon._worktree_mgr.list_worktrees.return_value = ["task-keep-1"]
    daemon._worktree_mgr.has_changes.return_value = True

    # Create and transition task
    pending_task = _make_task(
        task_id="keep-1", status=TaskStatus.PENDING, approval_level=0
    )
    await store.create_task(pending_task)
    await store.update_task_status("keep-1", TaskStatus.APPROVED)
    await store.update_task_status("keep-1", TaskStatus.CLAIMED)
    await store.update_task_status("keep-1", TaskStatus.RUNNING)

    task = _make_task(task_id="keep-1", status=TaskStatus.RUNNING)

    result = TaskResult(
        task_id="keep-1",
        success=True,
        cost_usd=0.01,
    )

    await daemon._handle_result(task, result)

    # Verify worktree was NOT removed
    daemon._worktree_mgr.has_changes.assert_called_once_with("task-keep-1")
    daemon._worktree_mgr.remove_worktree.assert_not_called()


@pytest.mark.asyncio
async def test_handle_result_no_cleanup_no_worktree_flag(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """Task with no_worktree=True should skip worktree cleanup entirely."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    daemon._worktree_mgr = MagicMock()
    daemon._worktree_mgr.is_git_repo.return_value = True

    pending_task = _make_task(
        task_id="nowt-1", status=TaskStatus.PENDING, approval_level=0, no_worktree=True
    )
    await store.create_task(pending_task)
    await store.update_task_status("nowt-1", TaskStatus.APPROVED)
    await store.update_task_status("nowt-1", TaskStatus.CLAIMED)
    await store.update_task_status("nowt-1", TaskStatus.RUNNING)

    task = _make_task(task_id="nowt-1", status=TaskStatus.RUNNING, no_worktree=True)

    result = TaskResult(task_id="nowt-1", success=True, cost_usd=0.01)

    await daemon._handle_result(task, result)

    # Should never check worktrees
    daemon._worktree_mgr.list_worktrees.assert_not_called()
    daemon._worktree_mgr.remove_worktree.assert_not_called()


@pytest.mark.asyncio
async def test_result_json_not_overwritten_on_resume(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """resume 후 완료 시 기존 result_json이 보존되어야 함."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="preserve-rj", approval_level=2)
    await store.create_task(task)
    await store.update_task_status(
        "preserve-rj", TaskStatus.COMPLETED, result_json='{"original": "result"}'
    )

    task_with_result = await store.get_task("preserve-rj")

    result = TaskResult(
        task_id="preserve-rj",
        success=True,
        result_json='{"overwritten": "bad"}',
    )
    await daemon._handle_result(task_with_result, result)

    final = await store.get_task("preserve-rj")
    result_str = str(final.result_json)
    assert "original" in result_str
    assert "overwritten" not in result_str


@pytest.mark.asyncio
async def test_revision_includes_original_result(
    db_path: pathlib.Path, tmp_path: pathlib.Path
) -> None:
    """revision 태스크 생성 시 원본 result_json이 instruction에 포함되어야 함."""
    store = Store(db_path)
    config = _make_config()
    daemon = Daemon(config, store, tmp_path)

    task = _make_task(task_id="rev-orig", approval_level=1)
    await store.create_task(task)
    await store.update_task_status(
        "rev-orig", TaskStatus.COMPLETED, result_json='{"output": "original work"}'
    )

    import json

    review_task = Task(
        id="rev-review",
        type="review",
        agent="reviewer",
        title="Review: Test",
        instruction=json.dumps(
            {
                "original_task_id": "rev-orig",
                "original_agent": "default",
                "original_instruction": "Do something",
                "result": '{"output": "original work"}',
            }
        ),
        approval_level=0,
        parent_task_id="rev-orig",
    )
    await store.create_task(review_task)

    review_result = TaskResult(
        task_id="rev-review",
        success=True,
        result_json=json.dumps(
            {
                "verdict": "revise",
                "issues": ["fix import order"],
                "summary": "needs fix",
            }
        ),
    )
    await daemon._handle_review_result(review_task, review_result)

    all_tasks = await store.list_tasks()
    revision_tasks = [t for t in all_tasks if "Revision" in t.title]
    assert len(revision_tasks) == 1
    assert "original work" in revision_tasks[0].instruction
