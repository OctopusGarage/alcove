from __future__ import annotations

import json
from pathlib import Path

from alcove.ai_eval import EvalPacketBuilder, build_eval_bundle, build_eval_packet
from alcove.verify_suites import eval_report_paths, verify_suite_manifest


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_verify_suite_manifest_owns_eval_report_paths(tmp_path):
    suites = verify_suite_manifest()
    suite_ids = [suite.id for suite in suites]
    paths = eval_report_paths(tmp_path)

    assert suite_ids == [
        "isolated",
        "real_home",
        "real_integrations",
        "agent_clients",
        "mcp_matrix",
        "dashboard_browser",
        "export_restore",
        "messy_inbox",
    ]
    assert paths["real_home_report"] == tmp_path / "real-home" / "real-home-smoke-report.json"
    assert paths["mcp_matrix_report"] == tmp_path / "mcp-matrix" / "mcp-matrix-report.json"
    assert paths["dashboard_browser_report"] == (
        tmp_path / "dashboard-browser" / "dashboard-browser-report.json"
    )
    assert paths["messy_inbox_report"] == tmp_path / "messy-inbox" / "messy-inbox-report.json"


def _write_minimal_packet_artifacts(
    tmp_path: Path,
    *,
    inbox_read: dict | None = None,
) -> tuple[Path, Path, Path]:
    smoke_root = tmp_path / "smoke"
    fixtures = smoke_root / "fixtures"
    _write_json(
        fixtures / "inbox-read.json",
        inbox_read or {"title": "Captured Post", "content": "body", "content_truncated": False},
    )
    _write_json(fixtures / "inbox-note.json", {})
    _write_json(fixtures / "kb-search.json", [])
    _write_json(fixtures / "cleanup-search.json", [])
    _write_json(fixtures / "cleanup-delete-preview.json", {})
    _write_json(fixtures / "cleanup-delete-confirm.json", {})
    _write_json(fixtures / "cleanup-search-after-delete.json", [])
    _write_json(fixtures / "cleanup-search-deleted.json", [])
    _write_json(fixtures / "pin-search.json", [])
    _write_json(fixtures / "prompt-search.json", [])
    _write_json(fixtures / "task-add.json", {})
    _write_json(fixtures / "idea-add.json", {})
    _write_json(fixtures / "routine-add.json", {})
    _write_json(fixtures / "mount-scan.json", {})
    _write_json(fixtures / "okf-catalog.json", {"status": "built", "files": []})
    _write_json(fixtures / "apple-notes-search.json", [])
    _write_json(
        fixtures / "apple-notes-fetch.json",
        {"status": "skipped", "reason": "No synthetic Apple Notes fixture search result"},
    )
    _write_json(fixtures / "chrome-bookmarks-search.json", [])
    _write_json(fixtures / "multilingual-knowledge-search.json", [])
    _write_json(fixtures / "multilingual-todo-search.json", [])
    _write_json(fixtures / "intent-routing-examples.json", {"status": "passed", "examples": []})
    _write_json(fixtures / "connector-fetch.json", {})
    _write_json(fixtures / "link-source.json", {})
    _write_json(fixtures / "dashboard-build.json", {})
    _write_json(fixtures / "dashboard-render.json", {})
    _write_json(smoke_root / "home" / "dashboard" / "snapshot.json", {})
    _write_json(fixtures / "validate.json", {"issues": []})
    _write_json(fixtures / "health.json", {"status": "ok", "issues": [], "actions": []})
    _write_json(fixtures / "gardener.json", {"issues": [], "actions": []})
    _write_json(fixtures / "export-all.json", {})
    _write_json(fixtures / "doctor.json", {})
    real_home = tmp_path / "real-home.json"
    _write_json(real_home, {})
    integrations = tmp_path / "integrations"
    _write_json(integrations / "real-integrations-summary.json", {})
    _write_json(integrations / "alcove-inbox-read-clipsmith.json", {})
    _write_json(integrations / "alcove-inbox-read-ocr.json", {})
    _write_json(integrations / "mcp-stdio-report.json", {})
    _write_json(integrations / "github-stars-import.json", {})
    _write_json(integrations / "github-stars-search.json", [])
    _write_json(integrations / "apple-notes-import-local.json", {})
    _write_json(integrations / "apple-notes-search.json", [])
    _write_json(
        integrations / "apple-notes-fetch.json",
        {"status": "skipped", "reason": "Apple Notes search returned no item to fetch"},
    )
    _write_json(
        integrations / "connector-failure-samples.json",
        {"status": "passed", "samples": []},
    )
    _write_json(
        tmp_path / "mcp-matrix" / "mcp-matrix-report.json",
        {"status": "passed", "called_tools": 0, "module_counts": {}, "checks": []},
    )
    _write_json(
        tmp_path / "dashboard-browser" / "dashboard-browser-report.json",
        {"status": "passed", "routes_checked": 0, "checks": []},
    )
    _write_json(
        tmp_path / "export-restore" / "export-restore-report.json",
        {"status": "passed", "summary": {}, "checks": []},
    )
    _write_json(
        tmp_path / "messy-inbox" / "messy-inbox-report.json",
        {"status": "passed", "items": [], "checks": []},
    )
    return smoke_root, real_home, integrations


