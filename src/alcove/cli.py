from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from alcove import __version__
from alcove.classify import ClassifyModule
from alcove.errors import AlcoveError
from alcove.gardener import GardenerModule
from alcove.inbox import InboxModule, InboxNoteRequest
from alcove.knowledge import (
    AddConceptRequest,
    AddEntityRequest,
    AddQuestionRequest,
    KnowledgeModule,
    NoteSourceRequest,
)
from alcove.lifecycle import LifecycleModule
from alcove.search import SearchModule, SearchRequest
from alcove.validate import ValidateModule
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
    inbox_peek = inbox_sub.add_parser("peek", help="Show the oldest inbox item")
    inbox_peek.add_argument("--json", action="store_true")
    inbox_read = inbox_sub.add_parser("read", help="Read an inbox item")
    inbox_read.add_argument("name")
    inbox_read.add_argument("--json", action="store_true")
    inbox_classify = inbox_sub.add_parser("classify", help="Suggest topic, tags, and summary")
    inbox_classify.add_argument("name")
    inbox_classify.add_argument("topic", nargs="?")
    inbox_archive = inbox_sub.add_parser("archive", help="Archive an inbox item as Source")
    inbox_archive.add_argument("name")
    inbox_archive.add_argument("topic")
    inbox_archive.add_argument("--summary", default="")
    inbox_archive.add_argument("--tag", action="append", default=[])
    inbox_archive.add_argument("--tags", default="")
    inbox_archive.add_argument("--no-auto-tags", action="store_true")
    inbox_archive.add_argument("--supersede-similar", action="store_true")
    inbox_archive.add_argument("--validate", action="store_true")
    inbox_archive.add_argument("--json", action="store_true")
    inbox_note = inbox_sub.add_parser("note", help="Archive an inbox item into knowledge")
    inbox_note.add_argument("name")
    inbox_note.add_argument("topic")
    inbox_note.add_argument("--summary", required=True)
    inbox_note.add_argument("--tag", action="append", default=[])
    inbox_note.add_argument("--tags", default="")
    inbox_note.add_argument("--selected-takeaways", default="")
    inbox_note.add_argument("--why", default="")
    inbox_note.add_argument("--connection", default="")
    inbox_note.add_argument("--action", default="")
    inbox_note.add_argument("--personal-note", default="")
    inbox_note.add_argument("--no-auto-tags", action="store_true")
    inbox_note.add_argument("--supersede-similar", action="store_true")
    inbox_note.add_argument("--validate", action="store_true")
    inbox_note.add_argument("--json", action="store_true")
    inbox_todo = inbox_sub.add_parser("todo", help="Move an inbox item to todo")
    inbox_todo.add_argument("name")
    inbox_todo.add_argument("reason", nargs="?", default="")
    inbox_delete = inbox_sub.add_parser("delete", help="Delete an inbox item")
    inbox_delete.add_argument("name")
    inbox_delete.add_argument("--confirm", action="store_true")

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
    add_note = knowledge_sub.add_parser("add-note", help="Add a standalone concept")
    add_note.add_argument("topic")
    add_note.add_argument("title")
    add_note.add_argument("--summary", default="")
    add_note.add_argument("--tag", action="append", default=[])
    add_note.add_argument("--tags", default="")
    add_question = knowledge_sub.add_parser("add-question", help="Add a reusable question")
    add_question.add_argument("topic")
    add_question.add_argument("question")
    add_question.add_argument("--answer", default="")
    add_question.add_argument("--tag", action="append", default=[])
    add_question.add_argument("--tags", default="")
    add_question.add_argument("--source-ref", action="append", default=[])
    add_question.add_argument("--source-refs", default="")
    add_entity = knowledge_sub.add_parser("add-entity", help="Add a reusable entity")
    add_entity.add_argument("topic")
    add_entity.add_argument("name")
    add_entity.add_argument("--kind", default="object")
    add_entity.add_argument("--summary", default="")
    add_entity.add_argument("--use-cases", default="")
    add_entity.add_argument("--open-questions", default="")
    add_entity.add_argument("--tag", action="append", default=[])
    add_entity.add_argument("--tags", default="")
    add_entity.add_argument("--source-ref", action="append", default=[])
    add_entity.add_argument("--source-refs", default="")
    promote = knowledge_sub.add_parser("promote", help="Promote a Source to a Concept")
    promote.add_argument("source")
    promote.add_argument("--topic", default="")
    promote.add_argument("--summary", default="")
    refresh = knowledge_sub.add_parser("refresh", help="Refresh a topic concept from active sources")
    refresh.add_argument("topic")
    refresh.add_argument("--in-place", action="store_true")
    refresh.add_argument("--summary", default="")
    knowledge_sub.add_parser("topics", help="List known topics/tags/domains")

    validate = sub.add_parser("validate", help="Validate an Alcove workspace")
    validate.add_argument("--workspace", required=True)
    validate.add_argument("--strict-quality", action="store_true")
    validate.add_argument("--json", action="store_true")

    gardener = sub.add_parser("gardener", help="Scan knowledge health")
    gardener.add_argument("--workspace", required=True)
    gardener.add_argument("--prune", action="store_true")
    gardener.add_argument("--json", action="store_true")

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


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _tags(args) -> list[str]:
    return [*getattr(args, "tag", []), *_split_csv(getattr(args, "tags", ""))]


def _refs(args) -> list[str]:
    return [*getattr(args, "source_ref", []), *_split_csv(getattr(args, "source_refs", ""))]


