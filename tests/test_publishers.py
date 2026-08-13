from __future__ import annotations

import json

import pytest
import yaml

from alcove.application import AlcoveApplication
from alcove.cli import main
from alcove.home import AlcoveHome
from alcove.pins import AddPinRequest, PinsModule
from alcove.projects import AddProjectRequest, ProjectsModule
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.publishers import (
    AppleNotesTarget,
    PublishError,
    PublisherModule,
    TargetRef,
    _markdown_as_html,
    render_pins_digest,
)
from alcove.runtime import AlcoveRuntime
from alcove.service import ServiceModule
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule


class FakeAppleNotesTarget(AppleNotesTarget):
    def __init__(self, *, ambiguous: bool = False, missing: bool = False) -> None:
        self.ambiguous = ambiguous
        self.missing = missing
        self.notes: dict[str, dict[str, str]] = {}
        self.replacements: list[dict[str, str]] = []

    def resolve_or_create(
        self,
        *,
        folder_path: str,
        title: str,
        note_id: str = "",
        recreate_missing: bool = False,
    ) -> TargetRef:
        if self.ambiguous and not note_id:
            raise PublishError("TARGET_AMBIGUOUS", f"Multiple notes match {title}")
        if note_id:
            if self.missing and not recreate_missing:
                raise PublishError("TARGET_MISSING", f"Missing note {note_id}")
            if note_id in self.notes:
                return TargetRef(note_id=note_id, folder_path=folder_path, title=title)
        generated = f"note-{len(self.notes) + 1}"
        self.notes[generated] = {"folder_path": folder_path, "title": title, "body": ""}
        return TargetRef(note_id=generated, folder_path=folder_path, title=title)

    def replace_note_body(self, *, note_id: str, title: str, body: str) -> dict[str, str]:
        self.notes[note_id] = {
            **self.notes.get(note_id, {}),
            "title": title,
            "body": body,
        }
        self.replacements.append({"note_id": note_id, "title": title, "body": body})
        return {"status": "updated", "note_id": note_id}


