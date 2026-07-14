from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from alcove.application import AlcoveApplication
from alcove.search import SearchRequest


ArgumentError = Callable[[argparse.ArgumentParser, str], int]
RuntimeFactory = Callable[[Any], Any]
SearchPrinter = Callable[[list[dict[str, Any]]], None]


def handle_search_command(
    args: Any,
    parser: argparse.ArgumentParser,
    *,
    runtime_from_args: RuntimeFactory,
    print_search_rows: SearchPrinter,
    argument_error: ArgumentError,
) -> int:
    runtime = runtime_from_args(args)
    app = AlcoveApplication(runtime)
    if args.unindexed:
        if runtime.workspace is None:
            return argument_error(parser, "search --unindexed requires --workspace")
        issues = app.search.search_unindexed_payload()["issues"]
        if args.json:
            print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
        else:
            for issue in issues:
                print(f"{issue['kind']} | {issue['path']} | {issue['message']}")
        return 1 if issues else 0
    if args.tags:
        results = app.search.search_tags_payload()["tags"][: max(args.limit, 0)]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for row in results:
                print(f"{row['tag']} | {row['count']}")
        return 0
    if args.tag_doctor:
        results = app.search.search_tag_doctor_payload()["issues"][: max(args.limit, 0)]
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            for row in results:
                print(f"{row['canonical']} | {row['count']} | {', '.join(row['variants'])}")
        return 0
    if args.recent is not None:
        results = app.search.search_recent_payload(args.recent)["results"]
    else:
        results = app.search.search(
            SearchRequest(
                query=args.query,
                type_filter=args.type_filter,
                tag=args.tag,
                topic=args.topic,
                platform=args.platform,
                date_from=args.date_from,
                date_to=args.date_to,
                min_confidence=args.min_confidence,
                status=args.status,
                limit=args.limit,
            ),
            surface="cli",
        )
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_search_rows(results)
    return 0
