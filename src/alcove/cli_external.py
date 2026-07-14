from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.connectors.apple_notes import AppleNotesImportRequest, AppleNotesLocalImportRequest
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksImportRequest,
    ChromeBookmarksLocalImportRequest,
)
from alcove.connectors.github_stars import GitHubStarsImportRequest, GitHubStarsUrlImportRequest
from alcove.linking import LinkSourceRequest
from alcove.mounts import AddMountRequest, MountIndexPolicy


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]
TagReader = Callable[[Any], list[str]]
PathPrinter = Callable[[str, Path | None], None]


def handle_mount_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: TagReader,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.mount_command == "add":
        payload = app.external.mount_add_payload(
            AddMountRequest(
                path=args.path,
                name=args.name,
                mount_type=args.type,
                tags=tags_from_args(args),
                index_policy=MountIndexPolicy(
                    profile=args.profile,
                    include=args.include,
                    exclude=args.exclude,
                    max_file_size_kb=args.max_file_size_kb,
                ),
            )
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"mount: {payload['mount']['id']}")
        return 0
    if args.mount_command == "update":
        payload = app.external.mount_update_policy_payload(
            args.mount_id,
            MountIndexPolicy(
                profile=args.profile,
                include=args.include,
                exclude=args.exclude,
                max_file_size_kb=args.max_file_size_kb,
            ),
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"mount updated: {payload['mount']['id']}")
        return 0
    if args.mount_command == "list":
        payload = app.external.mount_list_payload(args.status)
        results = payload["mounts"]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for mount in results:
                print(f"{mount['type']} | {mount['name']} | {mount['path']}")
        return 0
    if args.mount_command == "scan":
        report = app.external.mount_scan_payload(
            args.mount_id,
            include_diagnostics=args.include_diagnostics,
            dry_run=args.dry_run,
        )
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"scanned: {report['scanned']}, skipped: {report['skipped']}")
        return 0
    return argument_error(parser, "the following arguments are required: mount_command")