def _write_agent_client_smoke(path: Path) -> None:
    _write_json(
        path,
        {
            "status": "passed",
            "verified_mode": "mcp_stdio_with_generated_files",
            "unverified_optional_cli_probes": ["codex_cli", "claude_cli"],
            "release_grade_cli_probe_command": (
                "ALCOVE_AGENT_CLIENT_SMOKE_CODEX=1 "
                "ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE=1 "
                "scripts/smoke-agent-clients.sh"
            ),
            "checks": [
                {
                    "name": "mcp_stdio_client",
                    "status": "passed",
                    "detail": "64 tools",
                },
                {
                    "name": "codex_cli",
                    "status": "skipped",
                    "detail": "ALCOVE_AGENT_CLIENT_SMOKE_CODEX=1 not set",
                },
                {
                    "name": "claude_cli",
                    "status": "skipped",
                    "detail": "ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE=1 not set",
                },
            ],
            "summary": {
                "mcp_tool_count": 64,
                "codex_cli": "skipped",
                "claude_cli": "skipped",
            },
        },
    )


def _write_extended_smoke_reports(tmp_path: Path) -> dict[str, Path]:
    reports = {
        "mcp_matrix_report": tmp_path / "mcp-matrix" / "mcp-matrix-report.json",
        "dashboard_browser_report": tmp_path
        / "dashboard-browser"
        / "dashboard-browser-report.json",
        "export_restore_report": tmp_path / "export-restore" / "export-restore-report.json",
        "messy_inbox_report": tmp_path / "messy-inbox" / "messy-inbox-report.json",
    }
    _write_json(
        reports["mcp_matrix_report"],
        {
            "status": "passed",
            "tool_count": 64,
            "called_tools": 31,
            "module_counts": {"inbox": 3, "knowledge": 4, "global_memory": 8},
            "checks": [{"module": "inbox", "tool": "alcove_inbox_read", "status": "passed"}],
            "covered_by_external_smoke": [
                {
                    "tool": "alcove_connector_github_stars_import_url",
                    "reason": "live GitHub smoke",
                }
            ],
            "samples": {
                "inbox": {
                    "tool": "alcove_inbox_read",
                    "payload": {
                        "item": {
                            "title": "Captured Post",
                            "identifier": "manual/captured-post.md",
                        }
                    },
                },
                "knowledge": {
                    "tool": "alcove_kb_note",
                    "payload": {
                        "title": "Matrix Note",
                        "tags": [f"tag-{index}" for index in range(45)],
                    },
                },
                "search": {
                    "tool": "alcove_search",
                    "payload": {
                        "results": [
                            {
                                "title": "Matrix Search",
                                "tags": [f"tag-{index}" for index in range(45)],
                            }
                        ]
                    },
                },
            },
        },
    )
    _write_json(
        reports["dashboard_browser_report"],
        {
            "status": "passed",
            "routes_checked": 12,
            "viewports": [{"name": "mobile", "width": 390, "height": 844}],
            "large_dataset": {
                "pins": 81,
                "tasks_total": 51,
                "knowledge_items": 161,
                "search_index_items": 330,
            },
            "checks": [
                *[
                    {"name": f"desktop_route_{index:02d}", "status": "passed"}
                    for index in range(45)
                ],
                *[{"name": f"mobile_route_{index:02d}", "status": "passed"} for index in range(45)],
                {"name": "mobile_search_results", "status": "passed"},
            ],
            "console_errors": [],
        },
    )
    _write_json(
        reports["export_restore_report"],
        {
            "status": "passed",
            "summary": {"pin_results": 1, "kb_results": 1},
            "checks": [{"name": "kb_search", "status": "passed"}],
        },
    )
    _write_json(
        reports["messy_inbox_report"],
        {
            "status": "passed",
            "batch": {
                "count": 24,
                "platform_counts": {
                    "web": 4,
                    "x": 4,
                    "xhs": 4,
                    "wechat": 4,
                    "image-ocr": 4,
                    "manual": 4,
                },
            },
            "items": [
                {
                    "identifier": "web/long-warning-web",
                    "content_truncated": True,
                    "review_summary": "messy review",
                }
            ],
            "checks": [{"name": "ocr_deduplicated", "status": "passed"}],
        },
    )
    return reports


