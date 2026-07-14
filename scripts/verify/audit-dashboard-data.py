#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import yaml

from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome


CAPTURE_ENTRY_MARKERS = frozenset({"capture.json", "post.md", "summary.md", "article.md"})


class Audit:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            self.failures.append(f"{name}: actual={actual!r} expected={expected!r}")

    def check_true(self, name: str, condition: bool, detail: str = "") -> None:
        if not condition:
            suffix = f" ({detail})" if detail else ""
            self.failures.append(f"{name}: failed{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Alcove dashboard counts against source data."
    )
    parser.add_argument("--home", default="~/.alcove")
    parser.add_argument("--snapshot", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    home = AlcoveHome.init(Path(args.home).expanduser())
    snapshot = _load_snapshot(args.snapshot, home)
    audit = Audit()
    _audit_snapshot_internal(snapshot, audit)
    _audit_source_data(snapshot, home.root, audit)

    payload = {
        "status": "passed" if not audit.failures else "failed",
        "failures": audit.failures,
        "summary": _summary(snapshot),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"dashboard data audit: {payload['status']}")
        for key, value in payload["summary"].items():
            print(f"- {key}: {value}")
        for failure in audit.failures:
            print(f"FAIL {failure}", file=sys.stderr)
    return 0 if not audit.failures else 1


def _load_snapshot(snapshot_path: str, home: AlcoveHome) -> dict[str, Any]:
    if snapshot_path:
        return json.loads(Path(snapshot_path).expanduser().read_text(encoding="utf-8"))
    return DashboardModule(home=home).snapshot()


def _audit_snapshot_internal(snapshot: dict[str, Any], audit: Audit) -> None:
    counts = snapshot["summary"]["counts"]
    modules = {module["id"]: module for module in snapshot["modules"]}
    pending = len(snapshot["tasks"]["pending"])
    ideas = len(snapshot["tasks"]["ideas"])
    routines = len(snapshot["tasks"]["routines"])
    managed_items = sum(row.get("item_count", 0) for row in snapshot["knowledge"]["managed"])
    mount_items = sum(row.get("item_count", row.get("count", 0)) for row in snapshot["mounts"])
    connector_items = sum(
        row.get("item_count", row.get("count", 0)) for row in snapshot["connectors"]
    )

    audit.check("counts.pins vs pins.all", counts.get("pins"), len(snapshot["pins"]["all"]))
    audit.check(
        "counts.pin_collections vs pins.themes",
        counts.get("pin_collections"),
        len(snapshot["pins"]["themes"]),
    )
    audit.check("module.pins.metric", modules["pins"]["metric"], counts.get("pin_collections"))
    audit.check("counts.pending_tasks", counts.get("pending_tasks"), pending)
    audit.check("counts.active_ideas", counts.get("active_ideas"), ideas)
    audit.check("counts.active_routines", counts.get("active_routines"), routines)
    audit.check("module.planner.metric", modules["planner"]["metric"], pending + ideas + routines)
    audit.check("counts.tasks_total", counts.get("tasks_total"), len(snapshot["tasks"]["all"]))
    audit.check(
        "counts.ideas_total", counts.get("ideas_total"), len(snapshot["tasks"]["ideas_all"])
    )
    audit.check(
        "counts.routines_total",
        counts.get("routines_total"),
        len(snapshot["tasks"]["routines_all"]),
    )
    audit.check("counts.prompts", counts.get("prompts"), _active_count(snapshot["prompts"]))
    audit.check(
        "module.library.metric",
        modules["library"]["metric"],
        counts.get("prompts") + counts.get("projects"),
    )
    audit.check("counts.knowledge_items", counts.get("knowledge_items"), managed_items)
    audit.check("counts.mount_items", counts.get("mount_items"), mount_items)
    audit.check("counts.connector_items", counts.get("connector_items"), connector_items)
    audit.check(
        "module.knowledge.metric",
        modules["knowledge"]["metric"],
        managed_items + mount_items + connector_items,
    )
    audit.check(
        "counts.knowledge_bases", counts.get("knowledge_bases"), len(snapshot["knowledge_bases"])
    )
    audit.check("counts.mounts", counts.get("mounts"), len(snapshot["mounts"]))
    audit.check("counts.connectors", counts.get("connectors"), len(snapshot["connectors"]))
    audit.check("counts.activity_events", counts.get("activity_events"), len(snapshot["activity"]))
    audit.check("module.activity.metric", modules["activity"]["metric"], len(snapshot["activity"]))
    audit.check("counts.radars", counts.get("radars"), len(snapshot["radars"]))
    audit.check("module.radars.metric", modules["radars"]["metric"], len(snapshot["radars"]))
    audit.check(
        "counts.usage_events", counts.get("usage_events"), snapshot["usage"]["total_events"]
    )
    audit.check(
        "module.usage.metric", modules["usage"]["metric"], snapshot["usage"]["total_events"]
    )
    audit.check(
        "health.managed_items",
        snapshot["health"]["totals"].get("managed_items"),
        counts.get("knowledge_items"),
    )
    audit.check(
        "health.mount_items",
        snapshot["health"]["totals"].get("mount_items"),
        counts.get("mount_items"),
    )
    audit.check(
        "health.connector_items",
        snapshot["health"]["totals"].get("connector_items"),
        counts.get("connector_items"),
    )


def _audit_source_data(snapshot: dict[str, Any], home: Path, audit: Audit) -> None:
    counts = snapshot["summary"]["counts"]
    pins_index = _json(home / "pins" / "index.json", default={"pins": []})
    active_pins = [pin for pin in pins_index.get("pins", []) if pin.get("status") == "active"]
    audit.check("source pins.active", counts.get("pins"), len(active_pins))

    tasks = _json(home / "tasks" / "tasks.json", default={"tasks": [], "ideas": [], "routines": []})
    audit.check(
        "source tasks.pending",
        len(snapshot["tasks"]["pending"]),
        _status_count(tasks["tasks"], "pending"),
    )
    audit.check(
        "source ideas.active",
        len(snapshot["tasks"]["ideas"]),
        _status_count(tasks["ideas"], "active"),
    )
    audit.check(
        "source routines.active",
        len(snapshot["tasks"]["routines"]),
        _status_count(tasks["routines"], "active"),
    )
    audit.check("source tasks.all", len(snapshot["tasks"]["all"]), len(tasks["tasks"]))
    audit.check("source ideas.all", len(snapshot["tasks"]["ideas_all"]), len(tasks["ideas"]))
    audit.check(
        "source routines.all", len(snapshot["tasks"]["routines_all"]), len(tasks["routines"])
    )

    prompts = _json(home / "prompts" / "index.json", default={"prompts": []})
    audit.check(
        "source prompts.active", counts.get("prompts"), _status_count(prompts["prompts"], "active")
    )
    projects = _json(home / "projects" / "projects.json", default={"projects": []})
    audit.check("source projects", counts.get("projects"), len(projects["projects"]))

    mounts = _json(home / "mounts" / "mounts.json", default={"mounts": []})
    audit.check(
        "source mounts.active", counts.get("mounts"), _status_count(mounts["mounts"], "active")
    )
    for mount in snapshot["mounts"]:
        index = _json(home / "mounts" / "indexes" / f"{mount['id']}.json", default={"items": []})
        audit.check(
            f"source mount.{mount['id']}.items", mount.get("item_count"), len(index["items"])
        )
        audit.check_true(
            f"source mount.{mount['id']}.preview",
            len(mount.get("items", [])) <= int(mount.get("item_count") or 0),
        )

    for connector in snapshot["connectors"]:
        connector_name = connector["connector"]
        index = _json(home / "connectors" / connector_name / "index.json", default={"items": []})
        audit.check(
            f"source connector.{connector_name}.items",
            connector.get("item_count"),
            len(index["items"]),
        )
        audit.check_true(
            f"source connector.{connector_name}.preview",
            len(connector.get("items", [])) <= int(connector.get("item_count") or 0),
        )

    kb_registry = {row["name"]: row for row in snapshot["knowledge_bases"]}
    for path in sorted((home / "knowledge-bases").glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        name = str(data.get("name") or path.stem)
        root = Path(str(data.get("path") or "")).expanduser()
        if name not in kb_registry:
            audit.failures.append(f"source kb.{name}: registered but missing from snapshot")
            continue
        row = kb_registry[name]
        audit.check(
            f"source kb.{name}.inbox_entries", row.get("inbox_count"), _entry_count(root / "inbox")
        )
        audit.check(
            f"source kb.{name}.archive_entries",
            row.get("archive_count"),
            _entry_count(root / "archive"),
        )
        raw_markdown = (
            len(list((root / "knowledge").rglob("*.md"))) if (root / "knowledge").is_dir() else 0
        )
        audit.check_true(
            f"source kb.{name}.managed_items_within_raw_markdown",
            0 <= int(row.get("item_count") or 0) <= raw_markdown,
            f"item_count={row.get('item_count')} raw_markdown={raw_markdown}",
        )


def _summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    counts = snapshot["summary"]["counts"]
    return {
        "pins": counts.get("pins"),
        "planner": (
            f"{counts.get('pending_tasks')} pending / {counts.get('active_ideas')} ideas / "
            f"{counts.get('active_routines')} routines"
        ),
        "knowledge": (
            f"{counts.get('knowledge_items')} managed / {counts.get('mount_items')} mounted / "
            f"{counts.get('connector_items')} connector"
        ),
        "radars": counts.get("radars"),
        "usage_events": counts.get("usage_events"),
    }


def _json(path: Path, *, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _status_count(items: list[dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if item.get("status") == status)


def _active_count(items: list[dict[str, Any]]) -> int:
    return _status_count(items, "active")


def _entry_count(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(
        1
        for path in root.rglob("*")
        if path.is_dir() and any((path / marker).is_file() for marker in CAPTURE_ENTRY_MARKERS)
    )


if __name__ == "__main__":
    raise SystemExit(main())
