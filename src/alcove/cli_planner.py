from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]
ListReader = Callable[[Any], list[str]]
OptionalListReader = Callable[[Any], list[str] | None]
ScheduleReader = Callable[..., dict[str, Any]]


def handle_idea_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: ListReader,
    optional_tags_from_args: OptionalListReader,
    routine_schedule_from_args: ScheduleReader,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.idea_command == "add":
        payload = app.global_home.idea_add_payload(
            AddIdeaRequest(
                title=args.title,
                notes=args.notes,
                tags=tags_from_args(args),
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"idea: {payload['idea']['id']}")
        return 0
    if args.idea_command == "list":
        payload = app.global_home.idea_list_payload(args.status)
        results = payload["ideas"]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for idea in results:
                print(f"{idea['status']} | {idea['title']} | {idea['id']}")
        return 0
    if args.idea_command == "promote":
        payload = app.global_home.idea_promote_payload(
            args.idea_id,
            priority=args.priority,
            due=args.due,
            notes=args.notes,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"task: {payload['task']['id']}")
        return 0
    if args.idea_command == "edit":
        payload = app.global_home.idea_edit_payload(
            args.idea_id,
            title=args.title,
            notes=args.notes,
            tags=optional_tags_from_args(args),
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"idea: {payload['idea']['id']}")
        return 0
    if args.idea_command == "archive":
        payload = app.global_home.idea_archive_payload(args.idea_id)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"idea: {payload['idea']['id']}")
        return 0
    if args.idea_command == "promote-routine":
        payload = app.global_home.idea_promote_routine_payload(
            args.idea_id,
            priority=args.priority,
            next_due=args.next_due,
            notes=args.notes,
            schedule=routine_schedule_from_args(args, include_default=True),
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"routine: {payload['routine']['id']}")
        return 0
    return argument_error(parser, "the following arguments are required: idea_command")


def handle_task_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: ListReader,
    optional_tags_from_args: OptionalListReader,
    routine_schedule_from_args: ScheduleReader,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.task_command == "add":
        payload = app.global_home.task_add_payload(
            AddTaskRequest(
                title=args.title,
                notes=args.notes,
                tags=tags_from_args(args),
                priority=args.priority,
                due=args.due,
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"task: {payload['task']['id']}")
        return 0
    if args.task_command == "list":
        payload = app.global_home.task_list_payload(args.status)
        results = payload["tasks"]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for task in results:
                print(f"{task['priority']} | {task['status']} | {task['title']} | {task['id']}")
        return 0
    if args.task_command == "edit":
        payload = app.global_home.task_edit_payload(
            args.task_id,
            title=args.title,
            notes=args.notes,
            tags=optional_tags_from_args(args),
            priority=args.priority,
            due=args.due,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"task: {payload['task']['id']}")
        return 0
    if args.task_command == "complete":
        payload = app.global_home.task_complete_payload(args.task_id)
        print(json.dumps(payload, ensure_ascii=False) if args.json else payload["task"]["id"])
        return 0
    if args.task_command == "cancel":
        payload = app.global_home.task_cancel_payload(args.task_id)
        print(json.dumps(payload, ensure_ascii=False) if args.json else payload["task"]["id"])
        return 0
    if args.task_command == "routine-add":
        payload = app.global_home.routine_add_payload(
            AddRoutineRequest(
                title=args.title,
                notes=args.notes,
                tags=tags_from_args(args),
                priority=args.priority,
                every_days=args.every_days,
                next_due=args.next_due,
                schedule=routine_schedule_from_args(args),
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"routine: {payload['routine']['id']}")
        return 0
    if args.task_command == "routine-list":
        payload = app.global_home.routine_list_payload(args.status)
        results = payload["routines"]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for routine in results:
                print(
                    f"{routine['priority']} | {routine['status']} | "
                    f"{routine['next_due']} | {routine['title']} | {routine['id']}"
                )
        return 0
    if args.task_command == "routine-edit":
        payload = app.global_home.routine_edit_payload(
            args.routine_id,
            title=args.title,
            notes=args.notes,
            tags=optional_tags_from_args(args),
            priority=args.priority,
            schedule=routine_schedule_from_args(args) or None,
            next_due=args.next_due,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"routine: {payload['routine']['id']}")
        return 0
    if args.task_command == "routine-pause":
        payload = app.global_home.routine_pause_payload(args.routine_id)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"routine: {payload['routine']['id']}")
        return 0
    if args.task_command == "routine-resume":
        payload = app.global_home.routine_resume_payload(args.routine_id, today=args.today)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"routine: {payload['routine']['id']}")
        return 0
    if args.task_command == "routine-archive":
        payload = app.global_home.routine_archive_payload(args.routine_id)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"routine: {payload['routine']['id']}")
        return 0
    if args.task_command == "materialize-due":
        payload = app.global_home.routine_materialize_due_payload(args.today)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"created: {len(payload['created'])}")
        return 0
    if args.task_command == "digest":
        payload = app.global_home.task_digest_payload(
            period=args.period,
            today=args.today,
            notify=args.notify,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(payload["text"])
        return 0
    return argument_error(parser, "the following arguments are required: task_command")
