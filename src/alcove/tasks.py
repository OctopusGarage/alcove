from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
import json

from alcove.home import AlcoveHome
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
class AddRoutineRequest:
    title: str
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    priority: str = "medium"
    every_days: int = 1
    next_due: str = ""


@dataclass(frozen=True)
class Idea:
    id: str
    title: str
    notes: str
    tags: list[str]
    status: str
    created_at: str
    updated_at: str
    promoted_task_id: str = ""


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


@dataclass(frozen=True)
class Routine:
    id: str
    title: str
    notes: str
    tags: list[str]
    status: str
    priority: str
    every_days: int
    next_due: str
    created_at: str
    updated_at: str
    last_materialized_due: str = ""


class TasksModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.workspace = workspace
        self.home = home
        if home is None and workspace is None:
            home = AlcoveHome.init()
            self.home = home
        self.task_root = home.paths().tasks if home is not None else workspace.paths().tasks
        self.taxonomy = (
            load_taxonomy(workspace.paths().knowledge)
            if workspace
            else load_taxonomy(self.task_root)
        )
        self.store_path = self.task_root / "tasks.json"

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

    def idea_promote_to_task(
        self,
        idea_id: str,
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> Task:
        data = self._load()
        slug = normalize_slug(idea_id)
        timestamp = now_iso()
        for idea in data["ideas"]:
            if idea.get("id") != slug:
                continue
            if idea.get("status") == "promoted" and idea.get("promoted_task_id"):
                raise ValueError(f"Idea already promoted: {idea_id}")
            task = self._new_task(
                data,
                title=str(idea.get("title") or slug),
                notes=self._combine_notes(str(idea.get("notes") or ""), notes),
                tags=[str(tag) for tag in self._list(idea.get("tags"))],
                priority=priority,
                due=due,
                timestamp=timestamp,
            )
            data["tasks"].append(asdict(task))
            idea["status"] = "promoted"
            idea["updated_at"] = timestamp
            idea["promoted_task_id"] = task.id
            self._save(data)
            return task
        raise FileNotFoundError(f"Idea not found: {idea_id}")

    def task_add(self, request: AddTaskRequest) -> Task:
        data = self._load()
        timestamp = now_iso()
        task = self._new_task(
            data,
            title=request.title,
            notes=request.notes,
            tags=request.tags,
            priority=request.priority,
            due=request.due,
            timestamp=timestamp,
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

    def routine_add(self, request: AddRoutineRequest) -> Routine:
        data = self._load()
        timestamp = now_iso()
        every_days = max(int(request.every_days), 1)
        next_due = request.next_due or date.today().isoformat()
        self._parse_date(next_due)
        routine = Routine(
            id=self._unique_id(request.title, [item["id"] for item in data["routines"]]),
            title=request.title,
            notes=request.notes,
            tags=self._normalize_tags(request.tags),
            status="active",
            priority=self._priority(request.priority),
            every_days=every_days,
            next_due=next_due,
            created_at=timestamp,
            updated_at=timestamp,
        )
        data["routines"].append(asdict(routine))
        self._save(data)
        return routine

    def routine_list(self, status: str = "active") -> list[Routine]:
        return [
            self._routine(item)
            for item in self._load()["routines"]
            if not status or item.get("status") == status
        ]

    def routine_materialize_due(self, today: str | date | None = None) -> list[Task]:
        data = self._load()
        current = self._coerce_date(today) if today is not None else date.today()
        timestamp = now_iso()
        created: list[Task] = []
        for routine in data["routines"]:
            if routine.get("status", "active") != "active":
                continue
            next_due = self._parse_date(str(routine.get("next_due") or ""))
            if next_due > current:
                continue
            due = next_due
            task = self._new_task(
                data,
                title=str(routine.get("title") or ""),
                notes=str(routine.get("notes") or ""),
                tags=[str(tag) for tag in self._list(routine.get("tags"))],
                priority=str(routine.get("priority") or "medium"),
                due=due.isoformat(),
                timestamp=timestamp,
            )
            task_data = {**asdict(task), "source_routine_id": routine.get("id")}
            data["tasks"].append(task_data)
            created.append(task)
            every_days = max(int(routine.get("every_days") or 1), 1)
            while next_due <= current:
                next_due += timedelta(days=every_days)
            routine["next_due"] = next_due.isoformat()
            routine["last_materialized_due"] = due.isoformat()
            routine["updated_at"] = timestamp
        if created:
            self._save(data)
        return created

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

    def _new_task(
        self,
        data: dict[str, list[dict]],
        title: str,
        notes: str,
        tags: list[str],
        priority: str,
        due: str,
        timestamp: str,
    ) -> Task:
        return Task(
            id=self._unique_id(title, [item["id"] for item in data["tasks"]]),
            title=title,
            notes=notes,
            tags=self._normalize_tags(tags),
            status="pending",
            priority=self._priority(priority),
            due=due,
            created_at=timestamp,
            updated_at=timestamp,
        )

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
            promoted_task_id=str(item.get("promoted_task_id") or ""),
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

    def _routine(self, item: dict) -> Routine:
        return Routine(
            id=str(item.get("id") or ""),
            title=str(item.get("title") or ""),
            notes=str(item.get("notes") or ""),
            tags=[str(tag) for tag in self._list(item.get("tags"))],
            status=str(item.get("status") or "active"),
            priority=str(item.get("priority") or "medium"),
            every_days=int(item.get("every_days") or 1),
            next_due=str(item.get("next_due") or ""),
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
            last_materialized_due=str(item.get("last_materialized_due") or ""),
        )

    def _combine_notes(self, base: str, extra: str) -> str:
        values = [value.strip() for value in (base, extra) if value.strip()]
        return "\n\n".join(values)

    def _coerce_date(self, value: str | date) -> date:
        if isinstance(value, date):
            return value
        return self._parse_date(value)

    def _parse_date(self, value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    def _list(self, value: object) -> list:
        return value if isinstance(value, list) else []