def test_default_apple_notes_publisher_writes_pin_notes_and_skips_unchanged(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    PinsModule(home=home).add(
        AddPinRequest(
            title="Regular Reference",
            summary="Keep this handy.",
            content="Full regular content.",
            kind="regular",
            tags=["reference"],
            resources=["https://example.test/regular"],
            priority="high",
        )
    )
    PinsModule(home=home).add(
        AddPinRequest(
            title="Try Later",
            summary="Evaluate this idea.",
            content="Full todo content.",
            kind="todo",
            tags=["todo"],
            priority="medium",
        )
    )
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    init = module.init_apple_notes(root_folder="iCloud/Alcove")

    first = module.run("apple-notes", timestamp="2026-07-12T08:00:00+00:00")
    second = module.run("apple-notes", timestamp="2026-07-13T08:00:00+00:00")

    assert init["status"] == "initialized"
    assert first["status"] == "success"
    assert first["updated"] == 5
    assert second["status"] == "success"
    assert second["skipped"] == 5
    assert len(target.replacements) == 5
    assert target.replacements[0]["title"] == "Regular Pins"
    assert "# 📌 Regular Pins" in target.replacements[0]["body"]
    assert "## High Priority" in target.replacements[0]["body"]
    assert "Regular Reference" in target.replacements[0]["body"]
    assert "Full regular content." in target.replacements[0]["body"]
    assert "Notes" in target.replacements[0]["body"]
    assert "---" in target.replacements[0]["body"]
    assert "Detail:" not in target.replacements[0]["body"]
    assert target.replacements[1]["title"] == "TODO Pins"
    assert "Try Later" in target.replacements[1]["body"]
    assert target.replacements[2]["title"] == "Planner Digest"
    assert "No pending tasks." in target.replacements[2]["body"]
    assert target.replacements[3]["title"] == "Prompt Library"
    assert "No active prompts." in target.replacements[3]["body"]
    assert target.replacements[4]["title"] == "Project Registry"
    assert "No registered projects." in target.replacements[4]["body"]
    state = yaml.safe_load((home.root / "publishers/state/apple-notes.yml").read_text())
    assert state["targets"]["pins_regular"]["note_id"] == "note-1"
    assert state["targets"]["pins_todo"]["note_id"] == "note-2"
    assert state["targets"]["planner_digest"]["note_id"] == "note-3"
    assert state["targets"]["prompt_library"]["note_id"] == "note-4"
    assert state["targets"]["project_registry"]["note_id"] == "note-5"
    assert (home.root / "publishers/renders/pins_regular.md").is_file()
    assert (home.root / "publishers/renders/planner_digest.md").is_file()
    assert list((home.root / "publishers/runs").glob("*apple-notes.json"))


def test_repeated_publisher_runs_preserve_distinct_run_records(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    monkeypatch.setattr("alcove.publishers.now_iso", lambda: "2026-07-29T01:02:03+00:00")

    first = module.run("apple-notes", timestamp="2026-07-29T01:02:03+00:00")
    second = module.run("apple-notes", force=True, timestamp="2026-07-29T01:02:03+00:00")

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert len(list((home.root / "publishers/runs").glob("*apple-notes.json"))) == 2


def test_alcove_memory_write_triggers_due_publisher_before_ttl(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    module.run_due(timestamp="2026-07-12T08:00:00+00:00")
    target.replacements.clear()

    not_due = module.run_due(timestamp="2026-07-12T09:00:00+00:00")
    app = AlcoveApplication(AlcoveRuntime.resolve(home=home.root))
    app.global_home.pin_add_payload(
        AddPinRequest(title="Event Triggered Pin", content="Dirty publisher source.")
    )
    dirty_run = module.run_due(timestamp="2026-07-12T09:01:00+00:00")
    after_clean = module.run_due(timestamp="2026-07-12T09:02:00+00:00")

    assert not_due["ran"] == 0
    assert not_due["publishers"][0]["reason"] == "not_due"
    assert dirty_run["ran"] == 1
    assert dirty_run["updated"] == 1
    assert dirty_run["publishers"][0]["due_reason"] == "dirty"
    assert dirty_run["publishers"][0]["dirty_sources"] == ["pins"]
    assert any("Event Triggered Pin" in item["body"] for item in target.replacements)
    assert after_clean["ran"] == 0
    assert after_clean["publishers"][0]["reason"] == "not_due"


@pytest.mark.parametrize(
    ("source", "write"),
    [
        (
            "pins",
            lambda app, tmp_path: app.global_home.pin_add_payload(
                AddPinRequest(title="Dirty Pin", content="Refresh pins.")
            ),
        ),
        (
            "prompts",
            lambda app, tmp_path: app.global_home.prompt_save_payload(
                AddPromptRequest(
                    title="Dirty Prompt",
                    content="Refresh prompt library.",
                ),
                force=True,
            ),
        ),
        (
            "projects",
            lambda app, tmp_path: app.global_home.project_add_payload(
                AddProjectRequest(
                    alias="dirty-project",
                    path=str(tmp_path / "project"),
                    note="Refresh project registry.",
                )
            ),
        ),
        (
            "tasks",
            lambda app, tmp_path: app.global_home.task_add_payload(
                AddTaskRequest(title="Dirty Task", notes="Refresh planner digest.")
            ),
        ),
    ],
)
def test_governed_memory_writes_mark_expected_publisher_sources_dirty(
    tmp_path,
    source,
    write,
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    (tmp_path / "project").mkdir()
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    first_run = module.run_due(timestamp="2026-07-12T08:00:00+00:00")
    target.replacements.clear()
    app = AlcoveApplication(AlcoveRuntime.resolve(home=home.root))

    not_due = module.run_due(timestamp="2026-07-12T09:00:00+00:00")
    write(app, tmp_path)
    dirty_run = module.run_due(timestamp="2026-07-12T09:01:00+00:00")
    after_clean = module.run_due(timestamp="2026-07-12T09:02:00+00:00")

    assert first_run["ran"] == 1
    assert not_due["ran"] == 0
    assert dirty_run["ran"] == 1
    assert dirty_run["publishers"][0]["due_reason"] == "dirty"
    assert dirty_run["publishers"][0]["dirty_sources"] == [source]
    assert after_clean["ran"] == 0
    assert after_clean["publishers"][0]["reason"] == "not_due"


def test_publisher_due_check_handles_legacy_naive_last_synced_at(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = PublisherModule(home)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    state_path = home.root / "publishers/state/apple-notes.yml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    default_targets = yaml.safe_load(
        (home.root / "publishers/definitions/apple-notes.yml").read_text(encoding="utf-8")
    )["targets"]
    state_path.write_text(
        yaml.safe_dump(
            {
                "schema": "alcove/publisher-state/v1",
                "publisher_id": "apple-notes",
                "targets": {
                    target_id: {
                        "note_id": "note-1",
                        "folder_path": "iCloud/Alcove",
                        "title": target_id,
                        "content_hash": "unchanged",
                        "last_synced_at": "2026-07-12T08:00:00",
                        "last_status": "success",
                        "last_error": "",
                    }
                    for target_id in default_targets
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    result = module.run_due(timestamp="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 0
    assert result["publishers"][0]["reason"] == "not_due"


def test_apple_notes_init_merges_missing_default_targets_without_overwriting(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = PublisherModule(home)
    first = module.init_apple_notes(root_folder="iCloud/Alcove")
    definition_path = home.root / "publishers/definitions/apple-notes.yml"
    definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
    definition["targets"]["pins_regular"]["target"]["title"] = "My Regular Pins"
    del definition["targets"]["planner_digest"]
    del definition["targets"]["prompt_library"]
    del definition["targets"]["project_registry"]
    definition_path.write_text(yaml.safe_dump(definition, sort_keys=False), encoding="utf-8")

    second = module.init_apple_notes(root_folder="iCloud/Changed")
    merged = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
    third = module.init_apple_notes(root_folder="iCloud/Ignored")

    assert first["status"] == "initialized"
    assert second["status"] == "updated"
    assert second["added_targets"] == ["planner_digest", "prompt_library", "project_registry"]
    assert third["status"] == "exists"
    assert merged["target_defaults"]["root_folder"] == "iCloud/Alcove"
    assert merged["targets"]["pins_regular"]["target"]["title"] == "My Regular Pins"
    assert set(merged["targets"]) == {
        "pins_regular",
        "pins_todo",
        "planner_digest",
        "prompt_library",
        "project_registry",
    }


def test_publisher_due_check_runs_when_definition_has_unsynced_targets(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    definition_path = home.root / "publishers/definitions/apple-notes.yml"
    definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
    definition["targets"] = {"pins_regular": definition["targets"]["pins_regular"]}
    definition_path.write_text(yaml.safe_dump(definition, sort_keys=False), encoding="utf-8")
    state_path = home.root / "publishers/state/apple-notes.yml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        yaml.safe_dump(
            {
                "schema": "alcove/publisher-state/v1",
                "publisher_id": "apple-notes",
                "targets": {
                    "pins_regular": {
                        "note_id": "note-1",
                        "folder_path": "iCloud/Alcove/pins",
                        "title": "Regular Pins",
                        "content_hash": "unchanged",
                        "last_synced_at": "2026-07-12T08:00:00+00:00",
                        "last_status": "success",
                        "last_error": "",
                    }
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    module.init_apple_notes(root_folder="iCloud/Alcove")

    result = module.run_due(timestamp="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 1
    assert result["updated"] > 0


def _write_apple_notes_state(
    home: AlcoveHome,
    definition: dict[str, object],
    *,
    failed_target: str = "",
    invalid_target: str = "",
    stale_target: str = "",
) -> None:
    state_path = home.root / "publishers/state/apple-notes.yml"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        yaml.safe_dump(
            {
                "schema": "alcove/publisher-state/v1",
                "publisher_id": "apple-notes",
                "targets": {
                    target_id: {
                        "note_id": f"note-{index}",
                        "folder_path": "iCloud/Alcove",
                        "title": target_id,
                        "content_hash": "unchanged",
                        "last_synced_at": (
                            "not-a-timestamp"
                            if target_id == invalid_target
                            else (
                                "2026-07-10T08:00:00+00:00"
                                if target_id == stale_target
                                else "2026-07-12T08:00:00+00:00"
                            )
                        ),
                        "last_status": "failed" if target_id == failed_target else "success",
                        "last_error": (
                            "TARGET_MISSING: Missing note" if target_id == failed_target else ""
                        ),
                    }
                    for index, target_id in enumerate(definition["targets"], 1)
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_publisher_due_check_runs_when_any_target_is_stale_after_partial_failure(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    definition = yaml.safe_load(
        (home.root / "publishers/definitions/apple-notes.yml").read_text(encoding="utf-8")
    )
    _write_apple_notes_state(home, definition, failed_target="planner_digest")

    result = module.run_due(timestamp="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 1
    assert result["updated"] > 0


def test_publisher_due_check_runs_when_target_sync_time_is_invalid(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    definition = yaml.safe_load(
        (home.root / "publishers/definitions/apple-notes.yml").read_text(encoding="utf-8")
    )
    _write_apple_notes_state(home, definition, invalid_target="planner_digest")

    result = module.run_due(timestamp="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 1
    assert result["updated"] > 0


def test_publisher_due_check_runs_when_target_exceeds_ttl(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    definition = yaml.safe_load(
        (home.root / "publishers/definitions/apple-notes.yml").read_text(encoding="utf-8")
    )
    _write_apple_notes_state(home, definition, stale_target="planner_digest")

    result = module.run_due(timestamp="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 1
    assert result["updated"] > 0


def test_publisher_due_check_runs_when_current_timestamp_is_invalid(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    definition = yaml.safe_load(
        (home.root / "publishers/definitions/apple-notes.yml").read_text(encoding="utf-8")
    )
    _write_apple_notes_state(home, definition)

    result = module.run_due(timestamp="not-a-timestamp")

    assert result["ran"] == 1
    assert result["updated"] > 0


def test_publisher_due_check_skips_when_every_target_is_fresh(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    definition = yaml.safe_load(
        (home.root / "publishers/definitions/apple-notes.yml").read_text(encoding="utf-8")
    )
    _write_apple_notes_state(home, definition)

    result = module.run_due(timestamp="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 0
    assert result["publishers"] == [
        {"publisher": "apple-notes", "status": "skipped", "reason": "not_due"}
    ]


def test_publisher_due_check_runs_when_active_definition_has_no_targets(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes(root_folder="iCloud/Alcove")
    definition_path = home.root / "publishers/definitions/apple-notes.yml"
    definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
    _write_apple_notes_state(home, definition)
    definition["targets"] = {}
    definition_path.write_text(yaml.safe_dump(definition, sort_keys=False), encoding="utf-8")

    result = module.run_due(timestamp="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 1
    assert result["publishers"][0]["status"] == "success"
    assert result["publishers"][0]["targets"] == []


def test_module_publishers_render_actionable_global_memory(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    TasksModule(home=home).task_add(
        AddTaskRequest(
            title="Review dashboard outside LAN",
            notes="Check Apple Notes mirror before travel.",
            priority="high",
            due="2026-07-20",
            tags=["travel"],
        )
    )
    TasksModule(home=home).idea_add(
        AddIdeaRequest(title="Try offline knowledge review", notes="Use Notes on mobile.")
    )
    TasksModule(home=home).routine_add(
        AddRoutineRequest(title="Weekly knowledge review", every_days=7, next_due="2026-07-19")
    )
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Architecture Review",
            description="Review boundaries and tests.",
            content="Review the current change for architecture drift.",
            tags=["review"],
            use_cases=["Code Review", "Architecture"],
        )
    )
    project_path = tmp_path / "alcove"
    project_path.mkdir()
    ProjectsModule(home=home).add(
        AddProjectRequest(
            alias="alcove",
            path=str(project_path),
            note="Local-first personal intelligence hub.",
        )
    )
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes()

    result = module.run("apple-notes", timestamp="2026-07-12T10:00:00+00:00")

    bodies = {item["title"]: item["body"] for item in target.replacements}
    assert result["updated"] == 5
    assert "# 🧭 Planner Digest" in bodies["Planner Digest"]
    assert "## Pending Tasks" in bodies["Planner Digest"]
    assert "Review dashboard outside LAN" in bodies["Planner Digest"]
    assert "Priority  high" in bodies["Planner Digest"]
    assert "Try offline knowledge review" in bodies["Planner Digest"]
    assert "# 🧰 Prompt Library" in bodies["Prompt Library"]
    assert "Architecture Review" in bodies["Prompt Library"]
    assert "Use cases  Code Review, Architecture" in bodies["Prompt Library"]
    assert "# 🗂 Project Registry" in bodies["Project Registry"]
    assert "alcove" in bodies["Project Registry"]
    assert "Local-first personal intelligence hub." in bodies["Project Registry"]
    assert "---" in bodies["Planner Digest"]
    assert str(tmp_path) not in bodies["Project Registry"]


def test_apple_notes_html_conversion_uses_scannable_structure():
    markdown = "\n".join(
        [
            "# Planner Digest",
            "",
            "---",
            "",
            "Updated: 2026-07-12 18:00 SGT",
            "Count: 2",
            "",
            "---",
            "",
            "## Pending Tasks",
            "",
            "1. Review dashboard outside LAN",
            "   Priority: high",
            "   Due: 2026-07-20",
            "   Tags: travel, dashboard",
            "   Resources:",
            "   - https://example.test",
            "",
            "## Ideas",
            "",
            "No active ideas.",
        ]
    )

    html = _markdown_as_html(markdown)

    assert 'font-size: 24px">Planner Digest' in html
    assert 'font-size: 18px">Pending Tasks' in html
    assert "<b>1. Review dashboard outside LAN</b>" in html
    assert '<div style="margin-left: 22px"><b>Priority:</b> high</div>' in html
    assert '<div style="margin-left: 28px">• https://example.test</div>' in html
    assert "────────────" in html
    assert "# Planner Digest" not in html
    assert "## Pending Tasks" not in html


def test_pin_content_rendering_avoids_detail_dump(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    result = PinsModule(home=home).add(
        AddPinRequest(
            title="常用收藏",
            summary="Markdown 原文",
            content="# 常用收藏\n## Claude / Codex\n- Default: Sonnet\nhttps://example.test",
            kind="regular",
            priority="high",
        )
    )

    rendered = render_pins_digest(
        title="Regular Pins",
        pins=[result.pin],
        timestamp="2026-07-12T10:00:00+00:00",
    )

    assert "# 📌 Regular Pins" in rendered
    assert "## High Priority" in rendered
    assert "01. 常用收藏" in rendered
    assert "   Notes" in rendered
    assert "   ◼ 常用收藏" in rendered
    assert "   ◼ Claude / Codex" in rendered
    assert "   - Default: Sonnet" in rendered
    assert "   - https://example.test" in rendered
    assert "---" in rendered
    assert "Detail:" not in rendered
    assert "Table:" not in rendered


def test_pin_content_rendering_preserves_long_markdown_for_apple_notes(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    content = "\n".join(
        [
            "# 常用收藏",
            "## Claude Code：命令速查",
            "| 类别 | 命令 / 操作 | 用途 |",
            "| --- | --- | --- |",
            *[
                f"| 上下文 | `/context {index}` | 查看 context 状态 {index} |"
                for index in range(1, 14)
            ],
            "## Claude Code：项目配置",
            *[f"- 配置项 {index}" for index in range(1, 14)],
            "## Claude Code：扩展体系",
            *[f"- 扩展项 {index}" for index in range(1, 8)],
        ]
    )
    result = PinsModule(home=home).add(
        AddPinRequest(
            title="常用收藏",
            summary="Markdown 原文",
            content=content,
            kind="regular",
            priority="high",
        )
    )

    rendered = render_pins_digest(
        title="Regular Pins",
        pins=[result.pin],
        timestamp="2026-07-12T10:00:00+00:00",
    )

    assert "Full content is kept in Alcove." not in rendered
    assert "Outline  3 sections" in rendered
    assert "- Claude Code：命令速查" in rendered
    assert "Full notes" in rendered
    assert "◼ Claude Code：命令速查" in rendered
    assert "类别 | 命令 / 操作 | 用途" in rendered
    assert "查看 context 状态 13" in rendered
    assert "配置项 13" in rendered
    assert "\n   ◼ Claude Code：项目配置\n\n" in rendered
    assert "Table:" not in rendered


def test_publisher_reports_ambiguous_target_without_hiding_other_targets(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    PinsModule(home=home).add(AddPinRequest(title="Regular", kind="regular"))
    target = FakeAppleNotesTarget(ambiguous=True)
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes()

    result = module.run("apple-notes", target_id="pins_regular")

    assert result["status"] == "partial"
    assert result["errors"] == 1
    assert result["targets"][0]["status"] == "failed"
    assert result["targets"][0]["error_code"] == "TARGET_AMBIGUOUS"
    assert "duplicate Apple Notes" in result["targets"][0]["remediation_hint"]


def test_publisher_can_recreate_missing_stateful_note_when_configured(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    PinsModule(home=home).add(AddPinRequest(title="Regular", kind="regular"))
    target = FakeAppleNotesTarget()
    module = PublisherModule(home, target_factory=lambda _definition: target)
    module.init_apple_notes()
    first = module.run("apple-notes", target_id="pins_regular")
    definition_path = home.root / "publishers/definitions/apple-notes.yml"
    definition = yaml.safe_load(definition_path.read_text())
    definition["target_defaults"]["recreate_missing"] = True
    definition_path.write_text(yaml.safe_dump(definition, sort_keys=False), encoding="utf-8")
    target.missing = True
    target.notes.clear()

    second = module.run("apple-notes", target_id="pins_regular", force=True)

    assert first["updated"] == 1
    assert second["status"] == "success"
    assert second["updated"] == 1
    state = yaml.safe_load((home.root / "publishers/state/apple-notes.yml").read_text())
    assert state["targets"]["pins_regular"]["note_id"] == "note-1"


def test_cli_publish_init_list_and_run(tmp_path, monkeypatch, capsys):
    home = tmp_path / ".alcove"
    PinsModule(home=AlcoveHome.init(home)).add(AddPinRequest(title="CLI Pin", kind="regular"))
    target = FakeAppleNotesTarget()
    monkeypatch.setattr(
        "alcove.publishers.LocalAppleNotesTarget",
        lambda: target,
    )

    init_code = main(["publish", "init", "apple-notes", "--home", str(home), "--json"])
    capsys.readouterr()
    list_code = main(["publish", "list", "--home", str(home), "--json"])
    list_output = capsys.readouterr()
    run_code = main(["publish", "run", "apple-notes", "--home", str(home), "--json"])
    run_output = capsys.readouterr()

    assert init_code == 0
    assert list_code == 0
    assert json.loads(list_output.out)["count"] == 1
    assert run_code == 0
    assert json.loads(run_output.out)["updated"] == 5
    assert "CLI Pin" in target.replacements[0]["body"]


def test_service_tick_runs_due_publishers(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    PinsModule(home=home).add(AddPinRequest(title="Service Pin", kind="regular"))
    target = FakeAppleNotesTarget()
    monkeypatch.setattr("alcove.publishers.LocalAppleNotesTarget", lambda: target)
    PublisherModule(home).init_apple_notes()

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        fix_health=False,
    )

    assert result["publishers"]["ran"] == 1
    assert result["publishers"]["updated"] == 5
    assert "Service Pin" in target.replacements[0]["body"]


def test_local_apple_notes_adapter_failure_is_machine_readable(monkeypatch):
    from alcove.publishers import LocalAppleNotesTarget

    def fake_run(*_args, **_kwargs):
        class Completed:
            returncode = 1
            stdout = ""
            stderr = "Not authorized to send Apple events to Notes."

        return Completed()

    monkeypatch.setattr("alcove.publishers.platform.system", lambda: "Darwin")
    monkeypatch.setattr("alcove.publishers.shutil.which", lambda name: "/usr/bin/osascript")
    monkeypatch.setattr("alcove.publishers.subprocess.run", fake_run)

    with pytest.raises(PublishError) as exc:
        LocalAppleNotesTarget().resolve_or_create(folder_path="iCloud/Alcove/pins", title="Pins")

    assert exc.value.code == "AUTOMATION_PERMISSION_DENIED"
