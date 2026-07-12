from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from alcove.search import SearchModule, SearchRequest
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.workspace import Workspace
from alcove.home import AlcoveHome


def test_idea_add_and_list_persists_low_friction_capture(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)

    idea = module.idea_add(
        AddIdeaRequest(
            title="Review Clipsmith release flow",
            notes="Check whether release artifacts are worth adding.",
            tags=["clipsmith"],
        )
    )
    ideas = module.idea_list()

    assert idea.id == "review-clipsmith-release-flow"
    assert idea.status == "active"
    assert idea.tags == ["clipsmith"]
    assert ideas == [idea]
    assert (tmp_path / "tasks" / "tasks.json").is_file()


def test_task_add_list_and_complete_updates_status(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)

    task = module.task_add(
        AddTaskRequest(
            title="Wire Alcove MCP tools",
            notes="Expose search and inbox peek first.",
            tags=["mcp"],
            priority="high",
            due="2026-07-10",
        )
    )
    pending = module.task_list()
    completed = module.task_complete("wire-alcove-mcp-tools")
    pending_after_complete = module.task_list()
    done = module.task_list(status="done")

    assert task.id == "wire-alcove-mcp-tools"
    assert pending == [task]
    assert completed.status == "done"
    assert pending_after_complete == []
    assert done[0].id == task.id