def test_build_eval_packet_covers_core_modules_and_quality_questions(tmp_path):
    smoke_root = tmp_path / "smoke"
    fixtures = smoke_root / "fixtures"
    _write_json(
        fixtures / "inbox-read.json",
        {"title": "Captured Post", "content": "body", "content_truncated": False},
    )
    _write_json(fixtures / "inbox-note.json", {"archive": "archive.md", "source": "source.md"})
    _write_json(fixtures / "kb-search.json", [{"title": "Smoke Concept"}])
    _write_json(
        fixtures / "cleanup-search.json",
        [
            {
                "title": "Cleanup Source",
                "published_at": "",
                "collected_at": "2026-07-11T00:00:00+00:00",
                "deleted_at": "",
                "status": "active",
            }
        ],
    )
    _write_json(
        fixtures / "cleanup-delete-preview.json",
        {"status": "preview", "confirm_required": True},
    )
    _write_json(
        fixtures / "cleanup-delete-confirm.json",
        {
            "status": "deleted",
            "deleted_at": "2026-07-11T00:01:00+00:00",
            "related_actions": [{"action": "deleted_single_source_concept"}],
        },
    )
    _write_json(fixtures / "cleanup-search-after-delete.json", [])
    _write_json(
        fixtures / "cleanup-search-deleted.json",
        [{"title": "Cleanup Source", "status": "deleted", "deleted_at": "2026-07-11"}],
    )
    _write_json(
        fixtures / "kb-add.json",
        {
            "status": "registered",
            "knowledge_base": {
                "name": "research_notes",
                "path": str(smoke_root / "research_notes"),
            },
        },
    )
    _write_json(fixtures / "pin-search.json", [{"title": "Smoke Pin"}])
    _write_json(fixtures / "prompt-search.json", [{"title": "Smoke Prompt"}])
    _write_json(fixtures / "project-add.json", {"project": {"alias": "project-alpha"}})
    _write_json(
        fixtures / "project-find.json",
        {"projects": [{"alias": "project-alpha", "note": "Smoke project alias"}]},
    )
    _write_json(fixtures / "task-add.json", {"task": {"title": "Smoke Task"}})
    _write_json(fixtures / "mount-scan.json", {"items": [{"title": "Mounted Smoke"}]})
    _write_json(
        fixtures / "okf-catalog.json",
        {
            "status": "built",
            "files": [
                "index.md",
                "managed-kbs.md",
                "global-memory.md",
                "external-indexes.md",
                "search-map.md",
            ],
            "counts": {
                "managed_kbs": 1,
                "pins": 1,
                "prompts": 1,
                "tasks": 1,
                "mounts": 1,
                "connectors": 2,
            },
        },
    )
    _write_json(
        fixtures / "apple-notes-search.json",
        [
            {
                "title": "Smoke Apple Note",
                "type": "Apple Note",
                "platform": "apple-notes",
                "notes": "Apple Notes smoke needle.",
                "resource": None,
                "fetch_ref": "connectors/apple-notes#notes/x-coredata%3A%2F%2Fsmoke-note/note.json",
            }
        ],
    )
    _write_json(
        fixtures / "apple-notes-fetch.json",
        {
            "status": "fetched",
            "connector": "apple-notes",
            "item": {
                "title": "Smoke Apple Note",
                "folder_path": "iCloud/Smoke",
                "text": "Apple Notes smoke needle.",
            },
            "detail": {
                "title": "Smoke Apple Note",
                "folder_path": "iCloud/Smoke",
                "plaintext": "Apple Notes smoke needle.",
            },
        },
    )
    _write_json(
        fixtures / "multilingual-knowledge-search.json",
        [
            {"root": "pins", "type": "Pin", "title": "常用收藏：OKF 知识库采集"},
            {
                "root": "knowledge",
                "type": "Knowledge Concept",
                "title": "OKF 知识库检索原则",
                "path": "knowledge-bases/research_notes/concepts/agent-engineering/okf/okf-知识库检索原则.md",
            },
        ],
    )
    _write_json(
        fixtures / "multilingual-todo-search.json",
        [{"type": "Task", "title": "TODO：实践 Apple Notes connector 增量更新"}],
    )
    _write_json(
        fixtures / "intent-routing-examples.json",
        {
            "status": "passed",
            "examples": [
                {
                    "utterance": "查一下本地的个人知识库，关于OKF相关的知识数据，汇总总结一下",
                    "expected_read_path": "Home-wide search first.",
                }
            ],
        },
    )
    _write_json(fixtures / "connector-fetch.json", {"item": {"title": "octopusgarage/alcove"}})
    _write_json(fixtures / "link-source.json", {"status": "linked"})
    _write_json(
        fixtures / "dashboard-build.json",
        {"status": "built", "frontend_mode": "compiled_frontend"},
    )
    _write_json(
        fixtures / "dashboard-render.json",
        {"status": "passed", "screenshot_bytes": 12000},
    )
    _write_json(
        smoke_root / "home" / "dashboard" / "snapshot.json",
        {
            "knowledge": {"managed": []},
            "search_index": [{"title": f"row-{index}"} for index in range(12)],
        },
    )
    _write_json(fixtures / "validate.json", {"issues": []})
    _write_json(fixtures / "health.json", {"status": "ok", "issues": [], "actions": []})
    _write_json(fixtures / "gardener.json", {"issues": [], "actions": []})
    _write_json(fixtures / "export-all.json", {"type": "all"})
    _write_json(
        fixtures / "doctor.json",
        {
            "status": "ok",
            "checks": [
                {
                    "name": "alcove",
                    "status": "ok",
                    "path": "/Users/example/.venv/bin/alcove",
                }
            ],
        },
    )
    (smoke_root / "hub" / ".agents" / "skills" / "alcove-hub").mkdir(parents=True)
    (smoke_root / "hub" / "AGENTS.md").write_text("hub agents", encoding="utf-8")
    (smoke_root / "hub" / "CLAUDE.md").write_text("hub claude", encoding="utf-8")
    (smoke_root / "hub" / ".agents" / "skills" / "alcove-hub" / "SKILL.md").write_text(
        "hub skill", encoding="utf-8"
    )
    kb_root = smoke_root / "research_notes"
    (kb_root / ".agents" / "skills" / "alcove-kb").mkdir(parents=True)
    (kb_root / ".agents" / "skills" / "notes-search").mkdir(parents=True)
    (kb_root / ".agents" / "skills" / "social_post_manager").mkdir(parents=True)
    (kb_root / ".claude" / "commands").mkdir(parents=True)
    (kb_root / "AGENTS.md").write_text("kb agents", encoding="utf-8")
    (kb_root / "CLAUDE.md").write_text("kb claude", encoding="utf-8")
    (kb_root / ".agents" / "skills" / "alcove-kb" / "SKILL.md").write_text(
        "kb skill", encoding="utf-8"
    )
    (kb_root / ".agents" / "skills" / "notes-search" / "SKILL.md").write_text(
        "notes skill", encoding="utf-8"
    )
    long_manager_skill = "manager skill " + ("full command routing. " * 120)
    (kb_root / ".agents" / "skills" / "social_post_manager" / "SKILL.md").write_text(
        long_manager_skill, encoding="utf-8"
    )
    (kb_root / ".claude" / "commands" / "inbox-peek.md").write_text(
        "inbox command", encoding="utf-8"
    )
    _write_json(
        tmp_path / "real-home" / "real-home-smoke-report.json",
        {"status": "passed", "summary": {"pins": 2, "tasks": 1}, "checks": []},
    )
    integrations = tmp_path / "real-integrations"
    _write_json(
        integrations / "real-integrations-summary.json",
        {
            "status": "passed",
            "github_stars": 10,
            "apple_notes": 4,
            "mcp_tool_count": 64,
            "ocr_content_source": "summary.md, ocr.md, post.md",
        },
    )
    _write_json(
        integrations / "alcove-inbox-read-ocr.json",
        {
            "title": "OCR",
            "content_source": "summary.md, ocr.md, post.md",
            "content": "OCR result should be saved to ocr.md",
        },
    )
    _write_json(
        integrations / "apple-notes-import-local.json",
        {"scanned": 4, "exported": 4, "item_count": 4},
    )
    _write_json(
        integrations / "github-stars-search.json",
        [
            {
                "title": "octopusgarage/alcove",
                "type": "GitHub Star",
                "resource": "https://github.com/OctopusGarage/alcove",
                "notes": "octopusgarage/alcove\nLocal-first personal knowledge workbench.",
                "source_id": "github-stars",
                "source_label": "GitHub Stars · github / Python",
                "origin_label": "GitHub Stars",
                "fetch_ref": "connectors/github-stars#octopusgarage/alcove",
            }
        ],
    )
    _write_json(
        integrations / "apple-notes-search.json",
        [
            {
                "title": "Apple Notes Sample",
                "type": "Apple Note",
                "platform": "apple-notes",
                "date": "2026-07-10",
                "notes": "Apple Notes item-level search evidence.",
                "path": "connectors/apple-notes#local/sample-note",
                "display_id": "apple-notes/sample-note",
                "display_label": "Apple Notes Sample",
                "source_id": "apple-notes",
                "source_label": "Apple Notes · iCloud / iCloud/Ideas",
                "origin_label": "Apple Notes / iCloud/Ideas",
                "fetch_ref": "connectors/apple-notes#local/sample-note",
                "fetch_command": "alcove connector fetch connectors/apple-notes#local/sample-note --json",
            }
        ],
    )
    _write_json(
        integrations / "apple-notes-fetch.json",
        {
            "status": "fetched",
            "connector": "apple-notes",
            "display_id": "apple-notes/sample-note",
            "display_label": "Apple Notes Sample",
            "source_id": "apple-notes",
            "source_label": "Apple Notes · iCloud / iCloud/Ideas",
            "origin_label": "Apple Notes / iCloud/Ideas",
            "fetch_ref": "connectors/apple-notes#local/sample-note",
            "item": {
                "title": "Apple Notes Sample",
                "folder_path": "iCloud/Ideas",
                "updated_at": "2026-07-10T09:00:00Z",
                "relative_path": "local/sample-note",
                "text": "Apple Notes item-level search evidence.",
            },
            "detail": {
                "title": "Apple Notes Sample",
                "folder_path": "iCloud/Ideas",
                "updated_at": "2026-07-10T09:00:00Z",
                "plaintext": "Apple Notes item-level search evidence.",
            },
        },
    )
    _write_json(
        integrations / "connector-failure-samples.json",
        {
            "status": "passed",
            "samples": [
                {
                    "name": "github-stars-invalid-url",
                    "exit_code": 2,
                    "status": "passed",
                    "structured_json": True,
                    "error": {
                        "connector": "github-stars",
                        "error_code": "value",
                        "message": "Unsupported GitHub Stars URL host: example.com",
                        "remediation_hint": "Use a GitHub profile URL.",
                    },
                    "stderr": (
                        "real-integration: uv run alcove connector --home "
                        f"{tmp_path}/.tmp/ai-eval/real-integrations/home github-stars"
                    ),
                    "stdout": '{"error":{"connector":"github-stars"}}',
                }
            ],
        },
    )

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=tmp_path / "real-home" / "real-home-smoke-report.json",
        real_integrations_dir=integrations,
    )

    module_ids = {module["id"] for module in packet["modules"]}
    assert {
        "capture_inbox",
        "knowledge_okf",
        "global_memory",
        "external_indexes",
        "dashboard",
        "mcp_entry",
        "export_health",
        "agent_entries",
    }.issubset(module_ids)
    assert any(
        "OCR" in question
        for module in packet["modules"]
        for question in module["ai_quality_questions"]
    )
    assert packet["evidence"]["real_integrations"]["github_stars"] == 10
    live_samples = packet["evidence"]["real_integrations"]["live_samples"]
    assert live_samples[0]["connector"] == "github-stars"
    assert live_samples[0]["title"] == "octopusgarage/alcove"
    assert live_samples[0]["source_label"] == "GitHub Stars · github / Python"
    assert live_samples[0]["fetch_ref_available"] is True
    assert live_samples[1]["connector"] == "apple-notes"
    assert live_samples[1]["source_id"] == "apple-notes"
    assert live_samples[1]["source_label"].startswith("[redacted ")
    assert live_samples[1]["title"].startswith("[redacted ")
    assert live_samples[1]["notes_preview"] == {"present": True, "char_count": 39}
    assert live_samples[1]["fetch_status"] == "fetched"
    assert live_samples[1]["cleaned_preview"] == {"present": True, "char_count": 39}
    assert "Apple Notes item-level search evidence" not in json.dumps(
        live_samples[1], ensure_ascii=False
    )
    assert "inbox" in packet["evidence"]["integration_samples"]["mcp_tool_inventory"]
    assert (
        "alcove_connector_fetch"
        in packet["evidence"]["integration_samples"]["mcp_tool_inventory"]["external_indexes"]
    )
    assert (
        "alcove_connector_chrome_bookmarks_index"
        in packet["evidence"]["integration_samples"]["mcp_tool_inventory"]["external_indexes"]
    )
    apple_sample = packet["evidence"]["integration_samples"]["apple_notes_item_sample"]
    assert apple_sample["search_count"] == 1
    assert apple_sample["search_result"]["title"].startswith("[redacted ")
    assert "path" not in apple_sample["search_result"]
    assert "fetch_ref" not in apple_sample["search_result"]
    assert "fetch_command" not in apple_sample["search_result"]
    assert apple_sample["search_result"]["notes"] == {"present": True, "char_count": 39}
    assert apple_sample["search_result"]["source_id"] == "apple-notes"
    assert apple_sample["search_result"]["source_label"].startswith("[redacted ")
    assert apple_sample["search_result"]["fetch_ref_available"] is True
    assert apple_sample["tool_fetch"]["source_id"] == "apple-notes"
    assert apple_sample["tool_fetch"]["source_label"].startswith("[redacted ")
    assert apple_sample["fetch_result"]["source_id"] == "apple-notes"
    assert apple_sample["fetch_result"]["source_label"].startswith("[redacted ")
    assert apple_sample["search_result"]["fetch_command_available"] is True
    assert apple_sample["tool_fetch"]["display_ref"].startswith("[redacted ")
    assert apple_sample["tool_fetch"]["fetch_ref_available"] is True
    assert (
        apple_sample["tool_fetch"]["fetch_command_pattern"]
        == "alcove connector fetch <fetch_ref> --json"
    )
    assert "fetch_ref" not in apple_sample["fetch_result"]
    assert "relative_path" not in apple_sample["fetch_result"]["item"]
    assert apple_sample["fetch_result"]["detail"]["folder_path_present"] is True
    assert apple_sample["fetch_result"]["detail"]["plaintext"] == {
        "present": True,
        "char_count": 39,
    }
    assert apple_sample["fetch_result"]["detail"]["cleaned_preview"] == {
        "present": True,
        "char_count": 39,
    }
    assert apple_sample["fetch_result"]["detail"]["information_quality"]["status"] == "ok"
    assert "Apple Notes item-level search evidence" not in json.dumps(
        apple_sample, ensure_ascii=False
    )
    public_apple_sample = packet["evidence"]["integration_samples"][
        "apple_notes_public_fixture_sample"
    ]
    assert public_apple_sample["has_item"] is True
    assert public_apple_sample["title"] == "Smoke Apple Note"
    assert public_apple_sample["notes_preview"] == "Apple Notes smoke needle."
    assert public_apple_sample["fetch_result"]["plaintext_preview"] == "Apple Notes smoke needle."
    descriptions = packet["evidence"]["integration_samples"]["mcp_tool_descriptions"]
    assert "leads, not final truth" in descriptions["alcove_search"]
    assert "governed OKF write path" in descriptions["alcove_knowledge_revise"]
    assert "governed global write path" in descriptions["alcove_pin_update"]
    assert packet["evidence"]["smoke"]["dashboard_snapshot"]["knowledge"] == {"managed": []}
    assert packet["evidence"]["smoke"]["dashboard_render"]["status"] == "passed"
    assert (
        packet["evidence"]["smoke"]["multilingual_knowledge_search"][0]["title"]
        == "常用收藏：OKF 知识库采集"
    )
    assert any(
        row["root"] == "knowledge" and "OKF" in row["title"]
        for row in packet["evidence"]["smoke"]["multilingual_knowledge_search"]
    )
    assert packet["evidence"]["smoke"]["multilingual_todo_search"][0]["type"] == "Task"
    assert (
        packet["evidence"]["smoke"]["intent_routing_examples"]["examples"][0]["utterance"]
        == "查一下本地的个人知识库，关于OKF相关的知识数据，汇总总结一下"
    )
    assert (
        packet["evidence"]["integration_samples"]["connector_failure_samples"]["status"] == "passed"
    )
    failure_stderr = packet["evidence"]["integration_samples"]["connector_failure_samples"][
        "samples"
    ][0]["stderr"]
    assert "<eval-artifact>" in failure_stderr
    assert ".tmp/ai-eval" not in failure_stderr
    assert len(packet["evidence"]["smoke"]["dashboard_snapshot"]["search_index"]) == 12
    assert packet["evidence"]["smoke"]["doctor"]["diagnostic_paths_omitted"] is True
    assert "path" not in packet["evidence"]["smoke"]["doctor"]["checks"][0]
    assert packet["evidence"]["smoke"]["validate"]["issues"] == []
    assert packet["evidence"]["smoke"]["gardener"]["actions"] == []
    assert packet["evidence"]["smoke"]["okf_catalog"]["status"] == "built"
    assert "search-map.md" in packet["evidence"]["smoke"]["okf_catalog"]["files"]
    assert packet["evidence"]["smoke"]["project_add"]["project"]["alias"] == "project-alpha"
    assert packet["evidence"]["smoke"]["project_find"]["projects"][0]["alias"] == "project-alpha"
    assert packet["evidence"]["agent_entries"]["kb_social_post_manager"] == long_manager_skill
    assert packet["evidence"]["agent_entries"]["managed_kb_entry_root"].endswith(
        "smoke/research_notes"
    )
    assert (
        packet["evidence"]["agent_entries"]["skill_availability"]["hub_codex_skill"]["exists"]
        is True
    )
    assert "truncated" not in packet["evidence"]["agent_entries"]["kb_social_post_manager"]
    assert "scripts/eval-ai.sh" in packet["evidence"]["agent_entries"]["claude_eval_ai_command"]
    assert "scripts/smoke.sh" in packet["evidence"]["agent_entries"]["codex_smoke_skill"]
    assert packet["operating_model"]["read_path"]["search_role"].endswith(
        "candidate leads, not final answers."
    )
    assert (
        "connector lazy-fetch details"
        in packet["operating_model"]["read_path"]["follow_up_evidence"]
    )
    assert (
        "global OKF catalog under ~/.alcove/okf"
        in packet["operating_model"]["read_path"]["follow_up_evidence"]
    )
    assert "Governed writes" in packet["operating_model"]["write_path"]["principle"]
    assert any("candidate discovery" in rule for rule in packet["review_rules"])
    assert any("CLI/MCP write tools" in rule for rule in packet["review_rules"])
    assert any(
        "AI-led investigation" in question
        for module in packet["modules"]
        for question in module["ai_quality_questions"]
    )
    assert any(
        "global OKF catalog" in question
        for module in packet["modules"]
        for question in module["ai_quality_questions"]
    )
    assert any(
        "alcove_search as the final authority" in question
        for module in packet["modules"]
        for question in module["ai_quality_questions"]
    )


