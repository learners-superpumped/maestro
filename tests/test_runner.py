"""
TDD tests for maestro.runner

Tests cover:
- parse_stream_event: valid JSON, invalid JSON, empty line
- AgentRunner._build_execute_args: correct flags including --max-turns and --max-budget-usd
- AgentRunner._build_resume_args: with session_id
"""

from __future__ import annotations

import pytest

from maestro.models import Task, TaskStatus
from maestro.runner import AgentRunner, parse_stream_event


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_task() -> Task:
    """Return a minimal Task for use in runner tests."""
    return Task(
        id="task-001",
        type="claude",
        workspace="/tmp/test-workspace",
        title="Test Task",
        instruction="Write a hello world script",
        budget_usd=5.0,
    )


@pytest.fixture
def runner() -> AgentRunner:
    """Return an AgentRunner instance."""
    return AgentRunner()


# ---------------------------------------------------------------------------
# parse_stream_event
# ---------------------------------------------------------------------------


class TestParseStreamEvent:
    def test_valid_json_returns_dict(self):
        line = '{"type": "system", "session_id": "abc-123"}'
        result = parse_stream_event(line)
        assert result == {"type": "system", "session_id": "abc-123"}

    def test_valid_json_assistant_message(self):
        line = '{"type": "assistant", "message": {"content": "Hello"}}'
        result = parse_stream_event(line)
        assert result is not None
        assert result["type"] == "assistant"
        assert result["message"]["content"] == "Hello"

    def test_valid_json_result_event(self):
        line = '{"type": "result", "cost_usd": 0.0042, "is_error": false}'
        result = parse_stream_event(line)
        assert result is not None
        assert result["type"] == "result"
        assert result["cost_usd"] == pytest.approx(0.0042)

    def test_invalid_json_returns_none(self):
        line = "not-valid-json"
        result = parse_stream_event(line)
        assert result is None

    def test_empty_line_returns_none(self):
        result = parse_stream_event("")
        assert result is None

    def test_whitespace_only_line_returns_none(self):
        result = parse_stream_event("   ")
        assert result is None

    def test_line_with_leading_trailing_whitespace_is_parsed(self):
        line = '  {"type": "system", "session_id": "xyz"}  '
        result = parse_stream_event(line)
        assert result == {"type": "system", "session_id": "xyz"}

    def test_partial_json_returns_none(self):
        line = '{"type": "system"'
        result = parse_stream_event(line)
        assert result is None

    def test_json_array_returns_none(self):
        # We expect dicts only; arrays are not valid stream events
        line = '[1, 2, 3]'
        result = parse_stream_event(line)
        assert result is None


# ---------------------------------------------------------------------------
# AgentRunner._build_execute_args
# ---------------------------------------------------------------------------


class TestBuildExecuteArgs:
    def test_returns_list_of_strings(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=["Read", "Write"], max_turns=20)
        assert isinstance(args, list)
        assert all(isinstance(a, str) for a in args)

    def test_starts_with_claude(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=["Read"], max_turns=10)
        assert args[0] == "claude"

    def test_includes_prompt_flag(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=[], max_turns=5)
        assert "-p" in args
        p_idx = args.index("-p")
        assert args[p_idx + 1] == sample_task.instruction

    def test_includes_stream_json_output_format(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=[], max_turns=5)
        assert "--output-format" in args
        idx = args.index("--output-format")
        assert args[idx + 1] == "stream-json"

    def test_includes_allowed_tools(self, runner: AgentRunner, sample_task: Task):
        allowed_tools = ["Read", "Write", "Bash"]
        args = runner._build_execute_args(sample_task, allowed_tools=allowed_tools, max_turns=5)
        assert "--allowedTools" in args
        idx = args.index("--allowedTools")
        assert args[idx + 1] == "Read,Write,Bash"

    def test_includes_max_turns(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=[], max_turns=20)
        assert "--max-turns" in args
        idx = args.index("--max-turns")
        assert args[idx + 1] == "20"

    def test_max_turns_is_string(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=[], max_turns=15)
        idx = args.index("--max-turns")
        # Must be a str for subprocess consumption
        assert isinstance(args[idx + 1], str)
        assert args[idx + 1] == "15"

    def test_includes_max_budget_usd(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=[], max_turns=5)
        assert "--max-budget-usd" in args
        idx = args.index("--max-budget-usd")
        assert args[idx + 1] == str(sample_task.budget_usd)

    def test_max_budget_usd_uses_task_budget(self, runner: AgentRunner):
        task = Task(
            id="task-002",
            type="claude",
            workspace="/tmp/ws",
            title="Budget Task",
            instruction="Do something",
            budget_usd=2.5,
        )
        args = runner._build_execute_args(task, allowed_tools=[], max_turns=5)
        idx = args.index("--max-budget-usd")
        assert float(args[idx + 1]) == pytest.approx(2.5)

    def test_empty_allowed_tools_produces_empty_string(self, runner: AgentRunner, sample_task: Task):
        args = runner._build_execute_args(sample_task, allowed_tools=[], max_turns=5)
        idx = args.index("--allowedTools")
        assert args[idx + 1] == ""

    def test_full_args_structure(self, runner: AgentRunner, sample_task: Task):
        """Integration check: verify the complete expected argument list."""
        args = runner._build_execute_args(
            sample_task,
            allowed_tools=["Read", "Write"],
            max_turns=20,
        )
        assert args == [
            "claude",
            "-p", sample_task.instruction,
            "--output-format", "stream-json",
            "--verbose",
            "--allowedTools", "Read,Write",
            "--max-turns", "20",
            "--max-budget-usd", str(sample_task.budget_usd),
        ]


# ---------------------------------------------------------------------------
# AgentRunner._build_resume_args
# ---------------------------------------------------------------------------


class TestBuildResumeArgs:
    def test_returns_list_of_strings(self, runner: AgentRunner):
        args = runner._build_resume_args("session-abc", "Continue the task")
        assert isinstance(args, list)
        assert all(isinstance(a, str) for a in args)

    def test_starts_with_claude(self, runner: AgentRunner):
        args = runner._build_resume_args("session-abc", "Continue")
        assert args[0] == "claude"

    def test_includes_resume_flag(self, runner: AgentRunner):
        session_id = "session-xyz-123"
        args = runner._build_resume_args(session_id, "Continue")
        assert "--resume" in args
        idx = args.index("--resume")
        assert args[idx + 1] == session_id

    def test_includes_prompt_flag(self, runner: AgentRunner):
        instruction = "Pick up where you left off"
        args = runner._build_resume_args("session-abc", instruction)
        assert "-p" in args
        idx = args.index("-p")
        assert args[idx + 1] == instruction

    def test_includes_stream_json_output_format(self, runner: AgentRunner):
        args = runner._build_resume_args("session-abc", "Continue")
        assert "--output-format" in args
        idx = args.index("--output-format")
        assert args[idx + 1] == "stream-json"

    def test_full_args_structure(self, runner: AgentRunner):
        """Integration check: verify the complete expected argument list."""
        session_id = "my-session-id"
        instruction = "Resume the analysis"
        args = runner._build_resume_args(session_id, instruction)
        assert args == [
            "claude",
            "--resume", session_id,
            "-p", instruction,
            "--output-format", "stream-json",
            "--verbose",
        ]

    def test_different_session_ids(self, runner: AgentRunner):
        for session_id in ["abc", "123-456-789", "uuid-style-id"]:
            args = runner._build_resume_args(session_id, "instruction")
            idx = args.index("--resume")
            assert args[idx + 1] == session_id
