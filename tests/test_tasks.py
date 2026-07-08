from __future__ import annotations

from alcove.search import SearchModule, SearchRequest
from alcove.tasks import AddIdeaRequest, AddTaskRequest, TasksModule
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