def test_eval_packet_preserves_degraded_real_integration_status(tmp_path):
    smoke_root, real_home_report, integrations = _write_minimal_packet_artifacts(tmp_path)
    _write_json(
        integrations / "real-integrations-summary.json",
        {
            "status": "degraded",
            "github_stars": 2,
            "github_stars_live_verified": False,
            "github_stars_status": "fallback",
            "github_stars_fallback_reason": "live GitHub import failed during smoke",
            "apple_notes": 4,
            "mcp_tool_count": 64,
            "ocr_content_source": "summary.md, ocr.md",
        },
    )
    _write_json(
        integrations / "github-stars-import.json",
        {
            "scanned": 2,
            "exported": 2,
            "network_fallback": True,
            "fallback_reason": "live GitHub import failed during smoke",
        },
    )

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home_report,
        real_integrations_dir=integrations,
    )

    assert packet["evidence"]["real_integrations"]["status"] == "degraded"
    assert packet["evidence"]["real_integrations"]["github_stars_live_verified"] is False
    assert packet["evidence"]["real_integrations"]["github_stars_status"] == "fallback"
    assert (
        packet["evidence"]["integration_samples"]["github_stars_import"]["network_fallback"] is True
    )


def test_eval_packet_marks_identifier_heavy_apple_notes_low_information(tmp_path):
    smoke_root, real_home_report, integrations = _write_minimal_packet_artifacts(tmp_path)
    _write_json(
        integrations / "apple-notes-search.json",
        [
            {
                "title": "微信公众号",
                "type": "Apple Note",
                "platform": "apple-notes",
                "notes": "微信公众号\nwxda7a1cb0644cb4cd\n1d21951cef2c3d0be0721de131166bec\n",
                "fetch_ref": "connectors/apple-notes#local/weak-note",
            }
        ],
    )
    _write_json(
        integrations / "apple-notes-fetch.json",
        {
            "status": "fetched",
            "connector": "apple-notes",
            "display_label": "微信公众号",
            "item": {"title": "微信公众号"},
            "detail": {
                "title": "微信公众号",
                "folder_path": "iCloud/备忘查阅",
                "plaintext": "微信公众号\nwxda7a1cb0644cb4cd\n1d21951cef2c3d0be0721de131166bec\n",
            },
        },
    )

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home_report,
        real_integrations_dir=integrations,
    )

    apple_sample = packet["evidence"]["integration_samples"]["apple_notes_item_sample"]
    quality = apple_sample["fetch_result"]["detail"]["information_quality"]
    assert apple_sample["fetch_result"]["detail"]["cleaned_preview"] == {
        "present": True,
        "char_count": 5,
    }
    assert "微信公众号" not in json.dumps(apple_sample, ensure_ascii=False)
    assert quality["status"] == "low-information"
    live_sample = packet["evidence"]["real_integrations"]["live_samples"][0]
    assert live_sample["connector"] == "apple-notes"
    assert live_sample["information_quality"]["status"] == "low-information"


