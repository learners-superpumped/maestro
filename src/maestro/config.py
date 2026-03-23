"""Configuration loading for the Maestro orchestration daemon.

Reads a YAML file, applies defaults, performs $ENV_VAR substitution, and
returns a fully-typed MaestroConfig dataclass.
"""

from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Typed dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ProjectConfig:
    name: str
    store_path: str = "./store/maestro.db"


@dataclass
class DaemonConfig:
    planner_interval_ms: int = 300_000
    dispatcher_interval_ms: int = 10_000
    reconcile_interval_ms: int = 30_000


@dataclass
class ConcurrencyConfig:
    max_total_agents: int = 5
    max_per_workspace: int = 1


@dataclass
class BudgetConfig:
    daily_limit_usd: float = 30.0
    per_task_limit_usd: float = 5.0
    alert_threshold_pct: int = 80


@dataclass
class AgentConfig:
    default_allowed_tools: list[str] = field(default_factory=lambda: ["Read", "Write", "Bash"])
    default_max_turns: int = 20
    stall_timeout_ms: int = 300_000
    turn_timeout_ms: int = 3_600_000


@dataclass
class LoggingConfig:
    level: str = "info"
    file: str = "./logs/maestro.log"


@dataclass
class SlackConfig:
    webhook_url: str | None = None


@dataclass
class LinearConfig:
    api_key: str | None = None
    project_slug: str | None = None


@dataclass
class IntegrationsConfig:
    slack: SlackConfig = field(default_factory=SlackConfig)
    linear: LinearConfig = field(default_factory=LinearConfig)


@dataclass
class ScheduleEntry:
    name: str
    workspace: str
    task_type: str
    approval_level: int = 0
    cron: str | None = None
    interval_ms: int | None = None


@dataclass
class GoalEntry:
    id: str
    description: str
    workspace: str
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceProfile:
    max_concurrent: int = 1
    path: str = ""


