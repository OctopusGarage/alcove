from __future__ import annotations

import json
from pathlib import Path

from alcove.search import SearchModule, SearchRequest
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.workspace import Workspace


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