def test_eval_packet_agent_entries_follow_registered_kb_name(tmp_path):
    smoke_root, real_home_report, integrations = _write_minimal_packet_artifacts(tmp_path)
    _write_json(
        smoke_root / "fixtures" / "kb-add.json",
        {
            "status": "registered",
            "knowledge_base": {
                "name": "social_media_posts",
                "path": str(smoke_root / "social_media_posts"),
            },
        },
    )
    (smoke_root / "hub" / ".agents" / "skills" / "alcove-hub").mkdir(parents=True)
    (smoke_root / "hub" / "AGENTS.md").write_text("hub agents", encoding="utf-8")
    (smoke_root / "hub" / "CLAUDE.md").write_text("hub claude", encoding="utf-8")
    (smoke_root / "hub" / ".agents" / "skills" / "alcove-hub" / "SKILL.md").write_text(
        "hub skill", encoding="utf-8"
    )
    kb_root = smoke_root / "social_media_posts"
    (kb_root / ".agents" / "skills" / "alcove-kb").mkdir(parents=True)
    (kb_root / ".agents" / "skills" / "notes-search").mkdir(parents=True)
    (kb_root / ".agents" / "skills" / "social_post_manager").mkdir(parents=True)
    (kb_root / ".claude" / "commands").mkdir(parents=True)
    (kb_root / "AGENTS.md").write_text("social kb agents", encoding="utf-8")
    (kb_root / "CLAUDE.md").write_text("social kb claude", encoding="utf-8")
    (kb_root / ".agents" / "skills" / "alcove-kb" / "SKILL.md").write_text(
        "social kb skill", encoding="utf-8"
    )
    (kb_root / ".agents" / "skills" / "notes-search" / "SKILL.md").write_text(
        "social notes skill", encoding="utf-8"
    )
    (kb_root / ".agents" / "skills" / "social_post_manager" / "SKILL.md").write_text(
        "social post manager", encoding="utf-8"
    )
    (kb_root / ".claude" / "commands" / "inbox-peek.md").write_text(
        "social inbox command", encoding="utf-8"
    )

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home_report,
        real_integrations_dir=integrations,
    )

    entries = packet["evidence"]["agent_entries"]
    assert entries["managed_kb_entry_root"].endswith("smoke/social_media_posts")
    assert entries["kb_agents"] == "social kb agents"
    assert entries["kb_social_post_manager"] == "social post manager"
    assert not any("AGENTS.md" in warning for warning in packet["warnings"])


