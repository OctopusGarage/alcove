from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository, normalize_slug
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


PROMPT_SCHEMA = "okf/prompt/v1"
PROMPT_INDEX_SCHEMA = "alcove/prompts-index/v1"
PROMPT_REQUIRED_FIELDS = (
    "type",
    "schema",
    "title",
    "description",
    "tags",
    "status",
    "use_cases",
    "source_refs",
    "created_at",
    "updated_at",
)
PROMPT_DEFAULT_KIND = "full_prompt"
PROMPT_ALLOWED_KINDS = {
    "full_prompt",
    "fragment",
    "modifier",
    "playbook",
    "style_profile",
    "eval_prompt",
    "source_note",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AddPromptRequest:
    title: str
    content: str
    description: str = ""
    tags: builtins.list[str] = field(default_factory=list)
    use_cases: builtins.list[str] = field(default_factory=list)
    source_refs: builtins.list[str] = field(default_factory=list)
    kind: str = PROMPT_DEFAULT_KIND
    domain: str = ""
    intent: str = ""
    surfaces: builtins.list[str] = field(default_factory=list)
    triggers: builtins.list[str] = field(default_factory=list)
    inputs: builtins.list[str] = field(default_factory=list)
    outputs: builtins.list[str] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Prompt:
    id: str
    title: str
    content: str
    description: str
    tags: builtins.list[str]
    use_cases: builtins.list[str]
    source_refs: builtins.list[str]
    status: str
    path: Path
    created_at: str = ""
    updated_at: str = ""
    kind: str = PROMPT_DEFAULT_KIND
    domain: str = ""
    intent: str = ""
    surfaces: builtins.list[str] = field(default_factory=list)
    triggers: builtins.list[str] = field(default_factory=list)
    inputs: builtins.list[str] = field(default_factory=list)
    outputs: builtins.list[str] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptResult:
    path: Path
    prompt: Prompt
    index_path: Path


class PromptsModule:
    def __init__(
        self,
        workspace: Workspace | None = None,
        repo: MarkdownRepository | None = None,
        home: AlcoveHome | None = None,
    ) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.root = self.runtime.prompts_root
        self.index_path = self.root / "index.json"
        self.repo = repo or MarkdownRepository()
        self.taxonomy = load_taxonomy(self.runtime.taxonomy_root)

    def save(self, request: AddPromptRequest) -> PromptResult:
        path = self._path_for_title(request.title)
        existing = self.repo.read_doc(path) if path.is_file() else None
        timestamp = now_iso()
        created = (
            str(existing.frontmatter.get("created_at") or timestamp)
            if existing is not None
            else timestamp
        )
        doc = MarkdownDoc(
            frontmatter={
                "type": "Prompt",
                "schema": PROMPT_SCHEMA,
                "title": request.title,
                "description": request.description,
                "tags": self._normalize_tags(request.tags),
                "status": "active",
                "use_cases": self._prompt_use_cases(request),
                "source_refs": self._normalize_refs(request.source_refs),
                "kind": self._normalize_kind(request.kind),
                "domain": normalize_tag(request.domain, self.taxonomy) if request.domain else "",
                "intent": normalize_tag(request.intent, self.taxonomy) if request.intent else "",
                "surfaces": self._normalize_tags(request.surfaces),
                "triggers": self._normalize_list(request.triggers),
                "inputs": self._normalize_list(request.inputs),
                "outputs": self._normalize_list(request.outputs),
                "quality": self._normalize_quality(request.quality),
                "created_at": created,
                "updated_at": timestamp,
            },
            body=self._body(request.title, request.description, request.content),
        )
        self.repo.write_doc(path, doc)
        prompt = self._prompt_from_doc(self.repo.read_doc(path))
        self.rebuild_index()
        return PromptResult(path=path, prompt=prompt, index_path=self.index_path)

    def get(self, prompt_id: str) -> Prompt:
        return self._prompt_from_doc(self._read_prompt(prompt_id))

    def search(
        self,
        query: str = "",
        tag: str = "",
        status: str = "active",
        kind: str = "",
        domain: str = "",
        surface: str = "",
    ) -> builtins.list[Prompt]:
        q = str(query or "").casefold()
        tag_filter = normalize_tag(tag, self.taxonomy) if tag else ""
        kind_filter = self._normalize_kind(kind) if kind else ""
        domain_filter = normalize_tag(domain, self.taxonomy) if domain else ""
        surface_filter = normalize_tag(surface, self.taxonomy) if surface else ""
        prompts: builtins.list[Prompt] = []
        for prompt in self.list(status=status):
            if tag_filter and tag_filter not in prompt.tags:
                continue
            if kind_filter and prompt.kind != kind_filter:
                continue
            if domain_filter and prompt.domain != domain_filter:
                continue
            if surface_filter and surface_filter not in prompt.surfaces:
                continue
            text = self._search_text(prompt).casefold()
            if q and q not in text:
                continue
            prompts.append(prompt)
        return prompts

    def list(self, status: str = "active") -> builtins.list[Prompt]:
        if self._index_current():
            prompts = [self._prompt_from_index(item) for item in self._read_index_items()]
            return [prompt for prompt in prompts if not status or prompt.status == status]
        self.rebuild_index()
        prompts = [self._prompt_from_index(item) for item in self._read_index_items()]
        return [prompt for prompt in prompts if not status or prompt.status == status]

    def rebuild_index(self) -> Path:
        prompts: builtins.list[Prompt] = []
        for doc in self.repo.list_docs(self.root, type_filter="Prompt"):
            prompt = self._prompt_from_doc(doc)
            prompts.append(prompt)
        payload = {
            "schema_version": 1,
            "schema": PROMPT_INDEX_SCHEMA,
            "generated_at": now_iso(),
            "count": len(prompts),
            "prompts": [self._index_item(prompt) for prompt in prompts],
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return self.index_path

    def tags(self) -> builtins.list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for prompt in self.list(status=""):
            for tag in prompt.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def archive(self, prompt_id: str, confirm: bool = False) -> dict[str, Any]:
        doc = self._read_prompt(prompt_id)
        path = self._doc_path(doc)
        if not confirm:
            return {
                "status": "preview",
                "path": compact_user_path(path),
                "confirm_required": True,
            }
        frontmatter = {**doc.frontmatter, "status": "archived", "updated_at": now_iso()}
        self.repo.write_doc(path, MarkdownDoc(frontmatter, doc.body))
        index_path = self.rebuild_index()
        return {
            "status": "archived",
            "path": compact_user_path(path),
            "index_path": compact_user_path(index_path),
        }

    def _read_prompt(self, prompt_id: str) -> MarkdownDoc:
        slug = normalize_slug(prompt_id)
        path = self.root / f"{slug}.md"
        if path.is_file():
            return self.repo.read_doc(path)
        matches = sorted(self.root.glob(f"{slug}-*.md"))
        if matches:
            return self.repo.read_doc(matches[0])
        raise FileNotFoundError(f"Prompt not found: {prompt_id}")

    def _path_for_title(self, title: str) -> Path:
        path = self.root / f"{normalize_slug(title)}.md"
        return path if path.is_file() else self.repo.unique_path(self.root, title)

    def _prompt_from_doc(self, doc: MarkdownDoc) -> Prompt:
        path = self._doc_path(doc)
        frontmatter = doc.frontmatter
        self._require_prompt_frontmatter(frontmatter, path)
        return Prompt(
            id=path.stem,
            title=str(frontmatter.get("title") or path.stem),
            content=self._content_from_body(doc.body),
            description=str(frontmatter.get("description") or ""),
            tags=self._as_list(frontmatter.get("tags")),
            use_cases=self._as_list(frontmatter.get("use_cases")),
            source_refs=self._as_list(frontmatter.get("source_refs")),
            status=str(frontmatter.get("status") or "active"),
            path=path,
            created_at=str(frontmatter.get("created_at") or ""),
            updated_at=str(frontmatter.get("updated_at") or ""),
            kind=self._normalize_kind(str(frontmatter.get("kind") or PROMPT_DEFAULT_KIND)),
            domain=str(frontmatter.get("domain") or ""),
            intent=str(frontmatter.get("intent") or ""),
            surfaces=self._as_list(frontmatter.get("surfaces")),
            triggers=self._as_list(frontmatter.get("triggers")),
            inputs=self._as_list(frontmatter.get("inputs")),
            outputs=self._as_list(frontmatter.get("outputs")),
            quality=self._as_dict(frontmatter.get("quality")),
        )

    def _prompt_from_index(self, item: dict[str, Any]) -> Prompt:
        path_value = str(item.get("path") or "")
        path = self.root / Path(path_value).name if path_value else self.root / "missing.md"
        return Prompt(
            id=str(item.get("id") or path.stem),
            title=str(item.get("title") or path.stem),
            content=str(item.get("content") or ""),
            description=str(item.get("description") or ""),
            tags=self._as_list(item.get("tags")),
            use_cases=self._as_list(item.get("use_cases")),
            source_refs=self._as_list(item.get("source_refs")),
            status=str(item.get("status") or "active"),
            path=path,
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
            kind=self._normalize_kind(str(item.get("kind") or PROMPT_DEFAULT_KIND)),
            domain=str(item.get("domain") or ""),
            intent=str(item.get("intent") or ""),
            surfaces=self._as_list(item.get("surfaces")),
            triggers=self._as_list(item.get("triggers")),
            inputs=self._as_list(item.get("inputs")),
            outputs=self._as_list(item.get("outputs")),
            quality=self._as_dict(item.get("quality")),
        )

    def _index_item(self, prompt: Prompt) -> dict[str, Any]:
        return {
            "id": prompt.id,
            "type": "Prompt",
            "schema": PROMPT_SCHEMA,
            "title": prompt.title,
            "description": prompt.description,
            "tags": prompt.tags,
            "status": prompt.status,
            "kind": prompt.kind,
            "domain": prompt.domain,
            "intent": prompt.intent,
            "surfaces": prompt.surfaces,
            "triggers": prompt.triggers,
            "inputs": prompt.inputs,
            "outputs": prompt.outputs,
            "quality": prompt.quality,
            "use_cases": prompt.use_cases,
            "source_refs": prompt.source_refs,
            "created_at": prompt.created_at,
            "updated_at": prompt.updated_at,
            "path": f"prompts/{prompt.path.name}",
            "content": prompt.content,
            "search_text": self._search_text(prompt),
        }

    def _read_index_items(self) -> builtins.list[dict[str, Any]]:
        if not self.index_path.is_file():
            return []
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict):
            return []
        items = data.get("prompts")
        return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []

    def _index_current(self) -> bool:
        if not self.index_path.is_file():
            return False
        index_mtime = self.index_path.stat().st_mtime_ns
        markdown_paths = sorted(self.root.glob("*.md"))
        if any(path.stat().st_mtime_ns > index_mtime for path in markdown_paths):
            return False
        return len(markdown_paths) == len(self._read_index_items())

    def _search_text(self, prompt: Prompt) -> str:
        return (
            f"{prompt.id}\n{prompt.title}\n{prompt.description}\n"
            f"{prompt.kind}\n{prompt.domain}\n{prompt.intent}\n"
            f"{' '.join(prompt.tags)}\n{' '.join(prompt.surfaces)}\n"
            f"{' '.join(prompt.triggers)}\n{' '.join(prompt.use_cases)}\n"
            f"{' '.join(prompt.inputs)}\n{' '.join(prompt.outputs)}\n"
            f"{' '.join(prompt.source_refs)}\n{prompt.content}"
        )

    def _require_prompt_frontmatter(self, frontmatter: dict[str, Any], path: Path) -> None:
        missing = [field for field in PROMPT_REQUIRED_FIELDS if field not in frontmatter]
        if missing:
            raise ValueError(
                f"Prompt frontmatter missing required fields in {path}: {', '.join(missing)}"
            )
        if str(frontmatter.get("type") or "") != "Prompt":
            raise ValueError(f"Prompt frontmatter type must be Prompt in {path}")
        if str(frontmatter.get("schema") or "") != PROMPT_SCHEMA:
            raise ValueError(f"Prompt frontmatter schema must be {PROMPT_SCHEMA} in {path}")

    def _body(self, title: str, description: str, content: str) -> str:
        parts = [f"# {title}"]
        if description:
            parts.extend(["", description])
        parts.extend(["", "## Prompt", "", content])
        return "\n".join(parts) + "\n"

    def _content_from_body(self, body: str) -> str:
        marker = "## Prompt"
        if marker not in body:
            return body.strip()
        return body.split(marker, 1)[1].strip()

    def _doc_path(self, doc: MarkdownDoc) -> Path:
        if doc.path is None:
            raise ValueError("Prompt document has no path")
        return doc.path

    def _normalize_tags(self, tags: builtins.list[str]) -> builtins.list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _normalize_refs(self, refs: builtins.list[str]) -> builtins.list[str]:
        values: builtins.list[str] = []
        for ref in refs:
            value = str(ref or "").strip()
            if value and not value.startswith(("/", "~")) and ":" not in value:
                value = f"/{value}"
            if value and value not in values:
                values.append(value)
        return values

    def _normalize_kind(self, value: str) -> str:
        kind = normalize_tag(value or PROMPT_DEFAULT_KIND, self.taxonomy).replace("-", "_")
        return kind if kind in PROMPT_ALLOWED_KINDS else PROMPT_DEFAULT_KIND

    def _normalize_quality(self, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        out: dict[str, Any] = {}
        status = str(value.get("status") or "").strip()
        if status:
            out["status"] = "curated" if status == "proposed" else status
        score = value.get("score")
        if isinstance(score, int | float):
            out["score"] = max(0.0, min(1.0, float(score)))
        notes = str(value.get("notes") or "").strip()
        if notes:
            out["notes"] = notes
        last_eval_at = str(value.get("last_eval_at") or "").strip()
        if last_eval_at:
            out["last_eval_at"] = last_eval_at
        return out

    def _prompt_use_cases(self, request: AddPromptRequest) -> builtins.list[str]:
        explicit = self._normalize_list(request.use_cases)
        if explicit:
            return explicit
        inferred = self._infer_use_cases(request)
        return inferred or ["General prompt reuse"]

    def _infer_use_cases(self, request: AddPromptRequest) -> builtins.list[str]:
        text = " ".join(
            [
                request.title,
                request.description,
                request.content,
                " ".join(request.tags),
            ]
        ).casefold()
        candidates = [
            (("review", "regression", "missing test", "correctness", "pr "), "Code review"),
            (("debug", "bug", "root cause", "failure", "diagnose"), "Debugging"),
            (("write", "writing", "article", "draft", "prose"), "Writing"),
            (("architecture", "design", "module", "interface"), "Architecture review"),
            (("summar", "extract", "tl;dr", "tldr"), "Summarization"),
            (("plan", "task", "todo", "roadmap"), "Planning"),
            (("research", "source", "citation"), "Research"),
        ]
        use_cases: builtins.list[str] = []
        for needles, label in candidates:
            if any(needle in text for needle in needles):
                use_cases.append(label)
        return use_cases[:3]

    def _normalize_list(self, values: builtins.list[str]) -> builtins.list[str]:
        out: builtins.list[str] = []
        for value in values:
            item = str(value or "").strip()
            if item and item not in out:
                out.append(item)
        return out

    def _as_list(self, value: object) -> builtins.list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if value:
            return [str(value)]
        return []

    def _as_dict(self, value: object) -> dict[str, Any]:
        return dict(value) if isinstance(value, dict) else {}
