from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path

from alcove.markdown import normalize_slug
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AddIdeaRequest:
    title: str
    notes: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AddTaskRequest:
    title: str
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "medium"
    due: str = ""


@dataclass(frozen=True)
class Idea:
    id: str
    title: str
    notes: str
    tags: list[str]
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    notes: str
    tags: list[str]
    status: str
    priority: str
    due: str
    created_at: str
    updated_at: str
    completed_at: str = ""


class TasksModule:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.taxonomy = load_taxonomy(self.paths.knowledge)
        self.store_path = self.paths.tasks / "tasks.json"

    def idea_add(self, request: AddIdeaRequest) -> Idea:
        data = self._load()
        timestamp = now_iso()
        idea = Idea(
            id=self._unique_id(request.title, [item["id"] for item in data["ideas"]]),
            title=request.title,
            notes=request.notes,
            tags=self._normalize_tags(request.tags),
            status="active",
            created_at=timestamp,
            updated_at=timestamp,
        )
        data["ideas"].append(asdict(idea))
        self._save(data)
        return idea

    def idea_list(self, status: str = "active") -> list[Idea]:
        return [
            self._idea(item)
            for item in self._load()["ideas"]
            if not status or item.get("status") == status
        ]

    def task_add(self, request: AddTaskRequest) -> Task:
        data = self._load()
        timestamp = now_iso()
        task = Task(
            id=self._unique_id(request.title, [item["id"] for item in data["tasks"]]),
            title=request.title,
            notes=request.notes,
            tags=self._normalize_tags(request.tags),
            status="pending",
            priority=self._priority(request.priority),
            due=request.due,
            created_at=timestamp,
            updated_at=timestamp,
        )
        data["tasks"].append(asdict(task))
        self._save(data)
        return task

    def task_list(self, status: str = "pending") -> list[Task]:
        return [
            self._task(item)
            for item in self._load()["tasks"]
            if not status or item.get("status") == status
        ]

    def task_complete(self, task_id: str) -> Task:
        return self._update_task_status(task_id, "done")

    def task_cancel(self, task_id: str) -> Task:
        return self._update_task_status(task_id, "cancelled")

    def _update_task_status(self, task_id: str, status: str) -> Task:
        data = self._load()
        slug = normalize_slug(task_id)
        timestamp = now_iso()
        for item in data["tasks"]:
            if item.get("id") == slug:
                item["status"] = status
                item["updated_at"] = timestamp
                if status == "done":
                    item["completed_at"] = timestamp
                self._save(data)
                return self._task(item)
        raise FileNotFoundError(f"Task not found: {task_id}")

    def _load(self) -> dict[str, list[dict]]:
        if not self.store_path.is_file():
            return {"ideas": [], "tasks": [], "routines": []}
        data = json.loads(self.store_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"ideas": [], "tasks": [], "routines": []}
        return {
            "ideas": self._list(data.get("ideas")),
            "tasks": self._list(data.get("tasks")),
            "routines": self._list(data.get("routines")),
        }

    def _save(self, data: dict[str, list[dict]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _unique_id(self, title: str, existing: list[str]) -> str:
        slug = normalize_slug(title)
        if slug not in existing:
            return slug
        counter = 2
        while f"{slug}-{counter}" in existing:
            counter += 1
        return f"{slug}-{counter}"

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _priority(self, value: str) -> str:
        priority = normalize_slug(value)
        return priority if priority in {"high", "medium", "low"} else "medium"

    def _idea(self, item: dict) -> Idea:
        return Idea(
            id=str(item.get("id") or ""),
            title=str(item.get("title") or ""),
            notes=str(item.get("notes") or ""),
            tags=[str(tag) for tag in self._list(item.get("tags"))],
            status=str(item.get("status") or "active"),
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
        )

    def _task(self, item: dict) -> Task:
        return Task(
            id=str(item.get("id") or ""),
            title=str(item.get("title") or ""),
            notes=str(item.get("notes") or ""),
            tags=[str(tag) for tag in self._list(item.get("tags"))],
            status=str(item.get("status") or "pending"),
            priority=str(item.get("priority") or "medium"),
            due=str(item.get("due") or ""),
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
            completed_at=str(item.get("completed_at") or ""),
        )

    def _list(self, value: object) -> list:
        return value if isinstance(value, list) else []