def test_eval_packet_includes_agent_client_smoke_evidence(tmp_path):
    smoke_root, real_home_report, integrations = _write_minimal_packet_artifacts(tmp_path)
    agent_client_report = tmp_path / "agent-clients" / "agent-client-smoke-report.json"
    _write_agent_client_smoke(agent_client_report)

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home_report,
        real_integrations_dir=integrations,
        agent_client_report=agent_client_report,
    )

    evidence = packet["evidence"]["agent_client_smoke"]
    assert evidence["status"] == "passed"
    assert evidence["summary"]["mcp_tool_count"] == 64
    assert evidence["summary"]["codex_cli"] == "skipped"
    assert evidence["unverified_optional_cli_probes"] == ["codex_cli", "claude_cli"]
    assert any(check["name"] == "mcp_stdio_client" for check in evidence["checks"])

    agent_module = next(module for module in packet["modules"] if module["id"] == "agent_entries")
    assert any(
        "client smoke" in question.lower() for question in agent_module["ai_quality_questions"]
    )


def test_eval_packet_includes_extended_smoke_evidence(tmp_path):
    smoke_root, real_home_report, integrations = _write_minimal_packet_artifacts(tmp_path)
    reports = _write_extended_smoke_reports(tmp_path)

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home_report,
        real_integrations_dir=integrations,
        **reports,
    )

    assert packet["evidence"]["mcp_matrix"]["called_tools"] == 31
    assert packet["evidence"]["mcp_matrix"]["module_call_counts"]["inbox"] == 3
    assert packet["evidence"]["mcp_matrix"]["module_tool_counts"]["inbox"] == 1
    assert packet["evidence"]["mcp_matrix"]["tool_coverage"]["total_tools"] >= 60
    assert packet["evidence"]["mcp_matrix"]["tool_coverage"]["reported_call_count"] == 31
    assert packet["evidence"]["mcp_matrix"]["tool_coverage"]["unique_called_tools"] == 1
    assert packet["evidence"]["mcp_matrix"]["tool_coverage"]["externally_covered_tools"] == [
        "alcove_connector_github_stars_import_url"
    ]
    assert packet["evidence"]["mcp_matrix"]["tool_coverage"]["covered_tools"] == 2
    assert (
        "alcove_export_all" in packet["evidence"]["mcp_matrix"]["tool_coverage"]["uncalled_tools"]
    )
    assert (
        "alcove_connector_github_stars_import_url"
        not in packet["evidence"]["mcp_matrix"]["tool_coverage"]["uncovered_tools"]
    )
    assert packet["evidence"]["mcp_matrix"]["check_rollup"] == [
        {"module": "inbox", "tool": "alcove_inbox_read", "status": "passed"}
    ]
    assert packet["evidence"]["mcp_matrix"]["check_rollup_by_module"]["inbox"] == {
        "calls": 1,
        "passed": 1,
        "failed": 0,
        "tools": ["alcove_inbox_read:passed"],
    }
    assert packet["evidence"]["mcp_matrix"]["external_coverage_rollup"] == [
        "alcove_connector_github_stars_import_url"
    ]
    policy = packet["evidence"]["mcp_matrix"]["external_coverage_policy"]
    assert policy["status"] == "failed"
    assert policy["mode"] == "derived"
    assert policy["direct_call_exceptions"] == ["alcove_connector_github_stars_import_url"]
    assert (
        policy["uncovered_tools"]
        == packet["evidence"]["mcp_matrix"]["tool_coverage"]["uncovered_tools"][
            : len(policy["uncovered_tools"])
        ]
    )
    assert policy["uncovered_tools_truncated_count"] > 0
    assert policy["fail_when"] == (
        "An MCP tool is neither called by the MCP matrix nor externally covered."
    )
    assert (
        packet["evidence"]["mcp_matrix"]["samples"]["inbox"]["payload"]["item"]["title"]
        == "Captured Post"
    )
    knowledge_payload = packet["evidence"]["mcp_matrix"]["samples"]["knowledge"]["payload"]
    assert knowledge_payload["tags"] == [f"tag-{index}" for index in range(40)]
    assert knowledge_payload["tags_truncated_count"] == 5
    search_result = packet["evidence"]["mcp_matrix"]["samples"]["search"]["payload"]["results"][0]
    assert search_result["tags"] == [f"tag-{index}" for index in range(40)]
    assert search_result["tags_truncated_count"] == 5
    assert packet["evidence"]["dashboard_browser"]["routes_checked"] == 12
    assert packet["evidence"]["dashboard_browser"]["large_dataset"]["search_index_items"] == 330
    dashboard_checks = packet["evidence"]["dashboard_browser"]["checks"]
    assert any(check["name"].startswith("desktop_") for check in dashboard_checks)
    assert any(check["name"].startswith("mobile_") for check in dashboard_checks)
    assert packet["evidence"]["dashboard_browser"]["check_rollup_by_viewport"] == {
        "desktop": {"total": 45, "passed": 45, "failed": 0},
        "mobile": {"total": 46, "passed": 46, "failed": 0},
    }
    assert packet["evidence"]["dashboard_browser"]["checks_truncated_count"] > 0
    assert packet["evidence"]["export_restore"]["summary"]["kb_results"] == 1
    assert packet["evidence"]["messy_inbox"]["batch"]["count"] == 24
    assert packet["evidence"]["messy_inbox"]["items"][0]["content_truncated"] is True

    module_questions = {
        module["id"]: " ".join(module["ai_quality_questions"]).lower()
        for module in packet["modules"]
    }
    assert "mcp matrix" in module_questions["mcp_entry"]
    assert "browser smoke" in module_questions["dashboard"]
    assert "export-restore" in module_questions["export_health"]
    assert "messy inbox" in module_questions["capture_inbox"]


