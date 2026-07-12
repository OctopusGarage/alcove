from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Sequence

from alcove.ai_eval_connectors import (
    apple_notes_item_sample,
    apple_notes_public_fixture_sample,
    connector_failure_samples_for_eval,
    real_integration_summary_for_eval,
)
from alcove.ai_eval_mcp import (
    mcp_matrix_for_eval,
    mcp_tool_descriptions,
    mcp_tool_inventory,
    mcp_toolsets_for_eval,
)
from alcove.ai_eval_packet import (
    compact_packet,
    dashboard_browser_for_eval,
    doctor_for_eval,
    project_health_evidence,
)
from alcove.paths import compact_user_paths_in_text
from alcove.verify_suites import eval_report_paths


PACKET_SCHEMA = "alcove.ai_eval_packet.v1"


@dataclass(frozen=True)
class EvalBundle:
    packet_path: Path
    prompt_path: Path


def build_eval_packet(
    *,
    smoke_root: Path,
    real_home_report: Path,
    real_integrations_dir: Path,
    agent_client_report: Path | None = None,
    mcp_matrix_report: Path | None = None,
    dashboard_browser_report: Path | None = None,
    radar_reports_report: Path | None = None,
    export_restore_report: Path | None = None,
    messy_inbox_report: Path | None = None,
) -> dict[str, Any]:
    return EvalPacketBuilder(
        smoke_root=smoke_root,
        real_home_report=real_home_report,
        real_integrations_dir=real_integrations_dir,
        agent_client_report=agent_client_report,
        mcp_matrix_report=mcp_matrix_report,
        dashboard_browser_report=dashboard_browser_report,
        radar_reports_report=radar_reports_report,
        export_restore_report=export_restore_report,
        messy_inbox_report=messy_inbox_report,
    ).build()


@dataclass(frozen=True)
class EvalPacketBuilder:
    smoke_root: Path
    real_home_report: Path
    real_integrations_dir: Path
    agent_client_report: Path | None = None
    mcp_matrix_report: Path | None = None
    dashboard_browser_report: Path | None = None
    radar_reports_report: Path | None = None
    export_restore_report: Path | None = None
    messy_inbox_report: Path | None = None

    def build(self) -> dict[str, Any]:
        return _build_eval_packet(
            smoke_root=self.smoke_root,
            real_home_report=self.real_home_report,
            real_integrations_dir=self.real_integrations_dir,
            agent_client_report=self.agent_client_report,
            mcp_matrix_report=self.mcp_matrix_report,
            dashboard_browser_report=self.dashboard_browser_report,
            radar_reports_report=self.radar_reports_report,
            export_restore_report=self.export_restore_report,
            messy_inbox_report=self.messy_inbox_report,
        )


