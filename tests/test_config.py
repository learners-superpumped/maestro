"""Tests for the Maestro configuration system."""

from __future__ import annotations

import pathlib

import pytest

from maestro.config import (
    AgentDefinition,
    AssetsConfig,
    MaestroConfig,
    ResourceProfile,
    load_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FULL_CONFIG = """\
project:
  name: "clawops-maestro"
  store_path: ./store/maestro.db

daemon:
  planner_interval_ms: 300000
  dispatcher_interval_ms: 10000
  reconcile_interval_ms: 30000

concurrency:
  max_total_agents: 5
  max_per_goal: 1

resources:
  chrome-profiles:
    threads:
      max_concurrent: 1
      path: ./chrome-profiles/threads

budget:
  daily_limit_usd: 30.0
  per_task_limit_usd: 5.0
  alert_threshold_pct: 80

goals:
  - id: threads-presence
    description: "Threads brand presence"
    metrics:
      post_frequency: "3/week"
      engagement_check: "daily"

schedules:
  - name: threads-daily-post
    cron: "0 9 * * *"
    task_type: create_post
    approval_level: 2
  - name: threads-engagement
    interval_ms: 1800000
    task_type: check_and_engage
    approval_level: 1

agent:
  default_allowed_tools:
    - Read
    - Write
    - Bash
  default_max_turns: 20
  stall_timeout_ms: 300000
  turn_timeout_ms: 3600000

agents:
  researcher:
    role: "Research specialist"
    instructions: "Focus on accurate data"
    tools:
      - Read
      - WebSearch
    max_turns: 30
    no_worktree: true
  writer:
    role: "Content writer"

logging:
  level: info
  file: ./logs/maestro.log
"""

MINIMAL_CONFIG = """\
project:
  name: "minimal-test"
"""


# ---------------------------------------------------------------------------
# load_config: file handling
# ---------------------------------------------------------------------------


def test_load_valid_config(tmp_path: pathlib.Path) -> None:
    """load_config should return a MaestroConfig for a valid YAML file."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)

    cfg = load_config(cfg_file)

    assert isinstance(cfg, MaestroConfig)


def test_load_missing_file_raises(tmp_path: pathlib.Path) -> None:
    """load_config should raise FileNotFoundError when the file does not exist."""
    missing = tmp_path / "nonexistent.yaml"

    with pytest.raises(FileNotFoundError):
        load_config(missing)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_defaults_applied(tmp_path: pathlib.Path) -> None:
    """Sections omitted from YAML should receive sensible defaults."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)

    cfg = load_config(cfg_file)

    # project defaults
    assert cfg.project.name == "minimal-test"
    assert cfg.project.store_path == "./store/maestro.db"

    # daemon defaults
    assert cfg.daemon.planner_interval_ms == 300_000
    assert cfg.daemon.dispatcher_interval_ms == 10_000
    assert cfg.daemon.reconcile_interval_ms == 30_000

    # concurrency defaults
    assert cfg.concurrency.max_total_agents == 5
    assert cfg.concurrency.max_per_goal == 1

    # budget defaults
    assert cfg.budget.daily_limit_usd == 30.0
    assert cfg.budget.per_task_limit_usd == 5.0
    assert cfg.budget.alert_threshold_pct == 80

    # agent defaults
    assert cfg.agent.default_max_turns == 0
    assert cfg.agent.stall_timeout_ms == 300_000
    assert cfg.agent.turn_timeout_ms == 3_600_000

    # logging defaults
    assert cfg.logging.level == "info"

    # collections default to empty
    assert cfg.resources == {}


# ---------------------------------------------------------------------------
# Environment variable substitution
# ---------------------------------------------------------------------------


def test_env_var_substitution(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """$VAR tokens in string values should be replaced with env-var values."""
    monkeypatch.setenv("MAESTRO_STORE", "/data/maestro.db")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    config_yaml = """\
project:
  name: "env-test"
  store_path: $MAESTRO_STORE

logging:
  level: $LOG_LEVEL
  file: ./logs/maestro.log
"""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(config_yaml)

    cfg = load_config(cfg_file)

    assert cfg.project.store_path == "/data/maestro.db"
    assert cfg.logging.level == "debug"


def test_env_var_substitution_missing_var(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An undefined $VAR should remain as-is (no exception)."""
    monkeypatch.delenv("UNDEFINED_VAR", raising=False)

    config_yaml = """\
project:
  name: "env-test"
  store_path: $UNDEFINED_VAR
"""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(config_yaml)

    cfg = load_config(cfg_file)
    # undefined vars are left unchanged
    assert cfg.project.store_path == "$UNDEFINED_VAR"


# ---------------------------------------------------------------------------
# ProjectConfig
# ---------------------------------------------------------------------------


def test_project_config_parsed(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.project.name == "clawops-maestro"
    assert cfg.project.store_path == "./store/maestro.db"


# ---------------------------------------------------------------------------
# DaemonConfig
# ---------------------------------------------------------------------------


def test_daemon_config_parsed(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.daemon.planner_interval_ms == 300_000
    assert cfg.daemon.dispatcher_interval_ms == 10_000
    assert cfg.daemon.reconcile_interval_ms == 30_000


# ---------------------------------------------------------------------------
# ConcurrencyConfig
# ---------------------------------------------------------------------------


def test_concurrency_config_parsed(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.concurrency.max_total_agents == 5
    assert cfg.concurrency.max_per_goal == 1


# ---------------------------------------------------------------------------
# BudgetConfig
# ---------------------------------------------------------------------------


def test_budget_config_parsed(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.budget.daily_limit_usd == 30.0
    assert cfg.budget.per_task_limit_usd == 5.0
    assert cfg.budget.alert_threshold_pct == 80


# ---------------------------------------------------------------------------
# AgentConfig
# ---------------------------------------------------------------------------


def test_agent_config_parsed(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.agent.default_allowed_tools == ["Read", "Write", "Bash"]
    assert cfg.agent.default_max_turns == 20
    assert cfg.agent.stall_timeout_ms == 300_000
    assert cfg.agent.turn_timeout_ms == 3_600_000


# ---------------------------------------------------------------------------
# LoggingConfig
# ---------------------------------------------------------------------------


def test_logging_config_parsed(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.logging.level == "info"
    assert cfg.logging.file == "./logs/maestro.log"


# ---------------------------------------------------------------------------
# Goals removed from config (now in DB)
# ---------------------------------------------------------------------------


def test_goals_not_in_config(tmp_path: pathlib.Path) -> None:
    """Goals are no longer parsed from config — they live in the DB now."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)
    assert not hasattr(cfg, "goals")


# ---------------------------------------------------------------------------
# Resources parsing
# ---------------------------------------------------------------------------


def test_resources_parsed(tmp_path: pathlib.Path) -> None:
    """resources should be parsed into dict[resource_type, dict[profile_name, ResourceProfile]]."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert "chrome-profiles" in cfg.resources
    chrome_profiles = cfg.resources["chrome-profiles"]

    assert "threads" in chrome_profiles
    threads_profile = chrome_profiles["threads"]

    assert isinstance(threads_profile, ResourceProfile)
    assert threads_profile.max_concurrent == 1
    assert threads_profile.path == "./chrome-profiles/threads"


def test_resources_empty_when_omitted(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.resources == {}


# ---------------------------------------------------------------------------
# AssetsConfig
# ---------------------------------------------------------------------------


def test_assets_config_defaults() -> None:
    cfg = AssetsConfig()
    assert cfg.default_ttl["post"] is None
    assert cfg.default_ttl["engage"] == 30
    assert cfg.default_ttl["research"] == 7
    assert cfg.cleanup_interval_ms == 86_400_000
    assert cfg.archive_grace_days == 30
    assert cfg.gemini_api_key == ""


def test_assets_config_from_yaml(tmp_path: pathlib.Path) -> None:
    yaml_content = """\
project:
  name: test
  store_path: ./test.db
assets:
  default_ttl:
    post: null
    engage: 14
  cleanup_interval_ms: 3600000
"""
    cfg_path = tmp_path / "test.yaml"
    cfg_path.write_text(yaml_content)
    cfg = load_config(str(cfg_path))
    assert cfg.assets.default_ttl["engage"] == 14
    assert cfg.assets.cleanup_interval_ms == 3_600_000


# ---------------------------------------------------------------------------
# AgentDefinition parsing
# ---------------------------------------------------------------------------


def test_agents_parsed(tmp_path: pathlib.Path) -> None:
    """agents section should be parsed into dict[name, AgentDefinition]."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert "researcher" in cfg.agents
    researcher = cfg.agents["researcher"]
    assert isinstance(researcher, AgentDefinition)
    assert researcher.name == "researcher"
    assert researcher.role == "Research specialist"
    assert researcher.instructions == "Focus on accurate data"
    assert researcher.tools == ["Read", "WebSearch"]
    assert researcher.max_turns == 30
    assert researcher.no_worktree is True


def test_agents_partial_definition(tmp_path: pathlib.Path) -> None:
    """Agent with only role specified should get defaults for other fields."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert "writer" in cfg.agents
    writer = cfg.agents["writer"]
    assert writer.name == "writer"
    assert writer.role == "Content writer"
    assert writer.instructions == ""
    assert writer.tools == ["Read", "Write", "Bash"]
    assert writer.max_turns == 50
    assert writer.no_worktree is False


def test_agents_empty_when_omitted(tmp_path: pathlib.Path) -> None:
    """agents should default to empty dict when omitted."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.agents == {}


# ---------------------------------------------------------------------------
# ConcurrencyConfig – max_per_goal
# ---------------------------------------------------------------------------


def test_max_per_goal_parsed(tmp_path: pathlib.Path) -> None:
    """max_per_goal should be parsed from concurrency section."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.concurrency.max_per_goal == 1


def test_max_per_goal_default(tmp_path: pathlib.Path) -> None:
    """max_per_goal should default to 1 when not specified."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(MINIMAL_CONFIG)
    cfg = load_config(cfg_file)

    assert cfg.concurrency.max_per_goal == 1


# ---------------------------------------------------------------------------
# permission_mode
# ---------------------------------------------------------------------------


def test_agent_config_permission_mode_default(tmp_path: pathlib.Path) -> None:
    """Missing permission_mode defaults to 'bypass'."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)
    assert cfg.agent.permission_mode == "bypass"


def test_agent_config_permission_mode_explicit(tmp_path: pathlib.Path) -> None:
    """Explicit permission_mode is parsed."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(
        "project:\n  name: test\nagent:\n  permission_mode: restricted\n"
    )
    cfg = load_config(cfg_file)
    assert cfg.agent.permission_mode == "restricted"


def test_agent_definition_permission_mode_inherit(tmp_path: pathlib.Path) -> None:
    """Agent without permission_mode gets empty string (inherit)."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(
        "project:\n  name: test\nagents:\n  default:\n    max_turns: 10\n"
    )
    cfg = load_config(cfg_file)
    assert cfg.agents["default"].permission_mode == ""


def test_agent_definition_permission_mode_override(tmp_path: pathlib.Path) -> None:
    """Agent with explicit permission_mode is parsed."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(
        "project:\n  name: test\nagents:\n  sandbox:\n    permission_mode: restricted\n    tools: [Read]\n"
    )
    cfg = load_config(cfg_file)
    assert cfg.agents["sandbox"].permission_mode == "restricted"