def test_build_eval_packet_marks_compacted_content_as_truncated(tmp_path):
    smoke_root, real_home, integrations = _write_minimal_packet_artifacts(
        tmp_path,
        inbox_read={"title": "Captured Post", "content": "x" * 1300, "content_truncated": False},
    )

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home,
        real_integrations_dir=integrations,
    )

    inbox_read = packet["evidence"]["smoke"]["inbox_read"]
    assert inbox_read["content_truncated"] is False
    assert inbox_read["packet_truncated"] is True
    assert "AI eval packet shortened" in inbox_read["packet_truncation_note"]


def test_eval_packet_builder_owns_artifact_warnings_and_compaction(tmp_path):
    smoke_root, real_home, integrations = _write_minimal_packet_artifacts(
        tmp_path,
        inbox_read={
            "title": "Captured Post",
            "content": "/Users/example/private " + ("x" * 1300),
            "content_truncated": False,
        },
    )
    (smoke_root / "fixtures" / "prompt-search.json").unlink()

    packet = EvalPacketBuilder(
        smoke_root=smoke_root,
        real_home_report=real_home,
        real_integrations_dir=integrations,
    ).build()

    assert packet["evidence"]["smoke"]["prompt_search"] == {"missing": "prompt-search.json"}
    assert "missing artifact: prompt-search.json" in packet["warnings"]
    inbox_read = packet["evidence"]["smoke"]["inbox_read"]
    assert "~/private" in inbox_read["content"]
    assert inbox_read["packet_truncated"] is True