def _build_eval_packet(
    *,
    smoke_root: Path,
    real_home_report: Path,
    real_integrations_dir: Path,
    agent_client_report: Path | None = None,
    mcp_matrix_report: Path | None = None,
    dashboard_browser_report: Path | None = None,
    radar_reports_report: Path | None = None,
    export_restore_report: Path | None = None,
    messy_inbox_report: Path | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    smoke_fixtures = smoke_root / "fixtures"

    smoke = {
        "inbox_read": _read_json(smoke_fixtures / "inbox-read.json", warnings),
        "inbox_note": _read_json(smoke_fixtures / "inbox-note.json", warnings),
        "kb_search": _read_json(smoke_fixtures / "kb-search.json", warnings),
        "cleanup_search": _read_json(smoke_fixtures / "cleanup-search.json", warnings),
        "cleanup_delete_preview": _read_json(
            smoke_fixtures / "cleanup-delete-preview.json", warnings
        ),
        "cleanup_delete_confirm": _read_json(
            smoke_fixtures / "cleanup-delete-confirm.json", warnings
        ),
        "cleanup_search_after_delete": _read_json(
            smoke_fixtures / "cleanup-search-after-delete.json", warnings
        ),
        "cleanup_search_deleted": _read_json(
            smoke_fixtures / "cleanup-search-deleted.json", warnings
        ),
        "pin_search": _read_json(smoke_fixtures / "pin-search.json", warnings),
        "publisher_init": _read_json(smoke_fixtures / "publisher-init.json", warnings),
        "publisher_run": _read_json(smoke_fixtures / "publisher-run.json", warnings),
        "publisher_run_unchanged": _read_json(
            smoke_fixtures / "publisher-run-unchanged.json", warnings
        ),
        "publisher_render_quality": _read_json(
            smoke_fixtures / "publisher-render-quality.json", warnings
        ),
        "prompt_search": _read_json(smoke_fixtures / "prompt-search.json", warnings),
        "project_add": _read_json(smoke_fixtures / "project-add.json", warnings),
        "project_find": _read_json(smoke_fixtures / "project-find.json", warnings),
        "task_add": _read_json(smoke_fixtures / "task-add.json", warnings),
        "idea_add": _read_json(smoke_fixtures / "idea-add.json", warnings),
        "routine_add": _read_json(smoke_fixtures / "routine-add.json", warnings),
        "task_digest": _read_json(smoke_fixtures / "task-digest.json", warnings),
        "mount_scan": _read_json(smoke_fixtures / "mount-scan.json", warnings),
        "okf_catalog": _read_json(smoke_fixtures / "okf-catalog.json", warnings),
        "apple_notes_search": _read_json(smoke_fixtures / "apple-notes-search.json", warnings),
        "apple_notes_fetch": _read_json(smoke_fixtures / "apple-notes-fetch.json", warnings),
        "chrome_bookmarks_search": _read_json(
            smoke_fixtures / "chrome-bookmarks-search.json", warnings
        ),
        "multilingual_knowledge_search": _read_json(
            smoke_fixtures / "multilingual-knowledge-search.json", warnings
        ),
        "multilingual_todo_search": _read_json(
            smoke_fixtures / "multilingual-todo-search.json", warnings
        ),
        "intent_routing_examples": _read_json(
            smoke_fixtures / "intent-routing-examples.json", warnings
        ),
        "connector_fetch": _read_json(smoke_fixtures / "connector-fetch.json", warnings),
        "blog_monitor": _read_json(smoke_fixtures / "blog-monitor-smoke.json", warnings),
        "radar_list": _read_json(smoke_fixtures / "radar-list.json", warnings),
        "radar_run": _read_json(smoke_fixtures / "radar-run.json", warnings),
        "radar_status": _read_json(smoke_fixtures / "radar-status.json", warnings),
        "radar_import_social_radar": _read_json(
            smoke_fixtures / "radar-import-social-radar.json", warnings
        ),
        "link_source": _read_json(smoke_fixtures / "link-source.json", warnings),
        "dashboard_build": _read_json(smoke_fixtures / "dashboard-build.json", warnings),
        "dashboard_render": _read_json(smoke_fixtures / "dashboard-render.json", warnings),
        "dashboard_snapshot": _read_json(
            smoke_root / "home" / "dashboard" / "snapshot.json", warnings
        ),
        "validate": _read_json(smoke_fixtures / "validate.json", warnings),
        "health": _read_json(smoke_fixtures / "health.json", warnings),
        "gardener": _read_json(smoke_fixtures / "gardener.json", warnings),
        "export_all": _read_json(smoke_fixtures / "export-all.json", warnings),
        "doctor": doctor_for_eval(_read_json(smoke_fixtures / "doctor.json", warnings)),
    }
    real_home = _read_json(real_home_report, warnings)
    default_reports = eval_report_paths(real_integrations_dir.parent)
    integrations = {
        "summary": _read_json(real_integrations_dir / "real-integrations-summary.json", warnings),
        "web_inbox_read": _read_json(
            real_integrations_dir / "alcove-inbox-read-clipsmith.json", warnings
        ),
        "ocr_inbox_read": _read_json(
            real_integrations_dir / "alcove-inbox-read-ocr.json", warnings
        ),
        "mcp_stdio": _read_json(real_integrations_dir / "mcp-stdio-report.json", warnings),
        "github_stars_import": _read_json(
            real_integrations_dir / "github-stars-import.json", warnings
        ),
        "github_stars_search": _read_json(
            real_integrations_dir / "github-stars-search.json", warnings
        ),
        "apple_notes_import": _read_json(
            real_integrations_dir / "apple-notes-import-local.json", warnings
        ),
        "apple_notes_search": _read_json(
            real_integrations_dir / "apple-notes-search.json", warnings
        ),
        "apple_notes_fetch": _read_json(real_integrations_dir / "apple-notes-fetch.json", warnings),
        "connector_failure_samples": _read_json(
            real_integrations_dir / "connector-failure-samples.json", warnings
        ),
    }
    agent_client_smoke = _read_json(
        agent_client_report or default_reports["agent_client_report"],
        warnings,
    )
    mcp_matrix = _read_json(
        mcp_matrix_report or default_reports["mcp_matrix_report"],
        warnings,
    )
    mcp_matrix = mcp_matrix_for_eval(mcp_matrix)
    dashboard_browser = _read_json(
        dashboard_browser_report or default_reports["dashboard_browser_report"],
        warnings,
    )
    radar_reports = _read_json(
        radar_reports_report or default_reports["radar_reports_report"],
        warnings,
    )
    export_restore = _read_json(
        export_restore_report or default_reports["export_restore_report"],
        warnings,
    )
    messy_inbox = _read_json(
        messy_inbox_report or default_reports["messy_inbox_report"],
        warnings,
    )

    packet = {
        "schema": PACKET_SCHEMA,
        "purpose": (
            "AI quality evaluation packet for Alcove flows. Deterministic smoke "
            "already checked command success; this packet asks an AI reviewer to "
            "judge usefulness, intent fit, and module consistency."
        ),
        "operating_model": _operating_model(),
        "warnings": warnings,
        "evidence": {
            "smoke": compact_packet(smoke),
            "coverage_boundaries": compact_packet(_coverage_boundaries()),
            "real_home": compact_packet(real_home),
            "real_integrations": compact_packet(real_integration_summary_for_eval(integrations)),
            "integration_samples": compact_packet(
                {
                    "web_inbox_read": integrations["web_inbox_read"],
                    "ocr_inbox_read": integrations["ocr_inbox_read"],
                    "mcp_stdio": integrations["mcp_stdio"],
                    "mcp_tool_inventory": mcp_tool_inventory(),
                    "mcp_toolsets": mcp_toolsets_for_eval(),
                    "mcp_tool_descriptions": mcp_tool_descriptions(warnings),
                    "github_stars_import": integrations["github_stars_import"],
                    "apple_notes_import": integrations["apple_notes_import"],
                    "apple_notes_item_sample": apple_notes_item_sample(
                        integrations["apple_notes_search"],
                        integrations["apple_notes_fetch"],
                    ),
                    "apple_notes_public_fixture_sample": apple_notes_public_fixture_sample(
                        smoke["apple_notes_search"],
                        smoke["apple_notes_fetch"],
                    ),
                    "connector_failure_samples": connector_failure_samples_for_eval(
                        integrations["connector_failure_samples"]
                    ),
                }
            ),
            "project_health": compact_packet(
                project_health_evidence(real_integrations_dir.parent / "check.log", warnings)
            ),
            "agent_client_smoke": compact_packet(agent_client_smoke),
            "mcp_matrix": compact_packet(mcp_matrix),
            "dashboard_browser": compact_packet(dashboard_browser_for_eval(dashboard_browser)),
            "radar_reports": compact_packet(_radar_reports_for_eval(radar_reports)),
            "export_restore": compact_packet(export_restore),
            "messy_inbox": compact_packet(messy_inbox),
            "agent_entries": compact_packet(
                _agent_entry_evidence(smoke_root, warnings, agent_client_smoke),
                max_string=12000,
            ),
        },
        "modules": _modules(),
        "review_rules": [
            "Treat deterministic pass/fail as already verified; focus on AI/user quality.",
            "Flag confusing user-facing wording, missing source context, weak summaries, bad routing, and hidden useful content.",
            "Prefer concrete module/file/command references over generic criticism.",
            "Treat search results as candidate discovery, not final truth; broad or ambiguous knowledge questions should continue with AI-led investigation over OKF indexes, source refs, mount refs, connector fetches, and local files.",
            "Treat durable writes as governed operations; user-facing mutations should go through Alcove CLI/MCP write tools, with direct file edits reserved for repair fallback plus validation or index refresh.",
            "Do not propose broad rewrites unless a module boundary is causing the problem.",
        ],
    }
    return packet


def _operating_model() -> dict[str, Any]:
    return {
        "read_path": {
            "principle": "AI-led investigation over structured local memory.",
            "search_role": "alcove search and alcove_search return candidate leads, not final answers.",
            "follow_up_evidence": [
                "OKF domain/topic/tag/index pages",
                "global OKF catalog under ~/.alcove/okf",
                "candidate record paths",
                "source refs and archive provenance",
                "mount refs and local files",
                "connector lazy-fetch details",
                "full pin, prompt, task, and project records",
            ],
        },
        "write_path": {
            "principle": "Governed writes through Alcove CLI/MCP mutation tools.",
            "fallback": (
                "Direct file edits are repair-only fallbacks and should be followed by "
                "validation, refresh, scan, or index rebuild commands."
            ),
        },
    }


def _coverage_boundaries() -> dict[str, Any]:
    return {
        "blog_monitor": {
            "deterministic_eval_scope": [
                "fixture-backed discovery success",
                "capture-to-managed-KB inbox write",
                "summary file presence",
                "structured Telegram/Feishu notification contracts",
                "structured failure alert with source_id, stage, error, and retry command",
                "Hub routing instruction for active checks through alcove blog check",
            ],
            "release_grade_external_checks": [
                "run alcove blog check against the user's configured Playwright sources",
                "inspect generated inbox bundles and notification deliveries",
                "run through launchd/service tick when scheduler wiring changes",
            ],
            "reason": (
                "Live blog sites are unstable external dependencies; deterministic AI eval "
                "keeps behavior contract coverage in-repo and reserves live discovery for "
                "release-grade or user-data-specific checks."
            ),
        },
        "agent_entries": {
            "default_eval_scope": [
                "generated Hub and managed-KB entry files",
                "MCP stdio client list/call behavior",
                "global-lite install plan rendering",
            ],
            "release_grade_cli_probe": (
                "ALCOVE_AGENT_CLIENT_SMOKE_CODEX=1 "
                "ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE=1 scripts/smoke-agent-clients.sh"
            ),
            "reason": (
                "Codex and Claude CLI probes are higher-cost checks, so the default eval "
                "records whether they were enabled and the release-grade command to run."
            ),
        },
    }


def _agent_entry_evidence(
    smoke_root: Path,
    warnings: list[str],
    agent_client_smoke: Any,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    kb_root = _agent_entry_kb_root(smoke_root, warnings)
    agent_hub = _agent_client_entry_root(agent_client_smoke, "hub")
    agent_kb = _agent_client_entry_root(agent_client_smoke, "workspace")
    paths = {
        "codex_smoke_skill": [repo_root / ".agents" / "skills" / "alcove-smoke" / "SKILL.md"],
        "claude_smoke_command": [repo_root / ".claude" / "commands" / "smoke.md"],
        "claude_smoke_real_home_command": [
            repo_root / ".claude" / "commands" / "smoke-real-home.md"
        ],
        "claude_smoke_real_integrations_command": [
            repo_root / ".claude" / "commands" / "smoke-real-integrations.md"
        ],
        "claude_eval_ai_command": [repo_root / ".claude" / "commands" / "eval-ai.md"],
        "claude_smoke_eval_runner_agent": [
            repo_root / ".claude" / "agents" / "smoke-eval-runner.md"
        ],
        "hub_agents": _entry_candidates(smoke_root / "hub", agent_hub, "AGENTS.md"),
        "hub_claude": _entry_candidates(smoke_root / "hub", agent_hub, "CLAUDE.md"),
        "hub_codex_skill": _entry_candidates(
            smoke_root / "hub",
            agent_hub,
            ".agents/skills/alcove-hub/SKILL.md",
        ),
        "kb_agents": _entry_candidates(kb_root, agent_kb, "AGENTS.md"),
        "kb_claude": _entry_candidates(kb_root, agent_kb, "CLAUDE.md"),
        "kb_codex_skill": _entry_candidates(kb_root, agent_kb, ".agents/skills/alcove-kb/SKILL.md"),
        "kb_notes_search": _entry_candidates(
            kb_root,
            agent_kb,
            ".agents/skills/notes-search/SKILL.md",
        ),
        "kb_social_post_manager": _entry_candidates(
            kb_root,
            agent_kb,
            ".agents/skills/social_post_manager/SKILL.md",
        ),
        "claude_inbox_peek": _entry_candidates(
            kb_root,
            agent_kb,
            ".claude/commands/inbox-peek.md",
        ),
    }
    resolved_paths = {name: _first_existing_path(candidates) for name, candidates in paths.items()}
    evidence: dict[str, Any] = {
        name: _read_first_text(name, candidates, warnings) for name, candidates in paths.items()
    }
    evidence["managed_kb_entry_root"] = compact_user_paths_in_text(
        str(_first_existing_path([kb_root, agent_kb]) or kb_root)
    )
    evidence["skill_availability"] = {
        name: {
            "path": compact_user_paths_in_text(str(resolved_paths[name] or paths[name][0])),
            "exists": resolved_paths[name] is not None,
        }
        for name in paths
        if name.endswith("_skill") or name in {"kb_notes_search", "kb_social_post_manager"}
    }
    return evidence


def _entry_candidates(
    primary_root: Path, fallback_root: Path | None, relative_path: str
) -> list[Path]:
    candidates = [primary_root / relative_path]
    if fallback_root is not None:
        candidates.append(fallback_root / relative_path)
    return candidates


def _agent_client_entry_root(agent_client_smoke: Any, key: str) -> Path | None:
    if not isinstance(agent_client_smoke, dict):
        return None
    raw = str(agent_client_smoke.get(key) or "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _first_existing_path(candidates: Sequence[Path | None]) -> Path | None:
    for path in candidates:
        if path is not None and path.is_file():
            return path
        if path is not None and path.is_dir():
            return path
    return None


def _read_first_text(name: str, candidates: list[Path], warnings: list[str]) -> str:
    path = _first_existing_path(candidates)
    if path is None or not path.is_file():
        warnings.append(f"missing artifact: {name}")
        return ""
    return path.read_text(encoding="utf-8")


def _agent_entry_kb_root(smoke_root: Path, warnings: list[str]) -> Path:
    kb_add_path = smoke_root / "fixtures" / "kb-add.json"
    kb_add: Any = None
    if kb_add_path.is_file():
        try:
            kb_add = json.loads(kb_add_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append(f"invalid json artifact: {kb_add_path.name}: {exc}")
    if isinstance(kb_add, dict):
        kb = kb_add.get("knowledge_base")
        if isinstance(kb, dict):
            name = str(kb.get("name") or "").strip()
            if name:
                named_root = smoke_root / name
                if named_root.exists():
                    return named_root

    for child in sorted(smoke_root.iterdir() if smoke_root.exists() else []):
        if child.name in {"hub", "home", "fixtures", "export"}:
            continue
        if (child / ".alcove" / "config.yml").is_file():
            return child
    return smoke_root / "research_notes"


def _radar_reports_for_eval(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {"status": "missing", "reason": "radar report smoke artifact is not a mapping"}
    checks_value = report.get("checks")
    checks: list[Any] = checks_value if isinstance(checks_value, list) else []
    visual_summaries_value = report.get("visual_summaries")
    visual_summaries: list[Any] = (
        visual_summaries_value if isinstance(visual_summaries_value, list) else []
    )
    failed = [
        check
        for check in checks
        if isinstance(check, dict) and str(check.get("status") or "") == "failed"
    ]
    report_excerpts = []
    ai_notification_contracts = []
    for check in checks:
        if not isinstance(check, dict) or str(check.get("status") or "") != "passed":
            continue
        name = str(check.get("name") or "")
        detail = str(check.get("detail") or "")
        if not detail:
            continue
        if name.endswith("_ai_notify_contract"):
            ai_notification_contracts.append(
                {
                    "check": name,
                    "status": str(check.get("status") or ""),
                    "detail": detail[:1600],
                }
            )
        if name.endswith("_brief") or name.endswith("_enough_signals"):
            report_excerpts.append({"check": name, "excerpt": detail[:1600]})
    return {
        "status": report.get("status"),
        "radars": report.get("radars"),
        "failed_checks": failed[:10],
        "check_count": len(checks),
        "report_excerpts": report_excerpts[:8],
        "ai_notification_contracts": ai_notification_contracts[:8],
        "visual_summaries": visual_summaries[:12],
        "screenshots": report.get("screenshots"),
    }


def build_eval_bundle(
    *,
    output_dir: Path,
    smoke_root: Path,
    real_home_report: Path,
    real_integrations_dir: Path,
    agent_client_report: Path | None = None,
    mcp_matrix_report: Path | None = None,
    dashboard_browser_report: Path | None = None,
    radar_reports_report: Path | None = None,
    export_restore_report: Path | None = None,
    messy_inbox_report: Path | None = None,
) -> EvalBundle:
    output_dir.mkdir(parents=True, exist_ok=True)
    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home_report,
        real_integrations_dir=real_integrations_dir,
        agent_client_report=agent_client_report,
        mcp_matrix_report=mcp_matrix_report,
        dashboard_browser_report=dashboard_browser_report,
        radar_reports_report=radar_reports_report,
        export_restore_report=export_restore_report,
        messy_inbox_report=messy_inbox_report,
    )
    packet_path = output_dir / "ai-eval-packet.json"
    packet_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    prompt_path = output_dir / "ai-eval-prompt.md"
    prompt_path.write_text(_reviewer_prompt(packet_path, packet), encoding="utf-8")
    return EvalBundle(packet_path=packet_path, prompt_path=prompt_path)


def _modules() -> list[dict[str, Any]]:
    return [
        {
            "id": "capture_inbox",
            "scope": "Clipsmith capture, manual inbox, OCR bundle, messy bundle fixtures, inbox read surface.",
            "ai_quality_questions": [
                "Can an agent see enough source, title, content, and OCR text to summarize without losing evidence?",
                "Is OCR content surfaced when summary/post files also exist?",
                "Would a user understand what to archive, note, delete, or defer from this inbox payload?",
                "Do messy inbox fixtures still expose warnings, truncation, missing summaries, and deduped OCR clearly enough for review?",
            ],
        },
        {
            "id": "knowledge_okf",
            "scope": "OKF Source/Concept writes, note flow, search, link-source promotion.",
            "ai_quality_questions": [
                "Does the archived/note output preserve source provenance and user judgement fields?",
                "Are topic, tag, summary, and source-ref surfaces adequate for later AI retrieval?",
                "Does linked external evidence become a useful OKF Source rather than an opaque pointer?",
                "Do agent entries make clear that search is candidate discovery and complex OKF questions need AI-led investigation over local evidence?",
                "Does search-driven cleanup expose lifecycle dates, require preview/confirmation, hide deleted records from default search, and preserve deleted audit search?",
                "Does the global OKF catalog give agents a useful Markdown entry point across managed KBs, global memory, mounts, and connectors?",
                "Are OKF mutations routed through governed CLI/MCP write tools rather than ad hoc file edits?",
            ],
        },
        {
            "id": "global_memory",
            "scope": "Pins, prompts, projects, tasks, ideas, routines.",
            "ai_quality_questions": [
                "Are pins/prompts/tasks represented as user-facing memory rather than internal implementation records?",
                "Can an agent distinguish reference pins from todo/practice pins and concrete tasks?",
                "Are project aliases and prompt search results specific enough to route user intent?",
                "Do multilingual save/search examples route Chinese user wording to the expected governed pin/task/search flows?",
                "Do pin, prompt, task, and project writes use governed tools while preserving full records for follow-up inspection?",
                "Is the planner digest readable as a notification: no repeated title, no raw internal ids in the message body, clear section spacing, and enough detail for the user to act?",
            ],
        },
        {
            "id": "external_indexes",
            "scope": "Mounts, GitHub Stars, Apple Notes, Chrome Bookmarks, connector fetch, connector freshness.",
            "ai_quality_questions": [
                "Are external index results searchable with enough title/source/context to be useful?",
                "Do connector rows expose freshness and counts without leaking irrelevant local paths?",
                "Can an agent decide when to lazy-fetch or link a connector/mount item?",
                "Do connector and mount flows support AI-led follow-up from a search hit into fetched or local evidence before synthesis?",
                "Are connector permission, network, or malformed-export failures represented as controlled, diagnosable errors?",
            ],
        },
        {
            "id": "blog_monitor",
            "scope": "Scheduled Playwright blog discovery, Clipsmith capture, Telegram notifications, failure attention state, and Hub-triggered manual checks.",
            "ai_quality_questions": [
                "Can a Hub agent route 'check whether monitored blogs updated' to `alcove blog check` rather than stale `service tick`?",
                "Does the failure alert path give enough source id, stage, and error context for an agent-assisted retry?",
                "Are captured article paths, summary files, and notification status clear enough for user-facing reporting?",
                "Is the distinction clear between deterministic scheduled summaries and optional AI/chat summaries?",
                "Does the packet make clear whether blog evidence is fixture-backed contract coverage, live browser discovery, or release-time external verification?",
            ],
        },
        {
            "id": "radars",
            "scope": "Generic user-configured information radars, packaged presets, source adapters, reports, service scheduling, and Social Radar migration.",
            "ai_quality_questions": [
                "Are radar categories represented as user definitions rather than hard-coded product modules?",
                "Can an agent discover available radars with `alcove radar list`, then run the user-selected radar without assuming fixed IDs?",
                "Do reports and run status expose enough included counts, source errors, and artifact paths for follow-up review?",
                "Does Social Radar migration preserve historical cache/report evidence while avoiding secrets and old environment data?",
                "Are scheduled radar runs deterministic by default, with optional AI summary and Telegram notification enabled only by explicit definition config or manual flags?",
                "Do radar AI prompts stay radar-specific, and does notification fall back to the deterministic report when AI summary fails?",
            ],
        },
        {
            "id": "publishers",
            "scope": "Generic publisher definitions, pins digest rendering, Apple Notes target identity, unchanged-content skipping, and service scheduling.",
            "ai_quality_questions": [
                "Does the publisher treat Apple Notes as a readable mirror rather than the source of truth?",
                "Are regular and todo pins rendered into distinct, mobile-readable outputs with enough original content preserved?",
                "Are planner, prompt library, and project registry mirrors useful outside the LAN without opening the dashboard?",
                "Does Apple Notes render quality evidence show scannable headings, item/detail blocks, emphasis, spacing, and no plain text dump?",
                "Does state track Apple Notes note ids and content hashes so repeated runs avoid ambiguous title lookup and unnecessary writes?",
                "Are missing, ambiguous, permission, and unavailable Apple Notes failures explicit enough for a user or agent to repair?",
                "Can service tick run due publishers without requiring an open Codex or Claude session?",
            ],
        },
        {
            "id": "dashboard",
            "scope": "Dashboard snapshot, browser smoke, module summaries, pins/tasks/knowledge presentation, activity feed.",
            "ai_quality_questions": [
                "Does the dashboard surface real user data without noisy internal log paths?",
                "Are module names and counts understandable for a personal knowledge cockpit?",
                "Are pins and activity presented in a way that helps repeated review?",
                "Do browser smoke results show route, viewport, search, and console behavior are useful enough for local use?",
            ],
        },
        {
            "id": "mcp_entry",
            "scope": "MCP stdio tools, hub/global/KB agent entries, Claude/Codex commands, and client smoke evidence.",
            "ai_quality_questions": [
                "Would an agent choose the correct entry mode and tool for common user intents?",
                "Are the tools broad enough for workflows without exposing too much internal detail?",
                "Does global-lite expose a genuinely small MCP surface while hub/full and KB modes retain their necessary workflows?",
                "Do MCP tool descriptions prevent treating alcove_search as the final authority for complex questions?",
                "Do MCP write tools clearly represent governed mutations for durable user data?",
                "Do the smoke/eval commands avoid machine-specific paths and risky defaults?",
                "Does client smoke prove an MCP stdio client can list and call representative tools?",
                "Does MCP matrix evidence exercise each major tool group enough to catch routing drift?",
            ],
        },
        {
            "id": "export_health",
            "scope": "Export, restore rehearsal, doctor, validation, gardener, gitleaks/check gates.",
            "ai_quality_questions": [
                "Do health/export results help a user trust backup and migration behavior?",
                "Are reported issues actionable instead of merely structural?",
                "Do gates cover the likely failure classes without hiding real user-data risks?",
                "Does export-restore smoke demonstrate that exported global and KB data are usable in a fresh home/workspace?",
                "Does the health report cover managed KB OKF, global memory indexes, connector/mount derived OKF, and the global OKF catalog?",
            ],
        },
        {
            "id": "agent_entries",
            "scope": "Project-local prompts, Claude commands, Codex skill, AI eval prompt, and optional Codex/Claude CLI probes.",
            "ai_quality_questions": [
                "Can Codex/Claude trigger the right eval level without memorizing scripts?",
                "Are the prompts generic enough for another clone of the repository?",
                "Do the prompts make AI review separate from deterministic smoke checks?",
                "Does client smoke cover installed Hub and managed-KB entry files, and clearly mark optional Codex/Claude CLI probes when they are not enabled?",
            ],
        },
    ]


def _reviewer_prompt(packet_path: Path, packet: dict[str, Any]) -> str:
    module_ids = ", ".join(module["id"] for module in packet["modules"])
    return f"""# Alcove AI Eval Reviewer

Read `{packet_path}` and evaluate Alcove's end-to-end product quality. The
deterministic smoke suites already passed or produced the artifacts in the
packet; your job is to judge whether the system behavior is useful, coherent,
and agent-friendly.

Modules to review: {module_ids}

Return JSON only with this shape:

```json
{{
  "verdict": "pass | needs_fixes",
  "score": 0,
  "module_scores": [
    {{
      "module": "capture_inbox",
      "score": 0
    }}
  ],
  "findings": [
    {{
      "severity": "blocking | should_fix | nice_to_have",
      "module": "capture_inbox",
      "summary": "specific problem",
      "evidence": "artifact or field from the packet",
      "recommendation": "smallest useful fix"
    }}
  ],
  "strong_points": [],
  "untested_risks": []
}}
```

Scoring guidance:

- 90-100: coherent, useful, no should-fix issues.
- 75-89: usable but has clear should-fix gaps.
- 60-74: important flows work but quality or routing is shaky.
- below 60: users or agents are likely to make wrong decisions.

Return JSON only. Do not edit files.
"""


def _read_json(path: Path, warnings: list[str]) -> Any:
    if not path.is_file():
        warnings.append(f"missing artifact: {path.name}")
        return {"missing": path.name}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"invalid json artifact: {path.name}: {exc}")
        return {"invalid_json": path.name}


def _read_text(path: Path, warnings: list[str]) -> str:
    if not path.is_file():
        warnings.append(f"missing artifact: {path.name}")
        return ""
    return path.read_text(encoding="utf-8")


PACKET_REVIEW_FIELD_MAX = 5000


def _compact(value: Any, *, max_string: int = 1200, max_list: int = 40) -> Any:
    if isinstance(value, str):
        text = compact_user_paths_in_text(value)
        if len(text) <= max_string:
            return text
        return text[:max_string] + f"...[truncated {len(text) - max_string} chars]"
    if isinstance(value, list):
        return [
            _compact(item, max_string=max_string, max_list=max_list) for item in value[:max_list]
        ]
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            field_max_string = _field_max_string(key_text, max_string)
            compacted[key_text] = _compact(
                item,
                max_string=field_max_string,
                max_list=max_list,
            )
            if isinstance(item, str):
                compacted.update(_packet_truncation_fields(key_text, item, field_max_string))
            if isinstance(item, list) and len(item) > max_list:
                compacted[f"{key_text}_truncated_count"] = len(item) - max_list
        if isinstance(value.get("content"), str) and str(value.get("review_content") or ""):
            compacted["content"] = (
                "[raw content omitted from AI eval packet; review_content is the "
                "default agent review surface]"
            )
            compacted["content_preview"] = _compact(
                str(value.get("review_content") or ""),
                max_string=_field_max_string("review_content", max_string),
                max_list=max_list,
            )
            compacted.update(
                _packet_truncation_fields(
                    "content_preview",
                    str(value.get("review_content") or ""),
                    _field_max_string("review_content", max_string),
                )
            )
            compacted["raw_content_available"] = True
        if (
            "content" in value
            and "content_truncated" in value
            and isinstance(value.get("content"), str)
            and len(value["content"]) > max_string
            and not str(value.get("review_content") or "")
        ):
            compacted["packet_truncated"] = True
            compacted["packet_truncation_note"] = (
                "The AI eval packet shortened this content field for review size. "
                "Use content_truncated to interpret the underlying Alcove read payload."
            )
        return compacted
    return value


def _field_max_string(key: str, default: int) -> int:
    if key in {
        "review_content",
        "content_preview",
        "review_excerpt",
        "tail_excerpt",
        "notes_excerpt",
    }:
        return PACKET_REVIEW_FIELD_MAX
    return default


def _packet_truncation_fields(key: str, value: str, max_string: int) -> dict[str, Any]:
    text = compact_user_paths_in_text(value)
    if len(text) <= max_string:
        return {}
    return {
        f"{key}_packet_truncated": True,
        f"{key}_packet_omitted_chars": len(text) - max_string,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Alcove AI eval packet and prompt.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--smoke-root", required=True)
    parser.add_argument("--real-home-report", required=True)
    parser.add_argument("--real-integrations-dir", required=True)
    parser.add_argument("--agent-client-report")
    parser.add_argument("--mcp-matrix-report")
    parser.add_argument("--dashboard-browser-report")
    parser.add_argument("--radar-reports-report")
    parser.add_argument("--export-restore-report")
    parser.add_argument("--messy-inbox-report")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    bundle = build_eval_bundle(
        output_dir=Path(args.output_dir),
        smoke_root=Path(args.smoke_root),
        real_home_report=Path(args.real_home_report),
        real_integrations_dir=Path(args.real_integrations_dir),
        agent_client_report=Path(args.agent_client_report) if args.agent_client_report else None,
        mcp_matrix_report=Path(args.mcp_matrix_report) if args.mcp_matrix_report else None,
        dashboard_browser_report=Path(args.dashboard_browser_report)
        if args.dashboard_browser_report
        else None,
        radar_reports_report=Path(args.radar_reports_report) if args.radar_reports_report else None,
        export_restore_report=Path(args.export_restore_report)
        if args.export_restore_report
        else None,
        messy_inbox_report=Path(args.messy_inbox_report) if args.messy_inbox_report else None,
    )
    payload = {
        "packet": str(bundle.packet_path),
        "prompt": str(bundle.prompt_path),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"packet: {bundle.packet_path}")
        print(f"prompt: {bundle.prompt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
