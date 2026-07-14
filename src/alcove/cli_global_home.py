from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.pins import AddPinRequest, UpdatePinRequest
from alcove.projects import AddProjectRequest


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]
ListReader = Callable[[Any], list[str]]
OptionalListReader = Callable[[Any], list[str] | None]
PathPrinter = Callable[[str, Path | None], None]


def handle_pin_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: ListReader,
    refs_from_args: ListReader,
    resources_from_args: ListReader,
    optional_tags_from_args: OptionalListReader,
    optional_refs_from_args: OptionalListReader,
    optional_resources_from_args: OptionalListReader,
    print_path: PathPrinter,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.pin_command == "add":
        payload = app.global_home.pin_add_payload(
            AddPinRequest(
                title=args.title,
                description=args.description,
                summary=args.summary,
                content=args.content,
                kind=args.kind,
                tags=tags_from_args(args),
                priority=args.priority,
                source_refs=refs_from_args(args),
                resources=resources_from_args(args),
                content_format=args.content_format,
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print_path("pin", Path(payload["path"]))
        return 0
    if args.pin_command == "get":
        payload = app.global_home.pin_get_payload(args.pin_id)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            pin = payload["pin"]
            print(f"{pin['priority']} | {pin['kind']} | {pin['status']} | {pin['title']}")
            if pin.get("summary"):
                print(pin["summary"])
            if pin.get("content"):
                print(pin["content"])
        return 0
    if args.pin_command == "list":
        payload = app.global_home.pin_list_payload(args.tag, args.status)
        return _print_pin_rows(payload["pins"], json_output=args.json)
    if args.pin_command == "search":
        payload = app.global_home.pin_search_payload(
            query=args.query,
            kind=args.kind,
            tag=args.tag,
            status=args.status,
        )
        return _print_pin_rows(payload["pins"], json_output=args.json)
    if args.pin_command == "update":
        payload = app.global_home.pin_update_payload(
            UpdatePinRequest(
                pin_id=args.pin_id,
                title=args.title,
                description=args.description,
                summary=args.summary,
                content=args.content,
                kind=args.kind,
                tags=optional_tags_from_args(args),
                priority=args.priority,
                source_refs=optional_refs_from_args(args),
                resources=optional_resources_from_args(args),
                status=args.status,
                content_format=args.content_format,
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"{payload['status']}: {payload['path']}")
        return 0
    if args.pin_command == "rebuild-index":
        payload = app.global_home.pin_rebuild_index_payload()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"{payload['status']}: {payload['index_path']}")
        return 0
    if args.pin_command == "render-html":
        payload = app.global_home.pin_render_html_payload(args.output)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"{payload['status']}: {payload['path']}")
        return 0
    if args.pin_command == "archive":
        payload = app.global_home.pin_archive_payload(args.pin_id, confirm=args.confirm)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"{payload['status']}: {payload['path']}")
        return 0
    return argument_error(parser, "the following arguments are required: pin_command")


def handle_project_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.project_command == "add":
        payload = app.global_home.project_add_payload(
            AddProjectRequest(alias=args.alias, path=args.path, note=args.note)
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"project: {payload['project']['alias']} | {payload['project']['path']}")
        return 0
    if args.project_command == "get":
        payload = app.global_home.project_get_payload(args.alias)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            project = payload["project"]
            print(f"{project['alias']} | {project['path']} | {project['note']}")
        return 0
    if args.project_command == "find":
        payload = app.global_home.project_find_payload(args.keyword)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for project in payload["projects"]:
                print(f"{project['source']} | {project['alias']} | {project['path']}")
        return 0
    if args.project_command == "list":
        payload = app.global_home.project_list_payload()
        if args.json:
            print(json.dumps(payload["projects"], ensure_ascii=False, indent=2))
        else:
            for project in payload["projects"]:
                print(f"{project['alias']} | {project['path']} | {project['note']}")
        return 0
    if args.project_command == "remove":
        payload = app.global_home.project_remove_payload(args.alias)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"{payload['status']}: {args.alias}")
        return 0
    if args.project_command == "roots-set":
        payload = app.global_home.project_roots_set_payload(args.roots)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("roots: " + ", ".join(payload["roots"]))
        return 0
    return argument_error(parser, "the following arguments are required: project_command")


def _print_pin_rows(rows: list[dict[str, Any]], *, json_output: bool) -> int:
    if json_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for pin in rows:
            print(
                f"{pin['priority']} | {pin['kind']} | {pin['status']} | "
                f"{pin['title']} | {pin['path']}"
            )
    return 0
