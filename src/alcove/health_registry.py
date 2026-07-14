from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from alcove.home import AlcoveHome

if TYPE_CHECKING:
    from alcove.health import HealthModule
    from alcove.health_types import HealthIssue


HealthCheckRunner = Callable[
    ["HealthModule", "HealthCheckContext"],
    "HealthCheckResult",
]


@dataclass(frozen=True)
class HealthCheckContext:
    home: AlcoveHome
    strict: bool = False
    fixture_context: bool = False


@dataclass
class HealthCheckResult:
    issues: list["HealthIssue"] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class HomeHealthCheck:
    """Registered Alcove Home health check.

    HealthModule keeps the public check/fix interface. This registry owns home-check ordering
    and gives each check a result-returning interface, so new Alcove Home modules do not
    widen HealthModule's orchestration method or mutate shared buffers directly.
    """

    name: str
    run: HealthCheckRunner


def home_health_checks() -> list[HomeHealthCheck]:
    return [
        HomeHealthCheck("registered_kbs", _registered_kbs),
        HomeHealthCheck("workspaces", _workspaces),
        HomeHealthCheck("pins", _pins),
        HomeHealthCheck("prompts", _prompts),
        HomeHealthCheck("prompt_quality", _prompt_quality),
        HomeHealthCheck("tasks", _tasks),
        HomeHealthCheck("projects", _projects),
        HomeHealthCheck("mounts", _mounts),
        HomeHealthCheck("connectors", _connectors),
        HomeHealthCheck("connector_sources", _connector_sources),
        HomeHealthCheck("okf_catalog", _okf_catalog),
        HomeHealthCheck("dashboard", _dashboard),
        HomeHealthCheck("publishers", _publishers),
        HomeHealthCheck("radars", _radars),
        HomeHealthCheck("watchers", _watchers),
        HomeHealthCheck("blogs", _blogs),
        HomeHealthCheck("automations", _automations),
        HomeHealthCheck("usage", _usage),
    ]


def required_home_path_names() -> tuple[str, ...]:
    return (
        "pins",
        "prompts",
        "tasks",
        "projects",
        "mounts",
        "connectors",
        "knowledge_bases",
    )


def _registered_kbs(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_registered_kbs(context.home, issues, counts, strict=context.strict)
    return HealthCheckResult(issues=issues, counts=counts)


def _workspaces(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_agent_workspaces(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _pins(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_pins(context.home.paths().pins, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _prompts(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_prompts(context.home.paths().prompts, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _prompt_quality(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_prompt_quality(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _tasks(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_json_store(context.home.paths().tasks / "tasks.json", "tasks", issues, counts)
    health._check_planner_fixture_records(
        context.home.paths().tasks / "tasks.json",
        issues,
        counts,
        fixture_context=context.fixture_context,
    )
    return HealthCheckResult(issues=issues, counts=counts)


def _projects(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_json_store(
        context.home.paths().projects / "projects.json",
        "projects",
        issues,
        counts,
    )
    return HealthCheckResult(issues=issues, counts=counts)


def _mounts(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_mounts(context.home.paths().mounts, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _connectors(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_connectors(context.home.paths().connectors, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _connector_sources(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_connector_sources(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _okf_catalog(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_catalog(context.home.paths().okf, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _dashboard(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_dashboard(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _publishers(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_publishers(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _radars(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_radars(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _watchers(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_watchers(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _blogs(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_blogs(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _automations(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_automations(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)


def _usage(
    health: "HealthModule",
    context: HealthCheckContext,
) -> HealthCheckResult:
    issues: list["HealthIssue"] = []
    counts: dict[str, int] = {}
    health._check_usage_stats(context.home, issues, counts)
    return HealthCheckResult(issues=issues, counts=counts)
