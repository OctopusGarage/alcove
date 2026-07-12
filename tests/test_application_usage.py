from __future__ import annotations

import json

from alcove.application import AlcoveApplication
from alcove.connectors.github_stars import GitHubStarsImportRequest
from alcove.home import AlcoveHome
from alcove.knowledge import NoteSourceRequest
from alcove.mounts import AddMountRequest
from alcove.pins import AddPinRequest
from alcove.prompts import AddPromptRequest
from alcove.runtime import AlcoveRuntime
from alcove.tasks import AddTaskRequest
from alcove.usage import UsageRecorder
from alcove.workspace import Workspace


def test_application_global_mutations_record_usage_and_activity(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    app = AlcoveApplication(AlcoveRuntime.resolve(home=home.root))

    app.global_home.pin_add_payload(AddPinRequest(title="Usage Pin", content="Pin body."))
    app.global_home.task_add_payload(AddTaskRequest(title="Usage Task", notes="Task body."))
    app.global_home.prompt_save_payload(
        AddPromptRequest(title="Usage Prompt", content="Prompt body.")
    )

    summary = UsageRecorder(home).summary()
    activity = _activity(home)

    assert summary["actions"]["areas"] == {"pin": 1, "prompt": 1, "task": 1}
    assert summary["actions"]["names"] == {
        "pin.add": 1,
        "prompt.save": 1,
        "task.add": 1,
    }
    assert {event["action"] for event in activity} >= {"pin.add", "task.add", "prompt.save"}
    assert all("/Users/" not in json.dumps(event, ensure_ascii=False) for event in activity)


def test_application_managed_kb_mutation_records_usage_and_activity(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    workspace = Workspace.init(tmp_path / "kb")
    app = AlcoveApplication(AlcoveRuntime.resolve(workspace=workspace.root, home=home.root))

    app.knowledge.note_source_payload(
        NoteSourceRequest(
            platform="web",
            title="Usage Source",
            topic="agent-engineering/usage",
            resource="https://example.test/usage",
            summary="Usage source summary.",
        )
    )

    summary = UsageRecorder(home).summary()
    activity = _activity(home)

    assert summary["actions"]["areas"] == {"knowledge": 1}
    assert summary["actions"]["names"] == {"knowledge.note_source": 1}
    assert activity[0]["area"] == "knowledge"
    assert activity[0]["action"] == "knowledge.note_source"
    assert activity[0]["summary"] == "Noted source: Usage Source"


def test_application_external_mutations_record_usage_and_activity(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    app = AlcoveApplication(AlcoveRuntime.resolve(home=home.root))
    mounted = tmp_path / "mounted"
    mounted.mkdir()
    (mounted / "note.md").write_text("# Mounted Usage\n\nNeedle.", encoding="utf-8")
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Usage analytics.",
                    "topics": ["usage"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    app.external.mount_add_payload(AddMountRequest(path=str(mounted), name="Usage Mount"))
    app.external.mount_scan_payload("usage-mount")
    app.external.github_stars_index_payload(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["usage"])
    )

    summary = UsageRecorder(home).summary()
    activity = _activity(home)

    assert summary["actions"]["areas"] == {"connector": 1, "mount": 2}
    assert summary["actions"]["names"] == {
        "connector.github_stars.index": 1,
        "mount.add": 1,
        "mount.scan": 1,
    }
    assert {event["action"] for event in activity} >= {
        "mount.add",
        "mount.scan",
        "connector.github_stars.index",
    }


def _activity(home: AlcoveHome) -> list[dict]:
    return [
        json.loads(line)
        for line in (home.paths().logs / "activity.jsonl").read_text(encoding="utf-8").splitlines()
    ]