def handle_connector_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    tags_from_args: TagReader,
    argument_error: ArgumentError,
) -> int:
    app = AlcoveApplication(runtime_from_args(args))
    if args.connector_command == "status":
        payload = app.external.connector_status_payload(args.connector)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for source in payload["sources"]:
                print(
                    f"{source['connector']}/{source['id']} | {source['status']} | "
                    f"{source['item_count']} items | checked: {source['checked_at']}"
                )
        return 0
    if args.connector_command == "refresh":
        payload = app.external.connector_refresh_payload(
            connector=args.connector,
            stale_only=not args.all,
        )
        if args.json:
            print(
                json.dumps(
                    connector_cli_report(
                        payload,
                        include_items=False,
                        include_diff=args.include_diff,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            print(f"refreshed: {payload['refreshed']}, skipped: {payload['skipped']}")
        return 0
    if args.connector_command == "fetch":
        payload = app.external.connector_fetch_payload(args.item_path)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(
                f"{payload['connector']} | {payload['relative_path']} | {payload['item']['title']}"
            )
        return 0
    if args.connector_command == "apple-notes":
        return _handle_apple_notes(
            args, parser, app=app, tags_from_args=tags_from_args, argument_error=argument_error
        )
    if args.connector_command == "github-stars":
        return _handle_github_stars(
            args, parser, app=app, tags_from_args=tags_from_args, argument_error=argument_error
        )
    if args.connector_command == "chrome-bookmarks":
        return _handle_chrome_bookmarks(
            args, parser, app=app, tags_from_args=tags_from_args, argument_error=argument_error
        )
    return argument_error(parser, "the following arguments are required: connector_command")


def handle_link_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    print_path: PathPrinter,
    argument_error: ArgumentError,
) -> int:
    if args.link_command != "source":
        return argument_error(parser, "the following arguments are required: link_command")
    result = AlcoveApplication(runtime_from_args(args)).external.link_source_payload(
        LinkSourceRequest(
            item_path=args.item_path,
            topic=args.topic,
            summary=args.summary,
            create_concept=args.create_concept,
        )
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_path("source", Path(result["source_path"]))
        print_path("concept", Path(result["concept_path"]) if result["concept_path"] else None)
    return 0


def _handle_apple_notes(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    app: AlcoveApplication,
    tags_from_args: TagReader,
    argument_error: ArgumentError,
) -> int:
    if args.apple_notes_command == "index":
        report = app.external.apple_notes_index_payload(
            AppleNotesImportRequest(export_dir=args.export_dir, tags=tags_from_args(args))
        )
        return _print_connector_index_report(args, report)
    if args.apple_notes_command == "import-local":
        report = app.external.apple_notes_import_local_payload(
            AppleNotesLocalImportRequest(
                export_dir=args.export_dir,
                tags=tags_from_args(args),
                source_id=args.source_id,
            )
        )
        if args.json:
            print(
                json.dumps(
                    connector_cli_report(
                        report,
                        include_items=args.include_items,
                        include_diff=args.include_diff,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            export_dir = connector_storage_path(report, "export_dir")
            print(
                f"imported: {report['exported']}, indexed: {report['scanned']}, "
                f"skipped: {report['skipped']}, export: {export_dir}"
            )
        return 0
    if args.apple_notes_command == "refresh":
        return _print_connector_refresh_report(
            args,
            app.external.connector_refresh_payload(
                connector="apple-notes",
                stale_only=not args.force,
                source_id=args.source_id,
            ),
        )
    return argument_error(parser, "the following arguments are required: apple_notes_command")


def _handle_github_stars(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    app: AlcoveApplication,
    tags_from_args: TagReader,
    argument_error: ArgumentError,
) -> int:
    if args.github_stars_command == "index":
        report = app.external.github_stars_index_payload(
            GitHubStarsImportRequest(export_file=args.export_file, tags=tags_from_args(args))
        )
        return _print_connector_index_report(args, report)
    if args.github_stars_command == "import-url":
        report = app.external.github_stars_import_url_payload(
            GitHubStarsUrlImportRequest(
                source=args.source,
                export_file=args.export_file,
                tags=tags_from_args(args),
                limit=args.limit,
                max_pages=args.max_pages,
            )
        )
        if args.json:
            print(
                json.dumps(
                    connector_cli_report(
                        report,
                        include_items=args.include_items,
                        include_diff=args.include_diff,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            export_file = connector_storage_path(report, "export_file")
            print(
                f"imported: {report['exported']}, indexed: {report['scanned']}, "
                f"skipped: {report['skipped']}, export: {export_file}"
            )
        return 0
    if args.github_stars_command == "refresh":
        return _print_connector_refresh_report(
            args,
            app.external.connector_refresh_payload(
                connector="github-stars",
                stale_only=not args.force,
                source_id=args.source_id,
            ),
        )
    return argument_error(parser, "the following arguments are required: github_stars_command")


def _handle_chrome_bookmarks(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    app: AlcoveApplication,
    tags_from_args: TagReader,
    argument_error: ArgumentError,
) -> int:
    if args.chrome_bookmarks_command == "index":
        report = app.external.chrome_bookmarks_index_payload(
            ChromeBookmarksImportRequest(export_file=args.export_file, tags=tags_from_args(args))
        )
        return _print_connector_index_report(args, report)
    if args.chrome_bookmarks_command == "import-local":
        report = app.external.chrome_bookmarks_import_local_payload(
            ChromeBookmarksLocalImportRequest(
                source_file=args.source_file,
                profile=args.profile,
                source_id=args.source_id,
                tags=tags_from_args(args),
            )
        )
        if args.json:
            print(
                json.dumps(
                    connector_cli_report(
                        report,
                        include_items=args.include_items,
                        include_diff=args.include_diff,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            source_file = connector_storage_path(report, "source_file")
            print(
                f"imported: {report['exported']}, indexed: {report['scanned']}, "
                f"skipped: {report['skipped']}, source: {source_file}"
            )
        return 0
    if args.chrome_bookmarks_command == "refresh":
        return _print_connector_refresh_report(
            args,
            app.external.connector_refresh_payload(
                connector="chrome-bookmarks",
                stale_only=not args.force,
                source_id=args.source_id,
            ),
        )
    return argument_error(parser, "the following arguments are required: chrome_bookmarks_command")


def _print_connector_index_report(args: Any, report: dict[str, Any]) -> int:
    if args.json:
        print(
            json.dumps(
                connector_cli_report(report, include_items=args.include_items),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"indexed: {report['scanned']}, skipped: {report['skipped']}")
    return 0


def _print_connector_refresh_report(args: Any, payload: dict[str, Any]) -> int:
    if args.json:
        print(
            json.dumps(
                connector_cli_report(
                    payload,
                    include_items=False,
                    include_diff=args.include_diff,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"refreshed: {payload['refreshed']}, skipped: {payload['skipped']}")
    return 0


def connector_cli_report(
    report: dict[str, Any],
    *,
    include_items: bool,
    include_diff: bool = False,
) -> dict[str, Any]:
    payload = dict(report)
    move_connector_storage_paths(payload)
    items = payload.get("items")
    if isinstance(items, list):
        payload["item_count"] = len(items)
        if not include_items:
            payload.pop("items", None)
    summarize_diff_payload(payload, include_diff=include_diff)
    for source in payload.get("sources", []):
        if isinstance(source, dict):
            move_connector_storage_paths(source)
            summarize_diff_payload(source, include_diff=include_diff)
    return payload


def move_connector_storage_paths(payload: dict[str, Any]) -> None:
    for key in ["export_file", "export_dir", "index_path", "source_file"]:
        if key in payload:
            payload.pop(key)


def connector_storage_path(payload: dict[str, Any], key: str) -> object:
    if key in payload:
        return payload[key]
    debug_value = payload.get("debug")
    debug: dict[str, Any] = debug_value if isinstance(debug_value, dict) else {}
    storage_value = debug.get("storage")
    storage = storage_value if isinstance(storage_value, dict) else {}
    return storage.get(key, "")


def summarize_diff_payload(payload: dict[str, Any], *, include_diff: bool) -> None:
    diff = payload.get("diff")
    if not isinstance(diff, dict):
        return
    if include_diff:
        return
    payload["diff_summary"] = {
        "added_count": len(diff.get("added") or []),
        "removed_count": len(diff.get("removed") or []),
        "updated_count": len(diff.get("updated") or []),
        "unchanged": int(diff.get("unchanged") or 0),
    }
    payload.pop("diff", None)