def test_build_eval_packet_uses_review_surface_for_inbox_content(tmp_path):
    smoke_root, real_home, integrations = _write_minimal_packet_artifacts(
        tmp_path,
        inbox_read={
            "title": "Captured Post",
            "content": "navigation " * 200,
            "review_content": "Useful article summary.",
            "content_truncated": False,
        },
    )

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home,
        real_integrations_dir=integrations,
    )

    inbox_read = packet["evidence"]["smoke"]["inbox_read"]
    assert inbox_read["content_preview"] == "Useful article summary."
    assert inbox_read["raw_content_available"] is True
    assert "navigation" not in inbox_read["content"]


def test_build_eval_packet_keeps_modest_review_surface_untruncated(tmp_path):
    review_content = "Useful article summary. " * 80
    smoke_root, real_home, integrations = _write_minimal_packet_artifacts(
        tmp_path,
        inbox_read={
            "title": "Captured Post",
            "content": "navigation " * 600,
            "review_content": review_content,
            "review_content_truncated": False,
            "review_content_omitted_chars": 0,
            "content_truncated": False,
        },
    )

    packet = build_eval_packet(
        smoke_root=smoke_root,
        real_home_report=real_home,
        real_integrations_dir=integrations,
    )

    inbox_read = packet["evidence"]["smoke"]["inbox_read"]
    assert inbox_read["review_content"] == review_content
    assert inbox_read["content_preview"] == review_content
    assert "review_content_packet_truncated" not in inbox_read


def test_build_eval_bundle_writes_packet_prompt_and_missing_artifact_warnings(tmp_path):
    output_dir = tmp_path / "ai-eval"
    smoke_root = tmp_path / "missing-smoke"

    result = build_eval_bundle(
        output_dir=output_dir,
        smoke_root=smoke_root,
        real_home_report=tmp_path / "missing-real-home.json",
        real_integrations_dir=tmp_path / "missing-integrations",
    )

    packet = json.loads(result.packet_path.read_text(encoding="utf-8"))
    prompt = result.prompt_path.read_text(encoding="utf-8")
    assert result.packet_path.is_file()
    assert result.prompt_path.is_file()
    assert packet["schema"] == "alcove.ai_eval_packet.v1"
    assert packet["warnings"]
    assert "Return JSON only" in prompt
    assert '"module_scores": [' in prompt
    assert "capture_inbox" in prompt
