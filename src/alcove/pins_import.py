from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from alcove.paths import compact_user_path
from alcove.pins import AddPinRequest, Pin, PinsModule, UpdatePinRequest


class PinsMarkdownImportModule:
    """Import user-maintained regular/todo markdown pin files into Alcove pins."""

    def __init__(self, home: Any) -> None:
        self.home = home

    def import_pins(
        self,
        regular_file: str | Path | None = None,
        todo_file: str | Path | None = None,
    ) -> dict[str, Any]:
        archived_previous_imports = self._archive_previous_import_pins()
        keep_ids: set[str] = set()
        result: dict[str, Any] = {"archived_previous_imports": archived_previous_imports}
        if regular_file:
            result["regular"] = self._import_markdown_pin_file(
                Path(regular_file).expanduser(), "regular"
            )
            keep_ids.update(pin["id"] for pin in result["regular"]["pins"])
        if todo_file:
            result["todo"] = self._import_markdown_pin_file(Path(todo_file).expanduser(), "todo")
            keep_ids.update(pin["id"] for pin in result["todo"]["pins"])
        result["archived_duplicates"] = self._archive_superseded_theme_pins(keep_ids)
        PinsModule(home=self.home).rebuild_index()
        return result

    def _archive_previous_import_pins(self) -> int:
        module = PinsModule(home=self.home)
        archived = 0
        for pin in module.list(status="active"):
            tags = set(pin.tags)
            if "theme-pin" not in tags and not (
                "imported" in tags and "source-markdown-pin" not in tags
            ):
                continue
            module.update(UpdatePinRequest(pin_id=pin.id, status="archived"))
            archived += 1
        return archived

    def _import_markdown_pin_file(self, path: Path, kind: str) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        archive = self._archive_import_source(path, kind, text)
        title = self._markdown_title(text, fallback="常用收藏" if kind == "regular" else "Todo")
        raw_lines = text.count("\n")
        summary = self._markdown_pin_summary(text, raw_lines)
        module = PinsModule(home=self.home)
        existing = self._find_source_markdown_pin(module, title=title, kind=kind)
        request_tags = ["imported", "source-markdown-pin"]
        if existing is None:
            pin = module.add(
                AddPinRequest(
                    title=title,
                    summary=summary,
                    content=text.strip() + "\n",
                    kind=kind,
                    tags=request_tags,
                    priority="high" if kind == "regular" else "medium",
                    resources=[],
                    content_format="markdown",
                )
            ).pin
        else:
            pin = module.update(
                UpdatePinRequest(
                    pin_id=existing.id,
                    summary=summary,
                    content=text.strip() + "\n",
                    kind=kind,
                    tags=request_tags,
                    priority=existing.priority,
                    resources=[],
                    content_format="markdown",
                )
            ).pin
        return {
            "source": compact_user_path(path),
            "archive": archive,
            "raw_lines": raw_lines,
            "imported": 1,
            "pins": [{"id": pin.id, "title": pin.title, "kind": pin.kind}],
        }

    def _archive_import_source(self, path: Path, kind: str, text: str) -> dict[str, Any]:
        imports_root = self.home.paths().pins / "imports"
        imports_root.mkdir(parents=True, exist_ok=True)
        archive_path = imports_root / f"{kind}.txt"
        manifest_path = imports_root / f"{kind}.json"
        archive_path.write_text(text, encoding="utf-8")
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        payload = {
            "kind": kind,
            "source": compact_user_path(path),
            "path": compact_user_path(archive_path),
            "sha256": digest,
            "bytes": archive_path.stat().st_size,
            "lines": text.count("\n"),
            "imported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return payload

    def _markdown_title(self, text: str, fallback: str) -> str:
        for line in text.splitlines():
            value = line.strip()
            if value.startswith("# "):
                return value[2:].strip() or fallback
        return fallback

    def _markdown_pin_summary(self, text: str, raw_lines: int) -> str:
        values: list[str] = []
        for line in text.splitlines():
            value = line.strip()
            if not value or value.startswith("# ") or value.startswith("|"):
                continue
            if value in {"---", "===", "—"}:
                continue
            value = value.lstrip("#").strip()
            value = value.removeprefix("- ").strip()
            if value:
                values.append(value)
            if len(values) >= 4:
                break
        if not values:
            return f"Markdown 原文 · {raw_lines} 行"
        head, *tail = values
        if not tail:
            return head[:180]
        return f"{head} · {'; '.join(tail)}"[:180]

    def _find_source_markdown_pin(
        self,
        module: PinsModule,
        *,
        title: str,
        kind: str,
    ) -> Pin | None:
        matches = [
            pin
            for pin in module.list(status="active")
            if pin.title == title and pin.kind == kind and "source-markdown-pin" in pin.tags
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda pin: pin.updated_at, reverse=True)[0]

    def _archive_superseded_theme_pins(self, keep_ids: set[str]) -> int:
        if not keep_ids:
            return 0
        module = PinsModule(home=self.home)
        keep_titles = {module.get(pin_id).title for pin_id in keep_ids}
        archived = 0
        for pin in module.list(status="active"):
            if pin.id in keep_ids:
                continue
            if pin.title not in keep_titles or "theme-pin" not in pin.tags:
                continue
            module.update(UpdatePinRequest(pin_id=pin.id, status="archived"))
            archived += 1
        return archived