@dataclass
class MaestroConfig:
    project: ProjectConfig
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    schedules: list[ScheduleEntry] = field(default_factory=list)
    goals: list[GoalEntry] = field(default_factory=list)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    # dict[resource_type, dict[profile_name, ResourceProfile]]
    resources: dict[str, dict[str, ResourceProfile]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Environment variable substitution
# ---------------------------------------------------------------------------

_ENV_VAR_RE = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def _substitute_env_vars(value: Any) -> Any:
    """Recursively walk YAML-parsed data and substitute $VAR tokens in strings.

    Variables that are not set in the environment are left unchanged.
    """
    if isinstance(value, str):
        return _ENV_VAR_RE.sub(
            lambda m: os.environ.get(m.group(1), m.group(0)),
            value,
        )
    if isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env_vars(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_project(data: dict[str, Any]) -> ProjectConfig:
    return ProjectConfig(
        name=data["name"],
        store_path=data.get("store_path", "./store/maestro.db"),
    )


def _parse_daemon(data: dict[str, Any]) -> DaemonConfig:
    return DaemonConfig(
        planner_interval_ms=data.get("planner_interval_ms", 300_000),
        dispatcher_interval_ms=data.get("dispatcher_interval_ms", 10_000),
        reconcile_interval_ms=data.get("reconcile_interval_ms", 30_000),
    )


def _parse_concurrency(data: dict[str, Any]) -> ConcurrencyConfig:
    return ConcurrencyConfig(
        max_total_agents=data.get("max_total_agents", 5),
        max_per_workspace=data.get("max_per_workspace", 1),
    )


def _parse_budget(data: dict[str, Any]) -> BudgetConfig:
    return BudgetConfig(
        daily_limit_usd=float(data.get("daily_limit_usd", 30.0)),
        per_task_limit_usd=float(data.get("per_task_limit_usd", 5.0)),
        alert_threshold_pct=int(data.get("alert_threshold_pct", 80)),
    )


def _parse_agent(data: dict[str, Any]) -> AgentConfig:
    return AgentConfig(
        default_allowed_tools=list(data.get("default_allowed_tools", ["Read", "Write", "Bash"])),
        default_max_turns=int(data.get("default_max_turns", 20)),
        stall_timeout_ms=int(data.get("stall_timeout_ms", 300_000)),
        turn_timeout_ms=int(data.get("turn_timeout_ms", 3_600_000)),
    )


def _parse_logging(data: dict[str, Any]) -> LoggingConfig:
    return LoggingConfig(
        level=data.get("level", "info"),
        file=data.get("file", "./logs/maestro.log"),
    )


def _parse_schedules(items: list[dict[str, Any]]) -> list[ScheduleEntry]:
    entries: list[ScheduleEntry] = []
    for item in items:
        entries.append(
            ScheduleEntry(
                name=item["name"],
                workspace=item["workspace"],
                task_type=item["task_type"],
                approval_level=int(item.get("approval_level", 0)),
                cron=item.get("cron"),
                interval_ms=item.get("interval_ms"),
            )
        )
    return entries


def _parse_goals(items: list[dict[str, Any]]) -> list[GoalEntry]:
    entries: list[GoalEntry] = []
    for item in items:
        entries.append(
            GoalEntry(
                id=item["id"],
                description=item.get("description", ""),
                workspace=item.get("workspace", ""),
                metrics=dict(item.get("metrics") or {}),
            )
        )
    return entries


def _parse_integrations(data: dict[str, Any]) -> IntegrationsConfig:
    slack_data = data.get("slack") or {}
    linear_data = data.get("linear") or {}

    slack = SlackConfig(
        webhook_url=slack_data.get("webhook_url") or None,
    )
    linear = LinearConfig(
        api_key=linear_data.get("api_key") or None,
        project_slug=linear_data.get("project_slug") or None,
    )
    return IntegrationsConfig(slack=slack, linear=linear)


def _parse_resources(
    data: dict[str, Any],
) -> dict[str, dict[str, ResourceProfile]]:
    """Parse the resources section.

    Expected shape::

        resources:
          chrome-profiles:
            threads:
              max_concurrent: 1
              path: ./chrome-profiles/threads

    Returns ``dict[resource_type, dict[profile_name, ResourceProfile]]``.
    """
    result: dict[str, dict[str, ResourceProfile]] = {}
    for resource_type, profiles in data.items():
        if not isinstance(profiles, dict):
            continue
        result[resource_type] = {}
        for profile_name, profile_data in profiles.items():
            if not isinstance(profile_data, dict):
                continue
            result[resource_type][profile_name] = ResourceProfile(
                max_concurrent=int(profile_data.get("max_concurrent", 1)),
                path=str(profile_data.get("path", "")),
            )
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: pathlib.Path | str) -> MaestroConfig:
    """Load and parse a Maestro YAML config file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        A fully-populated :class:`MaestroConfig` instance.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ValueError: If required fields (e.g. ``project.name``) are missing.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_text = path.read_text(encoding="utf-8")
    raw_data: dict[str, Any] = yaml.safe_load(raw_text) or {}

    # Apply environment variable substitution across the whole structure
    data: dict[str, Any] = _substitute_env_vars(raw_data)

    # --- required section ---
    project_data = data.get("project")
    if not project_data or not isinstance(project_data, dict):
        raise ValueError("Config is missing required 'project' section with 'name'.")
    project = _parse_project(project_data)

    # --- optional sections with defaults ---
    daemon = _parse_daemon(data.get("daemon") or {})
    concurrency = _parse_concurrency(data.get("concurrency") or {})
    budget = _parse_budget(data.get("budget") or {})
    agent = _parse_agent(data.get("agent") or {})
    logging_cfg = _parse_logging(data.get("logging") or {})
    schedules = _parse_schedules(data.get("schedules") or [])
    goals = _parse_goals(data.get("goals") or [])
    integrations = _parse_integrations(data.get("integrations") or {})
    resources = _parse_resources(data.get("resources") or {})

    return MaestroConfig(
        project=project,
        daemon=daemon,
        concurrency=concurrency,
        budget=budget,
        agent=agent,
        logging=logging_cfg,
        schedules=schedules,
        goals=goals,
        integrations=integrations,
        resources=resources,
    )