def _selected_takeaways(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").replace("、", ",").split(",") if item.strip()]


def _process_result_dict(result) -> dict:
    return {
        "archive": str(result.archive_path),
        "source": str(result.source_path),
        "concept": str(result.concept_path) if result.concept_path else "",
        "tags": result.tags,
        "confidence": result.confidence,
        "superseded": result.superseded,
    }


def _with_validation(payload: dict, workspace: Workspace, enabled: bool) -> dict:
    if enabled:
        return {**payload, "validation": ValidateModule(workspace).validate()}
    return payload


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
                    if args.json:
                        print(json.dumps({"error": "inbox empty"}, ensure_ascii=False))
                    else:
                        print("Inbox is empty.")
                else:
                    if args.json:
                        print(json.dumps(asdict(post), ensure_ascii=False, default=str))
                    else:
                        _print_inbox_post(post)
                return 0
            if args.inbox_command == "read":
                post = inbox.read(args.name)
                if args.json:
                    print(json.dumps(asdict(post), ensure_ascii=False, default=str))
                else:
                    _print_inbox_post(post)
                return 0
            if args.inbox_command == "classify":
                draft = ClassifyModule(workspace).classify(args.name, args.topic)
                print(json.dumps(asdict(draft), ensure_ascii=False, default=str))
                return 0
            if args.inbox_command == "archive":
                result = inbox.archive(
                    args.name,
                    args.topic,
                    summary=args.summary,
                    tags=_tags(args) or None,
                    no_auto_tags=args.no_auto_tags,
                    supersede_similar=args.supersede_similar,
                )
                payload = _with_validation(_process_result_dict(result), workspace, args.validate)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, default=str))
                else:
                    _print_path("archive", result.archive_path)
                    _print_path("source", result.source_path)
                    print(f"tags: {','.join(result.tags)}")
                return 0
            if args.inbox_command == "note":
                result = inbox.note(
                    InboxNoteRequest(
                        name=args.name,
                        topic=args.topic,
                        summary=args.summary,
                        tags=_tags(args),
                        selected_takeaways=_selected_takeaways(args.selected_takeaways),
                        why=args.why,
                        connection=args.connection,
                        action=args.action,
                        personal_note=args.personal_note,
                        no_auto_tags=args.no_auto_tags,
                        supersede_similar=args.supersede_similar,
                    )
                )
                payload = _with_validation(_process_result_dict(result), workspace, args.validate)
                if args.json:
                    print(json.dumps(payload, ensure_ascii=False, default=str))
                else:
                    _print_path("archive", result.archive_path)
                    _print_path("source", result.source_path)
                    _print_path("concept", result.concept_path)
                    print(f"tags: {','.join(result.tags)}")
                return 0
            if args.inbox_command == "todo":
                path = inbox.todo(args.name, args.reason)
                print(json.dumps({"status": "todo", "path": str(path)}, ensure_ascii=False))
                return 0
            if args.inbox_command == "delete":
                print(json.dumps(inbox.delete(args.name, confirm=args.confirm), ensure_ascii=False))
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
            if args.knowledge_command == "add-note":
                result = knowledge.add_concept(
                    AddConceptRequest(
                        topic=args.topic,
                        title=args.title,
                        summary=args.summary,
                        tags=_tags(args),
                    )
                )
                print(json.dumps({"status": "noted", "okf_concept": str(result.path)}, ensure_ascii=False))
                return 0
            if args.knowledge_command == "add-question":
                result = knowledge.add_question(
                    AddQuestionRequest(
                        topic=args.topic,
                        question=args.question,
                        answer=args.answer,
                        tags=_tags(args),
                        source_refs=_refs(args),
                    )
                )
                print(json.dumps({"status": "added", "okf_question": str(result.path)}, ensure_ascii=False))
                return 0
            if args.knowledge_command == "add-entity":
                result = knowledge.add_entity(
                    AddEntityRequest(
                        topic=args.topic,
                        name=args.name,
                        kind=args.kind,
                        summary=args.summary,
                        use_cases=args.use_cases,
                        open_questions=args.open_questions,
                        tags=_tags(args),
                        source_refs=_refs(args),
                    )
                )
                print(json.dumps({"status": "added", "okf_entity": str(result.path)}, ensure_ascii=False))
                return 0
            if args.knowledge_command == "promote":
                result = knowledge.promote_source(args.source, topic=args.topic, summary=args.summary)
                print(json.dumps({"status": "promoted", "okf_concept": str(result.path)}, ensure_ascii=False))
                return 0
            if args.knowledge_command == "refresh":
                result = LifecycleModule(workspace).refresh_topic(
                    args.topic,
                    in_place=args.in_place,
                    summary=args.summary,
                )
                print(json.dumps(result, ensure_ascii=False, default=str))
                return 0
            if args.knowledge_command == "topics":
                classifier = ClassifyModule(workspace)
                print(
                    json.dumps(
                        {
                            "topics": classifier.list_topics(),
                            "tags": classifier.list_tags(),
                            "domains": classifier.taxonomy.get("domains", {}),
                        },
                        ensure_ascii=False,
                    )
                )
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
        if args.command == "validate":
            issues = ValidateModule(Workspace.discover(Path(args.workspace))).validate(
                strict_quality=args.strict_quality
            )
            if args.json:
                print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
            else:
                for issue in issues:
                    print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
            return 1 if issues else 0
        if args.command == "gardener":
            report = GardenerModule(Workspace.discover(Path(args.workspace))).gardener(
                prune=args.prune
            )
            payload = {"issues": report.issues, "actions": report.actions}
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                for issue in report.issues:
                    print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
                for action in report.actions:
                    print(f"{action['action']} | {action['path']}")
            return 0
        return _argument_error(parser, "the following arguments are required: command")
    except (AlcoveError, FileNotFoundError, ValueError) as exc:
        print(f"alcove: {exc}", file=sys.stderr)
        return 2


def entrypoint() -> None:
    raise SystemExit(main())
