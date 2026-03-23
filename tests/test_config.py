"""Tests for the Maestro configuration system."""

from __future__ import annotations

import os
import pathlib

import pytest
import yaml

from maestro.config import (
    AgentConfig,
    BudgetConfig,
    ConcurrencyConfig,
    DaemonConfig,
    GoalEntry,
    LoggingConfig,
    MaestroConfig,
    ProjectConfig,
    ResourceProfile,
    ScheduleEntry,
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
  max_per_workspace: 1

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
    workspace: sns-threads

schedules:
  - name: threads-daily-post
    cron: "0 9 * * *"
    workspace: sns-threads
    task_type: create_post
    approval_level: 2
  - name: threads-engagement
    interval_ms: 1800000
    workspace: sns-threads
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
    assert cfg.concurrency.max_per_workspace == 1

    # budget defaults
    assert cfg.budget.daily_limit_usd == 30.0
    assert cfg.budget.per_task_limit_usd == 5.0
    assert cfg.budget.alert_threshold_pct == 80

    # agent defaults
    assert cfg.agent.default_max_turns == 20
    assert cfg.agent.stall_timeout_ms == 300_000
    assert cfg.agent.turn_timeout_ms == 3_600_000

    # logging defaults
    assert cfg.logging.level == "info"

    # collections default to empty
    assert cfg.goals == []
    assert cfg.schedules == []
    assert cfg.resources == {}


# ---------------------------------------------------------------------------
# Environment variable substitution
# ---------------------------------------------------------------------------


def test_env_var_substitution(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert cfg.concurrency.max_per_workspace == 1


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
# Schedules parsing
# ---------------------------------------------------------------------------


def test_schedules_parsed(tmp_path: pathlib.Path) -> None:
    """Both cron-based and interval-based schedule entries should parse correctly."""
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert len(cfg.schedules) == 2

    cron_entry = cfg.schedules[0]
    assert isinstance(cron_entry, ScheduleEntry)
    assert cron_entry.name == "threads-daily-post"
    assert cron_entry.cron == "0 9 * * *"
    assert cron_entry.interval_ms is None
    assert cron_entry.workspace == "sns-threads"
    assert cron_entry.task_type == "create_post"
    assert cron_entry.approval_level == 2

    interval_entry = cfg.schedules[1]
    assert isinstance(interval_entry, ScheduleEntry)
    assert interval_entry.name == "threads-engagement"
    assert interval_entry.cron is None
    assert interval_entry.interval_ms == 1_800_000
    assert interval_entry.workspace == "sns-threads"
    assert interval_entry.task_type == "check_and_engage"
    assert interval_entry.approval_level == 1


# ---------------------------------------------------------------------------
# Goals parsing
# ---------------------------------------------------------------------------


def test_goals_parsed(tmp_path: pathlib.Path) -> None:
    cfg_file = tmp_path / "maestro.yaml"
    cfg_file.write_text(FULL_CONFIG)
    cfg = load_config(cfg_file)

    assert len(cfg.goals) == 1

    goal = cfg.goals[0]
    assert isinstance(goal, GoalEntry)
    assert goal.id == "threads-presence"
    assert goal.description == "Threads brand presence"
    assert goal.workspace == "sns-threads"
    assert goal.metrics == {"post_frequency": "3/week", "engagement_check": "daily"}


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
