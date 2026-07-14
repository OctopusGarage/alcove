from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
import fcntl
import json
from typing import Any

import yaml

from alcove.notifications import send_feishu_message, send_tcb_notification, send_telegram_message
from alcove.notification_delivery import (
    combined_notification_status,
    notification_sink_label,
    notification_sinks,
)
from alcove.planner_schedule import (
    advance_next_due,
    digest_due,
    digest_state_key,
    next_due_on_or_after,
    routine_schedule_from_item,
    schedule_every_days,
    validate_routine_schedule,
)
from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.runtime import AlcoveRuntime
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
    schedule: dict[str, Any] = field(default_factory=dict)


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
    promoted_routine_id: str = ""


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
    source_routine_id: str = ""


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
    schedule: dict[str, Any]
    created_at: str
    updated_at: str
    last_materialized_due: str = ""


class TasksModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.task_root = self.runtime.tasks_root
        taxonomy_root = self.runtime.knowledge_root if self.workspace else self.task_root
        self.taxonomy = load_taxonomy(taxonomy_root)
        self.store_path = self.task_root / "tasks.json"
        self.notification_config_path = self.task_root / "notifications.yml"
        self.notification_state_path = self.task_root / "notification-state.json"

    def idea_add(self, request: AddIdeaRequest) -> Idea:
        with self._transaction() as data:
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
        return idea

    def idea_list(self, status: str = "active") -> list[Idea]:
        return [
            self._idea(item)
            for item in self._load()["ideas"]
            if not status or item.get("status") == status
        ]

    def idea_edit(
        self,
        idea_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> Idea:
        with self._transaction() as data:
            idea = self._find_item(data["ideas"], idea_id)
            if idea.get("status") not in {"active", ""}:
                raise ValueError(f"Idea is not editable: {idea_id}")
            if title is not None:
                idea["title"] = title
                idea["id"] = self._unique_id(
                    title, [item["id"] for item in data["ideas"] if item is not idea]
                )
            if notes is not None:
                idea["notes"] = notes
            if tags is not None:
                idea["tags"] = self._normalize_tags(tags)
            idea["updated_at"] = now_iso()
            return self._idea(idea)

    def idea_archive(self, idea_id: str) -> Idea:
        with self._transaction() as data:
            idea = self._find_item(data["ideas"], idea_id)
            if idea.get("status") != "active":
                raise ValueError(f"Idea is not active: {idea_id}")
            idea["status"] = "archived"
            idea["updated_at"] = now_iso()
            idea["archived_at"] = idea["updated_at"]
            idea["outcome"] = "manual_archive"
            return self._idea(idea)

    def idea_promote_to_task(
        self,
        idea_id: str,
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> Task:
        with self._transaction() as data:
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
                return task
        raise FileNotFoundError(f"Idea not found: {idea_id}")

    def idea_promote_to_routine(
        self,
        idea_id: str,
        *,
        priority: str = "medium",
        next_due: str = "",
        notes: str = "",
        schedule: dict[str, Any] | None = None,
    ) -> Routine:
        with self._transaction() as data:
            slug = normalize_slug(idea_id)
            timestamp = now_iso()
            for idea in data["ideas"]:
                if idea.get("id") != slug:
                    continue
                if idea.get("status") == "promoted" and idea.get("promoted_routine_id"):
                    raise ValueError(f"Idea already promoted: {idea_id}")
                routine = self._new_routine(
                    data,
                    title=str(idea.get("title") or slug),
                    notes=self._combine_notes(str(idea.get("notes") or ""), notes),
                    tags=[str(tag) for tag in self._list(idea.get("tags"))],
                    priority=priority,
                    next_due=next_due,
                    schedule=schedule or {},
                    every_days=1,
                    timestamp=timestamp,
                )
                data["routines"].append(asdict(routine))
                idea["status"] = "promoted"
                idea["updated_at"] = timestamp
                idea["promoted_routine_id"] = routine.id
                idea["promoted_to_type"] = "routine"
                idea["promoted_to_id"] = routine.id
                return routine
        raise FileNotFoundError(f"Idea not found: {idea_id}")

    def task_add(self, request: AddTaskRequest) -> Task:
        with self._transaction() as data:
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
        return task

    def task_list(self, status: str = "pending", today: str | date | None = None) -> list[Task]:
        return self._task_list(status=status, today=today)

    def task_edit(
        self,
        task_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        due: str | None = None,
    ) -> Task:
        with self._transaction() as data:
            task = self._find_item(data["tasks"], task_id)
            if title is not None:
                task["title"] = title
            if notes is not None:
                task["notes"] = notes
            if tags is not None:
                task["tags"] = self._normalize_tags(tags)
            if priority is not None:
                task["priority"] = self._priority(priority)
            if due is not None:
                task["due"] = due
            task["updated_at"] = now_iso()
            return self._task(task)

    def task_complete(self, task_id: str) -> Task:
        return self._update_task_status(task_id, "done")

    def task_cancel(self, task_id: str) -> Task:
        return self._update_task_status(task_id, "cancelled")

    def routine_add(self, request: AddRoutineRequest) -> Routine:
        with self._transaction() as data:
            timestamp = now_iso()
            routine = self._new_routine(
                data,
                title=request.title,
                notes=request.notes,
                tags=request.tags,
                priority=request.priority,
                next_due=request.next_due,
                schedule=request.schedule,
                every_days=request.every_days,
                timestamp=timestamp,
            )
            data["routines"].append(asdict(routine))
        return routine

    def routine_list(self, status: str = "active") -> list[Routine]:
        return [
            self._routine(item)
            for item in self._load()["routines"]
            if not status or item.get("status") == status
        ]

    def routine_materialize_due(self, today: str | date | None = None) -> list[Task]:
        with self._transaction() as data:
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
                due_text = due.isoformat()
                if not self._routine_occurrence_exists(
                    data, str(routine.get("id") or ""), due_text
                ):
                    task = self._new_task(
                        data,
                        title=str(routine.get("title") or ""),
                        notes=str(routine.get("notes") or ""),
                        tags=[str(tag) for tag in self._list(routine.get("tags"))],
                        priority=str(routine.get("priority") or "medium"),
                        due=due_text,
                        timestamp=timestamp,
                    )
                    task_data = {**asdict(task), "source_routine_id": routine.get("id")}
                    data["tasks"].append(task_data)
                    generated = self._list(routine.get("generated_task_ids"))
                    generated.append(task_data["id"])
                    routine["generated_task_ids"] = generated
                    created.append(self._task(task_data))
                schedule = routine_schedule_from_item(routine)
                while next_due <= current:
                    next_due = advance_next_due(schedule, next_due)
                routine["next_due"] = next_due.isoformat()
                routine["last_materialized_due"] = due_text
                routine["updated_at"] = timestamp
        return created

    def routine_edit(
        self,
        routine_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        schedule: dict[str, Any] | None = None,
        next_due: str | None = None,
    ) -> Routine:
        with self._transaction() as data:
            routine = self._find_item(data["routines"], routine_id)
            if routine.get("status") == "archived":
                raise ValueError(f"Routine is archived: {routine_id}")
            if title is not None:
                routine["title"] = title
            if notes is not None:
                routine["notes"] = notes
            if tags is not None:
                routine["tags"] = self._normalize_tags(tags)
            if priority is not None:
                routine["priority"] = self._priority(priority)
            if schedule is not None:
                normalized = validate_routine_schedule(schedule)
                routine["schedule"] = normalized
                routine["every_days"] = schedule_every_days(normalized)
            if next_due is not None:
                self._parse_date(next_due)
                routine["next_due"] = next_due
            routine["updated_at"] = now_iso()
            return self._routine(routine)

    def routine_pause(self, routine_id: str) -> Routine:
        with self._transaction() as data:
            routine = self._find_item(data["routines"], routine_id)
            if routine.get("status") != "active":
                raise ValueError(f"Routine is not active: {routine_id}")
            routine["status"] = "paused"
            routine["updated_at"] = now_iso()
            return self._routine(routine)

    def routine_resume(self, routine_id: str, today: str | date | None = None) -> Routine:
        with self._transaction() as data:
            routine = self._find_item(data["routines"], routine_id)
            if routine.get("status") != "paused":
                raise ValueError(f"Routine is not paused: {routine_id}")
            current = self._coerce_date(today) if today is not None else date.today()
            schedule = routine_schedule_from_item(routine)
            next_due = next_due_on_or_after(schedule, current)
            routine["status"] = "active"
            routine["next_due"] = next_due.isoformat()
            routine["updated_at"] = now_iso()
            return self._routine(routine)

    def routine_archive(self, routine_id: str) -> Routine:
        with self._transaction() as data:
            routine = self._find_item(data["routines"], routine_id)
            if routine.get("status") == "archived":
                raise ValueError(f"Routine is already archived: {routine_id}")
            routine["status"] = "archived"
            routine["updated_at"] = now_iso()
            routine["archived_at"] = routine["updated_at"]
            routine["outcome"] = "manual_archive"
            return self._routine(routine)

    def task_digest(
        self,
        *,
        period: str = "weekly",
        today: str | date | None = None,
        notify: bool = False,
        sinks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        current = self._coerce_date(today) if today is not None else date.today()
        ideas = self.idea_list(status="active")
        tasks = self._task_list(status="pending", today=current)
        routines = self.routine_list(status="active")
        title = (
            f"📋 Alcove {normalize_slug(period) or 'weekly'} planner digest · {current.isoformat()}"
        )
        body = self._digest_body(
            ideas=ideas,
            tasks=tasks,
            routines=routines,
            current=current,
        )
        text = body
        notify_payload = {"status": "skipped", "reason": "notify disabled"}
        if notify:
            if self.home is None:
                raise ValueError("Task digest notification requires an Alcove Home")
            if sinks is None:
                sinks = self._configured_digest_sinks(period)
            notify_payload = self._notify_digest(title=title, body=body, sinks=sinks)
        return {
            "status": notify_payload.get("status", "built") if notify else "built",
            "period": period,
            "date": current.isoformat(),
            "title": title,
            "text": text,
            "items": {
                "ideas": [asdict(idea) for idea in ideas],
                "tasks": [asdict(task) for task in tasks],
                "routines": [asdict(routine) for routine in routines],
            },
            "counts": {
                "ideas": len(ideas),
                "tasks": len(tasks),
                "routines": len(routines),
            },
            "notify": notify_payload,
        }

    def run_due_notifications(
        self,
        today: str | date | None = None,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        reference_now = now or datetime.now().astimezone()
        current = self._coerce_date(today) if today is not None else reference_now.date()
        current_time = None if today is not None else reference_now.time()
        config = self._load_notification_config()
        digests = config.get("digests") if isinstance(config.get("digests"), dict) else {}
        state = self._load_notification_state()
        sent: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for period, raw_policy in digests.items():
            policy = raw_policy if isinstance(raw_policy, dict) else {}
            if not policy.get("enabled"):
                skipped.append({"period": period, "reason": "disabled"})
                continue
            if not digest_due(str(period), policy, current, current_time=current_time):
                skipped.append({"period": period, "reason": "not_due"})
                continue
            state_key = digest_state_key(str(period), current)
            if state.get(state_key):
                skipped.append({"period": period, "reason": "already_sent"})
                continue
            digest = self.task_digest(
                period=str(period),
                today=current,
                notify=bool(policy.get("notify", True)),
                sinks=notification_sinks(policy),
            )
            state[state_key] = now_iso()
            sent.append(digest)
        if sent:
            self._save_notification_state(state)
        return {
            "status": "checked",
            "sent": len(sent),
            "skipped": len(skipped),
            "digests": sent,
            "skipped_items": skipped,
        }

    def _update_task_status(self, task_id: str, status: str) -> Task:
        with self._transaction() as data:
            slug = normalize_slug(task_id)
            timestamp = now_iso()
            for item in data["tasks"]:
                if item.get("id") == slug:
                    item["status"] = status
                    item["updated_at"] = timestamp
                    if status == "done":
                        item["completed_at"] = timestamp
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

    def _new_routine(
        self,
        data: dict[str, list[dict]],
        *,
        title: str,
        notes: str,
        tags: list[str],
        priority: str,
        next_due: str,
        schedule: dict[str, Any],
        every_days: int,
        timestamp: str,
    ) -> Routine:
        normalized_schedule = (
            validate_routine_schedule(schedule)
            if schedule
            else {"frequency": "daily", "interval": max(int(every_days or 1), 1)}
        )
        due = next_due or date.today().isoformat()
        self._parse_date(due)
        return Routine(
            id=self._unique_id(title, [item["id"] for item in data["routines"]]),
            title=title,
            notes=notes,
            tags=self._normalize_tags(tags),
            status="active",
            priority=self._priority(priority),
            every_days=schedule_every_days(normalized_schedule),
            next_due=due,
            schedule=normalized_schedule,
            created_at=timestamp,
            updated_at=timestamp,
        )

    @contextmanager
    def _transaction(self) -> Iterator[dict[str, list[dict[str, Any]]]]:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.store_path.with_suffix(self.store_path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                data = self._load_unlocked()
                yield data
                self._save_unlocked(data)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        return self._load_unlocked()

    def _load_unlocked(self) -> dict[str, list[dict[str, Any]]]:
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

    def _save(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.with_suffix(self.store_path.suffix + ".lock").open(
            "a+", encoding="utf-8"
        ) as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                self._save_unlocked(data)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _save_unlocked(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _load_notification_config(self) -> dict[str, Any]:
        if not self.notification_config_path.is_file():
            return {}
        payload = yaml.safe_load(self.notification_config_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _load_notification_state(self) -> dict[str, str]:
        if not self.notification_state_path.is_file():
            return {}
        try:
            payload = json.loads(self.notification_state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return (
            {str(key): str(value) for key, value in payload.items()}
            if isinstance(payload, dict)
            else {}
        )

    def _save_notification_state(self, state: dict[str, str]) -> None:
        self.notification_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.notification_state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
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

    def _find_item(self, items: list[dict[str, Any]], item_id: str) -> dict[str, Any]:
        slug = normalize_slug(item_id)
        for item in items:
            candidate = str(item.get("id") or "")
            if candidate == slug or candidate.startswith(slug):
                return item
        raise FileNotFoundError(f"Task item not found: {item_id}")

    def _idea(self, item: dict[str, Any]) -> Idea:
        return Idea(
            id=str(item.get("id") or ""),
            title=str(item.get("title") or ""),
            notes=str(item.get("notes") or ""),
            tags=[str(tag) for tag in self._list(item.get("tags"))],
            status=str(item.get("status") or "active"),
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
            promoted_task_id=str(item.get("promoted_task_id") or ""),
            promoted_routine_id=str(item.get("promoted_routine_id") or ""),
        )

    def _task(self, item: dict[str, Any]) -> Task:
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
            source_routine_id=str(item.get("source_routine_id") or ""),
        )

    def _routine(self, item: dict[str, Any]) -> Routine:
        schedule = routine_schedule_from_item(item)
        return Routine(
            id=str(item.get("id") or ""),
            title=str(item.get("title") or ""),
            notes=str(item.get("notes") or ""),
            tags=[str(tag) for tag in self._list(item.get("tags"))],
            status=str(item.get("status") or "active"),
            priority=str(item.get("priority") or "medium"),
            every_days=schedule_every_days(schedule),
            next_due=str(item.get("next_due") or ""),
            schedule=schedule,
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
            last_materialized_due=str(item.get("last_materialized_due") or ""),
        )

    def _task_list(self, status: str = "pending", today: str | date | None = None) -> list[Task]:
        current = self._coerce_date(today) if today is not None else date.today()
        tasks = [
            item for item in self._load()["tasks"] if not status or item.get("status") == status
        ]

        def sort_key(item: dict[str, Any]) -> tuple[int, str, int, str]:
            due = str(item.get("due") or "")
            due_date = self._safe_parse_date(due)
            overdue_rank = 0 if due_date is not None and due_date < current else 1
            due_rank = due if due_date is not None else "9999-99-99"
            priority_rank = {"high": 0, "medium": 1, "low": 2}.get(
                str(item.get("priority") or "medium"),
                1,
            )
            return (overdue_rank, due_rank, priority_rank, str(item.get("created_at") or ""))

        return [self._task(item) for item in sorted(tasks, key=sort_key)]

    def _routine_occurrence_exists(
        self, data: dict[str, list[dict]], routine_id: str, due: str
    ) -> bool:
        return any(
            str(task.get("source_routine_id") or task.get("routine_id") or "") == routine_id
            and str(task.get("due") or "") == due
            for task in data["tasks"]
        )

    def _notify_digest(
        self,
        *,
        title: str,
        body: str,
        sinks: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        if self.home is None:
            raise ValueError("Task digest notification requires an Alcove Home")
        results: dict[str, dict[str, Any]] = {}
        for sink in notification_sinks({"sinks": sinks or []}):
            sink_type = str(sink.get("type") or "telegram")
            label = notification_sink_label(sink, results)
            if sink_type == "telegram":
                results[label] = send_telegram_message(
                    home=self.home,
                    text=self._digest_text(title=title, body=body),
                )
            elif sink_type == "feishu":
                results[label] = send_feishu_message(
                    home=self.home,
                    sink=sink,
                    title=title,
                    text=body,
                    report_path=None,
                )
            elif sink_type in {"tcb", "tmux_claude_bot"}:
                results[label] = send_tcb_notification(
                    sink=sink,
                    title=title,
                    text=body,
                    attachments=[],
                )
            else:
                results[label] = {
                    "status": "skipped",
                    "reason": f"unsupported notification sink: {sink_type}",
                }
        payload = {"status": combined_notification_status(results), "sinks": results}
        if set(results) == {"telegram"}:
            payload.update(results["telegram"])
            payload["sinks"] = results
        return payload

    def _configured_digest_sinks(self, period: str) -> list[dict[str, Any]]:
        config = self._load_notification_config()
        digests = config.get("digests") if isinstance(config.get("digests"), dict) else {}
        policy = digests.get(period)
        if not isinstance(policy, dict):
            policy = digests.get(normalize_slug(period))
        return notification_sinks(policy if isinstance(policy, dict) else {})

    def _digest_text(self, *, title: str, body: str) -> str:
        return "\n\n".join(section for section in [title, body] if section.strip())

    def _digest_body(
        self,
        *,
        ideas: list[Idea],
        tasks: list[Task],
        routines: list[Routine],
        current: date,
    ) -> str:
        sections: list[str] = []
        sections.append(
            self._digest_section(
                "✅ Pending tasks",
                [self._task_line(task, current=current) for task in tasks],
            )
        )
        sections.append(self._digest_section("💡 Ideas", [self._idea_line(idea) for idea in ideas]))
        sections.append(
            self._digest_section(
                "🔁 Active routines",
                [self._routine_line(routine, current=current) for routine in routines],
            )
        )
        return "\n\n".join(section for section in sections if section.strip())

    def _digest_section(self, title: str, rows: list[str]) -> str:
        if not rows:
            return f"{title}: none"
        return "\n".join(
            [
                f"{title} ({len(rows)})",
                "",
                *[f"{index}. {row}" for index, row in enumerate(rows, 1)],
            ]
        )

    def _task_line(self, task: Task, *, current: date) -> str:
        details = [f"Priority: {task.priority}"]
        if task.due:
            details.append(f"Due: {task.due}")
            overdue = self._overdue_label(task.due, current=current)
            if overdue:
                details.append(overdue)
        line = self._task_display_title(task)
        if task.notes:
            details.append(f"Note: {task.notes}")
        return "\n   ".join([line, *details])

    def _task_display_title(self, task: Task) -> str:
        if task.source_routine_id:
            return f"{task.title} (routine due)"
        return task.title

    def _idea_line(self, idea: Idea) -> str:
        if not idea.notes:
            return idea.title
        return f"{idea.title}\n   Note: {idea.notes}"

    def _routine_line(self, routine: Routine, *, current: date) -> str:
        details = [routine.title, f"Next: {routine.next_due}"]
        overdue = self._overdue_label(routine.next_due, current=current)
        if overdue:
            details.append(overdue)
        details.append(f"Frequency: {self._routine_frequency_label(routine.schedule)}")
        return "\n   ".join(details)

    def _overdue_label(self, value: str, *, current: date) -> str:
        due = self._safe_parse_date(value)
        if due is None or due >= current:
            return ""
        days = (current - due).days
        suffix = "s" if days != 1 else ""
        return f"Overdue: {days} day{suffix}"

    def _routine_frequency_label(self, schedule: dict[str, Any]) -> str:
        frequency = str(schedule.get("frequency") or "daily")
        interval = max(int(schedule.get("interval") or 1), 1)
        if frequency == "daily":
            return "daily" if interval == 1 else f"every {interval} days"
        if frequency == "weekly":
            weekdays = [str(day) for day in self._list(schedule.get("weekdays"))]
            day_text = f" on {', '.join(weekdays)}" if weekdays else ""
            return f"weekly{day_text}" if interval == 1 else f"every {interval} weeks{day_text}"
        if frequency == "monthly":
            day = int(schedule.get("day_of_month") or 0)
            day_text = f" on day {day}" if day else ""
            return f"monthly{day_text}" if interval == 1 else f"every {interval} months{day_text}"
        return frequency

    def _combine_notes(self, base: str, extra: str) -> str:
        values = [value.strip() for value in (base, extra) if value.strip()]
        return "\n\n".join(values)

    def _coerce_date(self, value: str | date) -> date:
        if isinstance(value, date):
            return value
        return self._parse_date(value)

    def _parse_date(self, value: str) -> date:
        return datetime.strptime(value, "%Y-%m-%d").date()

    def _safe_parse_date(self, value: str) -> date | None:
        try:
            return self._parse_date(value)
        except ValueError:
            return None

    def _list(self, value: object) -> list[Any]:
        return value if isinstance(value, list) else []
