from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from alcove import __version__
from alcove.errors import AlcoveError
from alcove.inbox import InboxModule, InboxNoteRequest
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alcove")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Initialize an Alcove workspace")
    init.add_argument("path", nargs="?", default=".")

    status = sub.add_parser("status", help="Show workspace status")
    status.add_argument("path", nargs="?", default=".")
    status.add_argument("--json", action="store_true")

    inbox = sub.add_parser("inbox", help="Work with inbox items")
    inbox.add_argument("--workspace", required=True)
    inbox_sub = inbox.add_subparsers(dest="inbox_command", required=True)
    inbox_sub.add_parser("peek", help="Show the oldest inbox item")
    inbox_note = inbox_sub.add_parser("note", help="Archive an inbox item into knowledge")
    inbox_note.add_argument("name")
    inbox_note.add_argument("topic")
    inbox_note.add_argument("--summary", required=True)
    inbox_note.add_argument("--tag", action="append", default=[])

    knowledge = sub.add_parser("knowledge", help="Work with knowledge notes")
    knowledge.add_argument("--workspace", required=True)
    knowledge_sub = knowledge.add_subparsers(dest="knowledge_command", required=True)
    note_source = knowledge_sub.add_parser("note-source", help="Record a source note")
    note_source.add_argument("--platform", required=True)
    note_source.add_argument("--title", required=True)
    note_source.add_argument("--topic", required=True)
    note_source.add_argument("--resource", default="")
    note_source.add_argument("--summary", required=True)
    note_source.add_argument("--tag", action="append", default=[])

    search = sub.add_parser("search", help="Search knowledge")
    search.add_argument("query")
    search.add_argument("--workspace", required=True)
    search.add_argument("--json", action="store_true")
    return parser


def _print_inbox_post(post) -> None:
    date = post.date or ""
    print(f"{post.platform} | {date} | {post.title}")
    print(f"path: {post.path}")
    print(f"source: {post.source or ''}")
    print(f"content_source: {post.content_source}")
    print()
    print(post.content)


def _print_path(label: str, path: Path | None) -> None:
    if path is not None:
        print(f"{label}: {path}")


def _argument_error(parser: argparse.ArgumentParser, message: str) -> int:
    parser.print_usage(sys.stderr)
    print(f"{parser.prog}: error: {message}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    try:
        if args.version:
            print(f"alcove {__version__}")
            return 0
        if args.command is None:
            return _argument_error(parser, "the following arguments are required: command")
        if args.command == "init":
            workspace = Workspace.init(Path(args.path))
            print(f"Initialized Alcove workspace at {workspace.root}")
            return 0
        if args.command == "status":
            workspace = Workspace.discover(Path(args.path))
            status = workspace.status()
            if args.json:
                print(json.dumps(status, ensure_ascii=False, indent=2))
            else:
                print(f"Alcove workspace: {status['root']}")
            return 0
        if args.command == "inbox":
            workspace = Workspace.discover(Path(args.workspace))
            inbox = InboxModule(workspace)
            if args.inbox_command == "peek":
                post = inbox.peek()
                if post is None:
                    print("Inbox is empty.")
                else:
                    _print_inbox_post(post)
                return 0
            if args.inbox_command == "note":
                result = inbox.note(
                    InboxNoteRequest(
                        name=args.name,
                        topic=args.topic,
                        summary=args.summary,
                        tags=args.tag,
                    )
                )
                _print_path("archive", result.archive_path)
                _print_path("source", result.source_path)
                _print_path("concept", result.concept_path)
                return 0
            return _argument_error(parser, "the following arguments are required: inbox_command")
        if args.command == "knowledge":
            workspace = Workspace.discover(Path(args.workspace))
            knowledge = KnowledgeModule(workspace)
            if args.knowledge_command == "note-source":
                result = knowledge.note_source(
                    NoteSourceRequest(
                        platform=args.platform,
                        title=args.title,
                        topic=args.topic,
                        resource=args.resource,
                        summary=args.summary,
                        tags=args.tag,
                    )
                )
                _print_path("source", result.source_path)
                _print_path("concept", result.concept_path)
                return 0
            return _argument_error(
                parser,
                "the following arguments are required: knowledge_command",
            )
        if args.command == "search":
            workspace = Workspace.discover(Path(args.workspace))
            results = SearchModule(workspace).search(SearchRequest(query=args.query))
            if args.json:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            else:
                for row in results:
                    print(
                        f"{row.get('type')} | {row.get('topic')} | "
                        f"{row.get('title')} | {row.get('path')}"
                    )
            return 0
        return _argument_error(parser, "the following arguments are required: command")
    except (AlcoveError, FileNotFoundError, ValueError) as exc:
        print(f"alcove: {exc}", file=sys.stderr)
        return 2


def entrypoint() -> None:
    raise SystemExit(main())