def test_idea_promote_to_task_marks_idea_and_creates_task(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    idea = module.idea_add(
        AddIdeaRequest(
            title="Turn capture into task",
            notes="This should become actionable.",
            tags=["workflow"],
        )
    )

    task = module.idea_promote_to_task(
        idea.id,
        priority="high",
        due="2026-07-09",
        notes="Add acceptance checks.",
    )

    promoted = module.idea_list(status="promoted")[0]
    assert task.id == "turn-capture-into-task"
    assert task.notes == "This should become actionable.\n\nAdd acceptance checks."
    assert task.tags == ["workflow"]
    assert task.priority == "high"
    assert task.due == "2026-07-09"
    assert promoted.id == idea.id
    assert promoted.status == "promoted"


def test_routine_materialize_due_creates_tasks_once_and_advances_next_due(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    routine = module.routine_add(
        AddRoutineRequest(
            title="Review weekly inbox",
            notes="Process waiting captures.",
            tags=["review"],
            priority="high",
            every_days=7,
            next_due="2026-07-08",
        )
    )

    created = module.routine_materialize_due(today="2026-07-08")
    created_again = module.routine_materialize_due(today="2026-07-08")
    routines = module.routine_list()

    assert routine.id == "review-weekly-inbox"
    assert len(created) == 1
    assert created[0].title == "Review weekly inbox"
    assert created[0].due == "2026-07-08"
    assert created[0].tags == ["review"]
    assert created[0].source_routine_id == "review-weekly-inbox"
    assert created_again == []
    assert routines[0].next_due == "2026-07-15"
    assert routines[0].last_materialized_due == "2026-07-08"


def test_weekly_routine_materialize_uses_weekdays_and_is_idempotent(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    module.routine_add(
        AddRoutineRequest(
            title="Weekly review",
            schedule={"frequency": "weekly", "interval": 1, "weekdays": ["wed", "fri"]},
            next_due="2026-07-08",
        )
    )

    created = module.routine_materialize_due(today="2026-07-08")
    created_again = module.routine_materialize_due(today="2026-07-08")

    assert [task.due for task in created] == ["2026-07-08"]
    assert created_again == []
    assert module.routine_list()[0].next_due == "2026-07-10"


def test_monthly_routine_materialize_clamps_day_of_month(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    module.routine_add(
        AddRoutineRequest(
            title="Month end review",
            schedule={"frequency": "monthly", "interval": 1, "day_of_month": 31},
            next_due="2026-01-31",
        )
    )

    created = module.routine_materialize_due(today="2026-01-31")

    assert created[0].due == "2026-01-31"
    assert module.routine_list()[0].next_due == "2026-02-28"


def test_routine_pause_resume_archive_and_edit(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    routine = module.routine_add(
        AddRoutineRequest(
            title="Review weekly inbox",
            schedule={"frequency": "weekly", "interval": 1, "weekdays": ["mon"]},
            next_due="2026-07-06",
        )
    )

    paused = module.routine_pause(routine.id)
    empty = module.routine_materialize_due(today="2026-07-06")
    resumed = module.routine_resume(routine.id, today="2026-07-12")
    edited = module.routine_edit(
        routine.id,
        title="Review managed inbox",
        priority="high",
        schedule={"frequency": "daily", "interval": 2},
    )
    archived = module.routine_archive(routine.id)

    assert paused.status == "paused"
    assert empty == []
    assert resumed.status == "active"
    assert resumed.next_due == "2026-07-13"
    assert edited.title == "Review managed inbox"
    assert edited.priority == "high"
    assert edited.schedule == {"frequency": "daily", "interval": 2}
    assert archived.status == "archived"


def test_task_edit_and_listing_sorts_overdue_due_and_priority(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    module.task_add(AddTaskRequest(title="Future low", priority="low", due="2026-07-20"))
    urgent = module.task_add(
        AddTaskRequest(title="Old medium", priority="medium", due="2026-07-01")
    )
    module.task_add(AddTaskRequest(title="Today high", priority="high", due="2026-07-10"))

    edited = module.task_edit(urgent.id, title="Old high", priority="high", notes="Escalated")
    rows = module.task_list(today="2026-07-10")

    assert edited.title == "Old high"
    assert edited.notes == "Escalated"
    assert [task.title for task in rows] == ["Old high", "Today high", "Future low"]


def test_task_list_tolerates_legacy_invalid_due_values(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    task = module.task_add(AddTaskRequest(title="Legacy date", due="next friday"))

    rows = module.task_list(today="2026-07-10")

    assert rows[0].id == task.id
    assert rows[0].due == "next friday"


def test_idea_edit_archive_and_promote_to_routine(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    archived_idea = module.idea_add(AddIdeaRequest(title="Archive later"))
    idea = module.idea_add(AddIdeaRequest(title="Weekly source review", notes="Look for signals."))

    edited = module.idea_edit(idea.id, title="Weekly source scan", tags=["radar"])
    routine = module.idea_promote_to_routine(
        edited.id,
        schedule={"frequency": "weekly", "interval": 1, "weekdays": ["sun"]},
        next_due="2026-07-12",
    )
    archived = module.idea_archive(archived_idea.id)

    assert edited.title == "Weekly source scan"
    assert routine.title == "Weekly source scan"
    assert routine.schedule["weekdays"] == ["sun"]
    assert module.idea_list(status="promoted")[0].promoted_routine_id == routine.id
    assert archived.status == "archived"


def test_task_digest_builds_report_and_can_notify(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = TasksModule(home=home)
    module.task_add(AddTaskRequest(title="Overdue task", due="2026-07-01"))
    module.idea_add(AddIdeaRequest(title="Fresh idea", notes="Capture first."))
    module.routine_add(
        AddRoutineRequest(
            title="Sunday planning",
            schedule={"frequency": "weekly", "interval": 1, "weekdays": ["sun"]},
            next_due="2026-07-12",
        )
    )
    sent: list[dict] = []

    def fake_send(*, home, text):
        sent.append({"home": home.root, "text": text})
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_telegram_message", fake_send)

    digest = module.task_digest(period="weekly", today="2026-07-12", notify=True)

    assert digest["status"] == "sent"
    assert digest["counts"] == {"ideas": 1, "tasks": 1, "routines": 1}
    assert digest["text"].count(digest["title"]) == 1
    assert "✅ Pending tasks" in digest["text"]
    assert "💡 Ideas" in digest["text"]
    assert "🔁 Active routines" in digest["text"]
    assert "Overdue task" in digest["text"]
    assert "Fresh idea" in digest["text"]
    assert sent[0]["text"].count(digest["title"]) == 1
    assert "Sunday planning" in sent[0]["text"]


def test_task_digest_text_is_readable_and_keeps_ids_in_payload(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = TasksModule(home=home)
    task = module.task_add(AddTaskRequest(title="Review task references"))
    idea = module.idea_add(AddIdeaRequest(title="Review idea references"))
    routine = module.routine_add(AddRoutineRequest(title="Review routine references"))

    digest = module.task_digest(period="weekly", today="2026-07-12")

    assert "1. Review task references" in digest["text"]
    assert "1. Review idea references" in digest["text"]
    assert "1. Review routine references" in digest["text"]
    assert f"[task:{task.id}]" not in digest["text"]
    assert f"[idea:{idea.id}]" not in digest["text"]
    assert f"[routine:{routine.id}]" not in digest["text"]
    assert digest["items"]["tasks"][0]["id"] == task.id
    assert digest["items"]["ideas"][0]["id"] == idea.id
    assert digest["items"]["routines"][0]["id"] == routine.id


def test_task_digest_can_notify_multiple_sinks(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = TasksModule(home=home)
    module.task_add(AddTaskRequest(title="Review notification sinks", due="2026-07-12"))
    sent_telegram: list[str] = []
    sent_feishu: list[dict] = []

    def fake_send_telegram(*, home, text):
        sent_telegram.append(text)
        return {"status": "sent"}

    def fake_send_feishu(*, home, sink, title, text, report_path=None):
        sent_feishu.append(
            {
                "sink": sink,
                "title": title,
                "text": text,
                "report_path": report_path,
            }
        )
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_telegram_message", fake_send_telegram)
    monkeypatch.setattr("alcove.tasks.send_feishu_message", fake_send_feishu)

    digest = module.task_digest(
        period="weekly",
        today="2026-07-12",
        notify=True,
        sinks=[{"type": "telegram"}, {"type": "feishu", "webhook_env": "ALCOVE_TEST_FEISHU"}],
    )

    assert digest["status"] == "sent"
    assert digest["notify"]["status"] == "sent"
    assert digest["notify"]["sinks"]["telegram"]["status"] == "sent"
    assert digest["notify"]["sinks"]["feishu"]["status"] == "sent"
    assert "Review notification sinks" in sent_telegram[0]
    assert sent_telegram[0].count(digest["title"]) == 1
    assert sent_feishu[0]["title"] == digest["title"]
    assert digest["title"] not in sent_feishu[0]["text"]
    assert "✅ Pending tasks" in sent_feishu[0]["text"]
    assert "Review notification sinks" in sent_feishu[0]["text"]
    assert sent_feishu[0]["report_path"] is None


def test_task_digest_uses_configured_sinks_when_notify_is_manual(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = TasksModule(home=home)
    module.task_add(AddTaskRequest(title="Manual digest configured sink"))
    (home.paths().tasks / "notifications.yml").write_text(
        "\n".join(
            [
                "digests:",
                "  weekly:",
                "    enabled: true",
                "    day: sunday",
                "    notify: true",
                "    sinks:",
                "      - type: feishu",
                "        webhook_env: ALCOVE_TEST_FEISHU",
                "",
            ]
        ),
        encoding="utf-8",
    )
    sent_feishu: list[str] = []

    def fake_send_feishu(*, home, sink, title, text, report_path=None):
        sent_feishu.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_feishu_message", fake_send_feishu)

    digest = module.task_digest(period="weekly", today="2026-07-12", notify=True)

    assert digest["status"] == "sent"
    assert digest["notify"]["sinks"]["feishu"]["status"] == "sent"
    assert "telegram" not in digest["notify"]["sinks"]
    assert digest["title"] not in sent_feishu[0]
    assert "Manual digest configured sink" in sent_feishu[0]


def test_due_digest_respects_configured_send_time(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = TasksModule(home=home)
    module.task_add(AddTaskRequest(title="Timed weekly digest"))
    (home.paths().tasks / "notifications.yml").write_text(
        "\n".join(
            [
                "digests:",
                "  weekly:",
                "    enabled: true",
                "    day: sunday",
                "    time: '21:00'",
                "    notify: true",
                "",
            ]
        ),
        encoding="utf-8",
    )
    sent: list[str] = []

    def fake_send(*, home, text):
        sent.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_telegram_message", fake_send)

    early = module.run_due_notifications(now=datetime.fromisoformat("2026-07-12T20:59:00+08:00"))
    due = module.run_due_notifications(now=datetime.fromisoformat("2026-07-12T21:00:00+08:00"))

    assert early["sent"] == 0
    assert early["skipped_items"] == [{"period": "weekly", "reason": "not_due"}]
    assert due["sent"] == 1
    assert "Timed weekly digest" in sent[0]


def test_search_includes_active_ideas_and_pending_tasks(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = TasksModule(workspace)
    module.idea_add(
        AddIdeaRequest(
            title="Bookmark Mounts",
            notes="Index starred repos and browser bookmarks later.",
            tags=["mounts"],
        )
    )
    module.task_add(
        AddTaskRequest(
            title="Build Task Search",
            notes="Tasks should appear in Alcove search.",
            tags=["tasks"],
        )
    )
    module.task_complete("build-task-search")

    rows = SearchModule(workspace).search(SearchRequest(query="bookmarks"))

    assert len(rows) == 1
    assert {
        "root": "tasks",
        "type": "Idea",
        "title": "Bookmark Mounts",
        "tags": ["mounts"],
        "status": "active",
        "path": "tasks/tasks.json#ideas/bookmark-mounts",
    }.items() <= rows[0].items()


def test_import_social_radar_preserves_tasks_ideas_and_routines(tmp_path):
    workspace = Workspace.init(tmp_path)
    source = tmp_path / "todos.json"
    source.write_text(
        json.dumps(
            {
                "todos": [
                    {
                        "id": "todo-1",
                        "title": "Review repair records",
                        "category": "personal",
                        "status": "cancelled",
                        "priority": "medium",
                        "due": None,
                        "created_at": "2026-04-04",
                        "notes": f"Check {Path.home()}/raw records.",
                        "source": "manual",
                    }
                ],
                "ideas": [
                    {
                        "id": "idea-1",
                        "title": "Build data migration",
                        "status": "active",
                        "category": "migration",
                        "notes": "Migrate personal records.",
                        "created_at": "2026-04-22",
                    }
                ],
                "routines": [
                    {
                        "id": "routine-1",
                        "title": "Check Apple Notes backup",
                        "category": "maintenance",
                        "status": "archived",
                        "priority": "medium",
                        "notes": "Confirm commits exist.",
                        "schedule": {"frequency": "weekly", "interval": 1, "weekdays": ["sat"]},
                        "next_due": "2026-04-19",
                        "last_generated_due": None,
                        "created_at": "2026-04-16",
                        "generated_todo_ids": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    module = TasksModule(workspace)

    result = module.import_social_radar(source)
    second = module.import_social_radar(source)

    assert result["tasks"]["imported"] == 1
    assert result["ideas"]["imported"] == 1
    assert result["routines"]["imported"] == 1
    assert second["tasks"]["updated"] == 1
    store = json.loads((tmp_path / "tasks" / "tasks.json").read_text(encoding="utf-8"))
    assert store["tasks"][0]["social_radar_id"] == "todo-1"
    assert store["tasks"][0]["status"] == "cancelled"
    assert str(Path.home()) not in store["tasks"][0]["notes"]
    assert "~/raw records" in store["tasks"][0]["notes"]
    assert store["ideas"][0]["tags"] == ["migration", "social-radar"]
    assert store["routines"][0]["schedule"]["weekdays"] == ["sat"]
    assert store["routines"][0]["every_days"] == 7
    assert (tmp_path / "tasks" / "imports" / "social-radar-todos.latest.json").is_file()
