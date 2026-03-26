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
    scheduler_interval_ms: int = 10_000


@dataclass
class ConcurrencyConfig:
    max_total_agents: int = 5
    max_per_goal: int = 1


@dataclass
class BudgetConfig:
    daily_limit_usd: float = 30.0
    per_task_limit_usd: float = 5.0
    alert_threshold_pct: int = 80


@dataclass
class AgentDefinition:
    """Defines a named agent with role, instructions, tools, and behavior."""

    name: str = "default"
    role: str = ""
    instructions: str = ""
    tools: list[str] = field(default_factory=lambda: ["Read", "Write", "Bash"])
    max_turns: int = 50
    no_worktree: bool = False
    permission_mode: str = ""  # empty = inherit from global AgentConfig


@dataclass
class AgentConfig:
    permission_mode: str = "bypass"
    default_allowed_tools: list[str] = field(
        default_factory=lambda: ["Read", "Write", "Bash"]
    )
    default_max_turns: int = 20
    stall_timeout_ms: int = 300_000
    turn_timeout_ms: int = 3_600_000
    max_review_rounds: int = 3


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
class ResourceProfile:
    max_concurrent: int = 1
    path: str = ""


@dataclass
class AssetsConfig:
    """에셋 파이프라인 설정."""

    default_ttl: dict[str, int | None] = field(
        default_factory=lambda: {
            "post": None,
            "engage": 30,
            "research": 7,
            "image": None,
            "video": None,
            "audio": None,
            "document": None,
        }
    )
    cleanup_interval_ms: int = 86_400_000
    archive_grace_days: int = 30
    gemini_api_key: str = ""


@dataclass
class MaestroConfig:
    project: ProjectConfig
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    concurrency: ConcurrencyConfig = field(default_factory=ConcurrencyConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    assets: AssetsConfig = field(default_factory=AssetsConfig)
    agents: dict[str, AgentDefinition] = field(default_factory=dict)
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
        scheduler_interval_ms=data.get("scheduler_interval_ms", 10_000),
    )


def _parse_concurrency(data: dict[str, Any]) -> ConcurrencyConfig:
    return ConcurrencyConfig(
        max_total_agents=data.get("max_total_agents", 5),
        max_per_goal=data.get("max_per_goal", 1),
    )


def _parse_budget(data: dict[str, Any]) -> BudgetConfig:
    return BudgetConfig(
        daily_limit_usd=float(data.get("daily_limit_usd", 30.0)),
        per_task_limit_usd=float(data.get("per_task_limit_usd", 5.0)),
        alert_threshold_pct=int(data.get("alert_threshold_pct", 80)),
    )


def _parse_agent(data: dict[str, Any]) -> AgentConfig:
    return AgentConfig(
        permission_mode=str(data.get("permission_mode", "bypass")),
        default_allowed_tools=list(
            data.get("default_allowed_tools", ["Read", "Write", "Bash"])
        ),
        default_max_turns=int(data.get("default_max_turns", 20)),
        stall_timeout_ms=int(data.get("stall_timeout_ms", 300_000)),
        turn_timeout_ms=int(data.get("turn_timeout_ms", 3_600_000)),
        max_review_rounds=int(data.get("max_review_rounds", 3)),
    )


def _parse_logging(data: dict[str, Any]) -> LoggingConfig:
    return LoggingConfig(
        level=data.get("level", "info"),
        file=data.get("file", "./logs/maestro.log"),
    )


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


def _parse_assets(data: dict[str, Any]) -> AssetsConfig:
    defaults = AssetsConfig()
    ttl_raw = data.get("default_ttl")
    if ttl_raw and isinstance(ttl_raw, dict):
        merged_ttl = dict(defaults.default_ttl)
        merged_ttl.update(ttl_raw)
        ttl = merged_ttl
    else:
        ttl = dict(defaults.default_ttl)
    return AssetsConfig(
        default_ttl=ttl,
        cleanup_interval_ms=int(
            data.get("cleanup_interval_ms", defaults.cleanup_interval_ms)
        ),
        archive_grace_days=int(
            data.get("archive_grace_days", defaults.archive_grace_days)
        ),
        gemini_api_key=str(data.get("gemini_api_key", "")),
    )


def _parse_agents(data: dict[str, Any]) -> dict[str, AgentDefinition]:
    """Parse the agents section.

    Expected shape::

        agents:
          researcher:
            role: "Research specialist"
            instructions: "Focus on finding accurate data"
            tools: ["Read", "WebSearch"]
            max_turns: 30
            no_worktree: true

    Returns ``dict[agent_name, AgentDefinition]``.
    """
    result: dict[str, AgentDefinition] = {}
    for agent_name, agent_data in data.items():
        if not isinstance(agent_data, dict):
            continue
        default = AgentDefinition()
        result[agent_name] = AgentDefinition(
            name=agent_name,
            role=str(agent_data.get("role", default.role)),
            instructions=str(agent_data.get("instructions", default.instructions)),
            tools=list(agent_data.get("tools", default.tools)),
            max_turns=int(agent_data.get("max_turns", default.max_turns)),
            no_worktree=bool(agent_data.get("no_worktree", default.no_worktree)),
            permission_mode=str(agent_data.get("permission_mode", "")),
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
    integrations = _parse_integrations(data.get("integrations") or {})
    resources = _parse_resources(data.get("resources") or {})
    agents = _parse_agents(data.get("agents") or {})
    assets_raw = data.get("assets", {})
    assets = _parse_assets(assets_raw or {})
    if not assets.gemini_api_key:
        assets.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

    return MaestroConfig(
        project=project,
        daemon=daemon,
        concurrency=concurrency,
        budget=budget,
        agent=agent,
        logging=logging_cfg,
        integrations=integrations,
        assets=assets,
        agents=agents,
        resources=resources,
    )
