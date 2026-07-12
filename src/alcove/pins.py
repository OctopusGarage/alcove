from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape
import json
from pathlib import Path
from typing import Any, List

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository, normalize_slug
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


PIN_SCHEMA = "okf/pin/v1"
PIN_INDEX_SCHEMA = "alcove/pins-index/v1"
PIN_REQUIRED_FIELDS = (
    "type",
    "schema",
    "title",
    "description",
    "summary",
    "kind",
    "content_format",
    "tags",
    "status",
    "priority",
    "source_refs",
    "resources",
    "created_at",
    "updated_at",
)
PIN_KINDS = {"regular", "todo"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AddPinRequest:
    title: str
    description: str = ""
    summary: str = ""
    content: str = ""
    kind: str = "regular"
    tags: list[str] = field(default_factory=list)
    priority: str = "medium"
    source_refs: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    content_format: str = "text"


@dataclass(frozen=True)
class UpdatePinRequest:
    pin_id: str
    title: str | None = None
    description: str | None = None
    summary: str | None = None
    content: str | None = None
    kind: str | None = None
    tags: list[str] | None = None
    priority: str | None = None
    source_refs: list[str] | None = None
    resources: list[str] | None = None
    status: str | None = None
    content_format: str | None = None


@dataclass(frozen=True)
class Pin:
    id: str
    title: str
    description: str
    summary: str
    content: str
    kind: str
    tags: list[str]
    status: str
    priority: str
    source_refs: list[str]
    resources: list[str]
    content_format: str
    path: Path
    created_at: str = ""
    updated_at: str = ""
    last_used_at: str = ""


@dataclass(frozen=True)
class PinResult:
    path: Path
    pin: Pin
    index_path: Path


class PinsModule:
    def __init__(
        self,
        workspace: Workspace | None = None,
        repo: MarkdownRepository | None = None,
        home: AlcoveHome | None = None,
    ) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.pin_root = self.runtime.pins_root
        self.index_path = self.pin_root / "index.json"
        self.index_md_path = self.pin_root / "index.md"
        self.board_path = self.pin_root / "board.html"
        self.repo = repo or MarkdownRepository()
        self.taxonomy = load_taxonomy(self.runtime.taxonomy_root)

    def add(self, request: AddPinRequest) -> PinResult:
        path = self.repo.unique_path(self.pin_root, request.title)
        timestamp = now_iso()
        summary = request.summary or request.description
        content = self._normalize_content(
            request.content or request.description or summary,
            content_format=request.content_format,
        )
        doc = MarkdownDoc(
            frontmatter={
                "type": "Pin",
                "schema": PIN_SCHEMA,
                "title": request.title,
                "description": summary,
                "summary": summary,
                "kind": self._kind(request.kind),
                "content_format": self._content_format(request.content_format),
                "tags": self._normalize_tags(request.tags),
                "status": "active",
                "priority": self._priority(request.priority),
                "source_refs": self._normalize_refs(request.source_refs),
                "resources": self._normalize_list(request.resources),
                "created_at": timestamp,
                "updated_at": timestamp,
                "last_used_at": "",
            },
            body=self._body(request.title, summary, content),
        )
        self.repo.write_doc(path, doc)
        pin = self._pin_from_doc(self.repo.read_doc(path))
        index_path = self.rebuild_index()
        return PinResult(path=path, pin=pin, index_path=index_path)

    def get(self, pin_id: str) -> Pin:
        return self._pin_from_doc(self._read_pin(pin_id))

    def update(self, request: UpdatePinRequest) -> PinResult:
        doc = self._read_pin(request.pin_id)
        old = self._pin_from_doc(doc)
        path = self._doc_path(doc)
        timestamp = now_iso()
        title = request.title if request.title is not None else old.title
        summary = self._choose_updated_summary(request, old)
        content = (
            self._normalize_content(
                request.content, content_format=request.content_format or old.content_format
            )
            if request.content is not None
            else old.content
        )
        frontmatter = {
            **doc.frontmatter,
            "type": "Pin",
            "schema": PIN_SCHEMA,
            "title": title,
            "description": summary,
            "summary": summary,
            "kind": self._kind(request.kind if request.kind is not None else old.kind),
            "content_format": self._content_format(
                request.content_format if request.content_format is not None else old.content_format
            ),
            "tags": (self._normalize_tags(request.tags) if request.tags is not None else old.tags),
            "status": request.status if request.status is not None else old.status,
            "priority": (
                self._priority(request.priority) if request.priority is not None else old.priority
            ),
            "source_refs": (
                self._normalize_refs(request.source_refs)
                if request.source_refs is not None
                else old.source_refs
            ),
            "resources": (
                self._normalize_list(request.resources)
                if request.resources is not None
                else old.resources
            ),
            "created_at": old.created_at or timestamp,
            "updated_at": timestamp,
            "last_used_at": old.last_used_at,
        }
        self.repo.write_doc(path, MarkdownDoc(frontmatter, self._body(title, summary, content)))
        pin = self._pin_from_doc(self.repo.read_doc(path))
        index_path = self.rebuild_index()
        return PinResult(path=path, pin=pin, index_path=index_path)

    def list(self, tag: str | None = None, status: str = "active") -> List[Pin]:
        tag_filter = normalize_tag(tag, self.taxonomy) if tag else None
        pins: list[Pin] = []
        for doc in self.repo.list_docs(self.pin_root, type_filter="Pin"):
            pin = self._pin_from_doc(doc)
            if status and pin.status != status:
                continue
            if tag_filter and tag_filter not in pin.tags:
                continue
            pins.append(pin)
        return self._sort_pins(pins)

    def search(
        self,
        query: str = "",
        kind: str = "",
        tag: str = "",
        status: str = "active",
    ) -> List[Pin]:
        q = str(query or "").casefold()
        kind_filter = self._kind(kind) if kind else ""
        tag_filter = normalize_tag(tag, self.taxonomy) if tag else ""
        pins: list[Pin] = []
        for pin in self.list(status=status):
            if kind_filter and pin.kind != kind_filter:
                continue
            if tag_filter and tag_filter not in pin.tags:
                continue
            if q and q not in self._search_text(pin).casefold():
                continue
            pins.append(pin)
        return pins

    def rebuild_index(self) -> Path:
        pins = self.list(status="")
        payload = {
            "schema_version": 1,
            "schema": PIN_INDEX_SCHEMA,
            "generated_at": now_iso(),
            "count": len(pins),
            "pins": [self._index_item(pin) for pin in pins],
        }
        self.pin_root.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.repo.write_doc(
            self.index_md_path,
            MarkdownDoc(
                frontmatter={
                    "type": "Pins Index",
                    "schema": PIN_INDEX_SCHEMA,
                    "generated_at": payload["generated_at"],
                    "count": len(pins),
                },
                body=self._index_markdown(pins),
            ),
        )
        return self.index_path

    def render_html(self, output_path: str | Path | None = None) -> Path:
        pins = self.list(status="active")
        target = Path(output_path).expanduser() if output_path else self.board_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self._html(pins), encoding="utf-8")
        return target

    def archive(self, pin_id: str, confirm: bool = False) -> dict[str, Any]:
        doc = self._read_pin(pin_id)
        path = self._doc_path(doc)
        if not confirm:
            return {
                "status": "preview",
                "path": str(path),
                "confirm_required": True,
            }
        frontmatter = {
            **doc.frontmatter,
            "status": "archived",
            "updated_at": now_iso(),
        }
        self.repo.write_doc(path, MarkdownDoc(frontmatter, doc.body))
        index_path = self.rebuild_index()
        return {"status": "archived", "path": str(path), "index_path": str(index_path)}

    def _read_pin(self, pin_id: str) -> MarkdownDoc:
        slug = normalize_slug(pin_id)
        path = self.pin_root / f"{slug}.md"
        if path.is_file():
            return self.repo.read_doc(path)
        matches = sorted(self.pin_root.glob(f"{slug}-*.md"))
        if matches:
            return self.repo.read_doc(matches[0])
        raise FileNotFoundError(f"Pin not found: {pin_id}")

    def _pin_from_doc(self, doc: MarkdownDoc) -> Pin:
        path = self._doc_path(doc)
        frontmatter = doc.frontmatter
        summary = str(
            frontmatter.get("summary")
            or frontmatter.get("description")
            or self._section_from_body(doc.body, "Summary")
            or ""
        )
        content = self._content_from_body(
            doc.body,
            preserve_trailing=self._content_format(str(frontmatter.get("content_format") or "text"))
            == "markdown",
        )
        if not content:
            content = str(frontmatter.get("content") or frontmatter.get("description") or summary)
        return Pin(
            id=path.stem,
            title=str(frontmatter.get("title") or path.stem),
            description=summary,
            summary=summary,
            content=content,
            kind=self._kind(str(frontmatter.get("kind") or "regular")),
            tags=self._as_list(frontmatter.get("tags")),
            status=str(frontmatter.get("status") or "active"),
            priority=self._priority(str(frontmatter.get("priority") or "medium")),
            source_refs=self._as_list(frontmatter.get("source_refs")),
            resources=self._as_list(frontmatter.get("resources")),
            content_format=self._content_format(str(frontmatter.get("content_format") or "text")),
            path=path,
            created_at=str(frontmatter.get("created_at") or ""),
            updated_at=str(frontmatter.get("updated_at") or ""),
            last_used_at=str(frontmatter.get("last_used_at") or ""),
        )

    def _index_item(self, pin: Pin) -> dict[str, Any]:
        return {
            "id": pin.id,
            "type": "Pin",
            "schema": PIN_SCHEMA,
            "title": pin.title,
            "description": pin.description,
            "summary": pin.summary,
            "content": pin.content,
            "kind": pin.kind,
            "content_format": pin.content_format,
            "tags": pin.tags,
            "status": pin.status,
            "priority": pin.priority,
            "source_refs": pin.source_refs,
            "resources": pin.resources,
            "created_at": pin.created_at,
            "updated_at": pin.updated_at,
            "last_used_at": pin.last_used_at,
            "path": f"pins/{pin.path.name}",
            "search_text": self._search_text(pin),
        }

    def _index_markdown(self, pins: List[Pin]) -> str:
        lines = ["# Pins Index", "", "## Regular", ""]
        for pin in [item for item in pins if item.kind == "regular"]:
            lines.append(self._index_line(pin))
        lines.extend(["", "## Todo", ""])
        for pin in [item for item in pins if item.kind == "todo"]:
            lines.append(self._index_line(pin))
        return "\n".join(lines).rstrip() + "\n"

    def _index_line(self, pin: Pin) -> str:
        tags = f" tags: {', '.join(pin.tags)}" if pin.tags else ""
        return f"- [{pin.title}]({pin.path.name}) - {pin.priority}; {pin.summary}{tags}"

    def _search_text(self, pin: Pin) -> str:
        return "\n".join(
            part
            for part in [
                pin.id,
                pin.title,
                pin.description,
                pin.summary,
                pin.content,
                pin.kind,
                " ".join(pin.tags),
                " ".join(pin.source_refs),
                " ".join(pin.resources),
            ]
            if part
        )

    def _body(self, title: str, summary: str, content: str) -> str:
        parts = [f"# {title}"]
        if summary:
            parts.extend(["", "## Summary", "", summary])
        if content:
            parts.extend(["", "## Content", "", content])
        return "\n".join(parts).rstrip() + "\n"

    def _normalize_content(self, content: str, *, content_format: str) -> str:
        value = str(content or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in value.split("\n")]
        normalized: list[str] = []
        blank_count = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                blank_count += 1
                if blank_count <= 1:
                    normalized.append("")
                continue
            blank_count = 0
            if self._content_format(content_format) == "markdown" and stripped in {"===", "—"}:
                normalized.append("---")
                continue
            normalized.append(line)
        return "\n".join(normalized).strip()

    def _section_from_body(self, body: str, heading: str) -> str:
        marker = f"## {heading}"
        if marker not in body:
            return ""
        section = body.split(marker, 1)[1]
        if "\n## " in section:
            section = section.split("\n## ", 1)[0]
        return section.strip()

    def _content_from_body(self, body: str, *, preserve_trailing: bool = False) -> str:
        content = self._content_section_from_body(body, preserve_trailing=preserve_trailing)
        if content:
            return content
        lines = body.splitlines()
        while lines and lines[0].startswith("#"):
            lines.pop(0)
        return "\n".join(lines).strip()

    def _content_section_from_body(self, body: str, *, preserve_trailing: bool) -> str:
        marker = "## Content"
        if marker not in body:
            return ""
        content = body.split(marker, 1)[1].lstrip("\n")
        return content if preserve_trailing else content.strip()

    def _choose_updated_summary(self, request: UpdatePinRequest, old: Pin) -> str:
        if request.summary is not None:
            return request.summary
        if request.description is not None:
            return request.description
        return old.summary

    def _doc_path(self, doc: MarkdownDoc) -> Path:
        if doc.path is None:
            raise ValueError("Pin document has no path")
        return doc.path

    def _normalize_tags(self, tags: List[str]) -> List[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _normalize_refs(self, refs: List[str]) -> List[str]:
        values: list[str] = []
        for ref in refs:
            value = str(ref or "").strip()
            if value and not value.startswith("/"):
                value = f"/{value}"
            if value and value not in values:
                values.append(value)
        return values

    def _normalize_list(self, values: List[str]) -> List[str]:
        out: list[str] = []
        for value in values:
            item = str(value or "").strip()
            if item and item not in out:
                out.append(item)
        return out

    def _priority(self, value: str) -> str:
        priority = normalize_slug(value)
        return priority if priority in PRIORITY_ORDER else "medium"

    def _kind(self, value: str) -> str:
        kind = normalize_slug(value)
        return kind if kind in PIN_KINDS else "regular"

    def _content_format(self, value: str) -> str:
        content_format = normalize_slug(value)
        return content_format if content_format in {"text", "markdown"} else "text"

    def _sort_pins(self, pins: List[Pin]) -> List[Pin]:
        return sorted(
            pins,
            key=lambda pin: (
                PRIORITY_ORDER.get(pin.priority, 1),
                pin.kind != "regular",
                str(pin.updated_at or pin.created_at),
                pin.title.casefold(),
            ),
        )

    def _as_list(self, value: object) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if value:
            return [str(value)]
        return []

    def _html(self, pins: List[Pin]) -> str:
        generated = now_iso()
        regular = [pin for pin in pins if pin.kind == "regular"]
        todo = [pin for pin in pins if pin.kind == "todo"]
        tags = sorted({tag for pin in pins for tag in pin.tags})
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pins Board</title>
  <style>
    :root {{
      --paper: #f7f6f0;
      --surface: #ffffff;
      --ink: #1f2528;
      --muted: #66706d;
      --line: #d8ded8;
      --green: #23685a;
      --blue: #315f87;
      --amber: #a86528;
      --soft-green: #e8f0eb;
      --soft-blue: #e7eef5;
      --soft-amber: #f4ecdf;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 16px/1.62 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }}
    .page {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 44px 0 56px;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 32px;
      align-items: end;
      padding-bottom: 30px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0;
      font-size: clamp(36px, 7vw, 76px);
      line-height: 0.95;
      font-weight: 760;
    }}
    .lede {{
      max-width: 680px;
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 18px;
    }}
    .meta {{
      display: grid;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
    }}
    .statline {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 26px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 3px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.64);
      color: var(--muted);
      font-size: 13px;
      white-space: nowrap;
    }}
    .map {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .lanes {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 22px;
      margin-top: 30px;
    }}
    section {{
      min-width: 0;
    }}
    .lane-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin: 0 0 14px;
    }}
    h2 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
    }}
    .count {{
      color: var(--muted);
      font-size: 14px;
    }}
    article {{
      border: 1px solid var(--line);
      border-left-width: 5px;
      border-radius: 8px;
      background: var(--surface);
      padding: 18px 18px 16px;
      margin-bottom: 14px;
      box-shadow: 0 1px 0 rgba(31, 37, 40, 0.04);
    }}
    .regular article {{ border-left-color: var(--green); }}
    .todo article {{ border-left-color: var(--blue); }}
    .pin-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
    }}
    h3 {{
      margin: 0;
      font-size: 18px;
      line-height: 1.3;
    }}
    .priority {{
      flex: 0 0 auto;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--soft-amber);
      color: var(--amber);
      font-size: 12px;
      font-weight: 650;
      text-transform: uppercase;
    }}
    .summary {{
      margin: 8px 0 0;
      color: var(--ink);
    }}
    .content {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 14px;
    }}
    .tags {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 13px;
    }}
    .tag {{
      padding: 2px 7px;
      border-radius: 6px;
      background: var(--soft-green);
      color: var(--green);
      font-size: 12px;
    }}
    .todo .tag {{
      background: var(--soft-blue);
      color: var(--blue);
    }}
    .refs {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      word-break: break-word;
    }}
    .empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 22px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.48);
    }}
    footer {{
      margin-top: 34px;
      padding-top: 18px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 820px) {{
      .page {{ width: min(100% - 22px, 720px); padding-top: 26px; }}
      header {{ grid-template-columns: 1fr; gap: 18px; }}
      .lanes {{ grid-template-columns: 1fr; }}
      .pin-top {{ align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <header>
      <div>
        <h1>Pins Board</h1>
        <p class="lede">把需要反复查阅的稳定信息和未来值得实践的想法分开置顶；源数据仍是 OKF Pin Markdown，页面只是可重建的展示层。</p>
        <div class="statline">
          <span class="chip">{len(regular)} 常规</span>
          <span class="chip">{len(todo)} 待实践</span>
          <span class="chip">{len(tags)} 标签</span>
        </div>
      </div>
      <div class="meta">
        {self._board_svg(len(regular), len(todo))}
        <span>Generated {escape(generated)}</span>
      </div>
    </header>
    <div class="lanes">
      {self._html_lane("常规置顶", "适合需要时反复查阅和引用。", regular, "regular")}
      {self._html_lane("待实践 / 深入", "以后找机会实践、细化或进一步理解。", todo, "todo")}
    </div>
    <footer>Source: Markdown pins in {escape(compact_user_path(self.pin_root))}. Derived: index.json, index.md, board.html.</footer>
  </main>
</body>
</html>
"""

    def _html_lane(self, title: str, subtitle: str, pins: List[Pin], css_class: str) -> str:
        articles = "\n".join(self._html_pin(pin) for pin in pins)
        if not articles:
            articles = '<div class="empty">暂无内容。</div>'
        return f"""<section class="{css_class}">
        <div class="lane-head">
          <div>
            <h2>{escape(title)}</h2>
            <div class="count">{escape(subtitle)}</div>
          </div>
          <span class="count">{len(pins)}</span>
        </div>
        {articles}
      </section>"""

    def _html_pin(self, pin: Pin) -> str:
        tags = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in pin.tags)
        refs = [*pin.resources, *pin.source_refs]
        refs_html = ""
        if refs:
            refs_html = (
                '<div class="refs">' + "<br>".join(escape(ref) for ref in refs[:4]) + "</div>"
            )
        content = pin.content
        if len(content) > 280:
            content = content[:277].rstrip() + "..."
        return f"""<article>
          <div class="pin-top">
            <h3>{escape(pin.title)}</h3>
            <span class="priority">{escape(pin.priority)}</span>
          </div>
          <p class="summary">{escape(pin.summary)}</p>
          <p class="content">{escape(content)}</p>
          <div class="tags">{tags}</div>
          {refs_html}
        </article>"""

    def _board_svg(self, regular_count: int, todo_count: int) -> str:
        total = max(regular_count + todo_count, 1)
        regular_width = int(220 * regular_count / total)
        todo_x = 28 + regular_width
        todo_width = max(0, 220 - regular_width)
        return f"""<svg class="map" viewBox="0 0 280 96" role="img" aria-label="pin board balance">
          <rect x="1" y="1" width="278" height="94" rx="8" fill="#fff" stroke="#d8ded8"/>
          <line x1="28" y1="48" x2="252" y2="48" stroke="#d8ded8" stroke-width="2"/>
          <rect x="28" y="40" width="{regular_width}" height="16" rx="4" fill="#23685a"/>
          <rect x="{todo_x}" y="40" width="{todo_width}" height="16" rx="4" fill="#315f87"/>
          <circle cx="28" cy="48" r="6" fill="#23685a"/>
          <circle cx="252" cy="48" r="6" fill="#315f87"/>
          <text x="28" y="24" fill="#66706d" font-size="12">regular {regular_count}</text>
          <text x="184" y="76" fill="#66706d" font-size="12">todo {todo_count}</text>
        </svg>"""
