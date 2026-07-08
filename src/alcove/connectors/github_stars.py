from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path

from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class GitHubStarsImportRequest:
    export_file: str
    tags: list[str] = field(default_factory=list)


class GitHubStarsConnector:
    connector_id = "github-stars"

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.taxonomy = load_taxonomy(self.paths.knowledge)
        self.connector_dir = self.paths.state / "connectors" / self.connector_id
        self.index_path = self.connector_dir / "index.json"

    def import_export(self, request: GitHubStarsImportRequest) -> dict:
        export_file = Path(request.export_file).expanduser().resolve()
        if not export_file.is_file():
            raise FileNotFoundError(f"GitHub stars export file not found: {export_file}")
        data = json.loads(export_file.read_text(encoding="utf-8"))
        repos = self._repositories(data)
        tags = self._normalize_tags(request.tags)
        items: list[dict] = []
        skipped = 0
        for raw in repos:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            item = self._item(raw, export_file, tags)
            if item is None:
                skipped += 1
                continue
            items.append(item)
        self._save_index(items, export_file)
        return {
            "connector": self.connector_id,
            "export_file": str(export_file),
            "index_path": str(self.index_path),
            "scanned": len(items),
            "skipped": skipped,
            "items": items,
        }

    def _repositories(self, data: object) -> list:
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ("repositories", "repos", "items", "nodes"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return []

    def _item(self, raw: dict, export_file: Path, tags: list[str]) -> dict | None:
        full_name = self._string(raw, "full_name", "fullName", "nameWithOwner")
        url = self._string(raw, "html_url", "url")
        if not full_name or not url:
            return None
        description = self._string(raw, "description")
        language = self._language(raw)
        topics = self._topics(raw)
        item_tags = self._normalize_tags([*tags, *topics])
        stars = raw.get("stargazers_count", raw.get("stargazerCount", ""))
        text_parts = [
            full_name,
            description,
            language,
            " ".join(topics),
            f"stars: {stars}" if stars != "" else "",
        ]
        return {
            "connector": self.connector_id,
            "connector_name": "GitHub Stars",
            "type": "GitHub Star",
            "title": full_name,
            "account": "github",
            "folder_path": language,
            "path": str(export_file),
            "resource": url,
            "relative_path": full_name,
            "text": "\n".join(part for part in text_parts if part)[:4000],
            "tags": item_tags,
            "status": "active",
            "stars": stars,
            "language": language,
            "updated_at": self._string(raw, "updated_at", "updatedAt"),
            "indexed_at": now_iso(),
        }

    def _save_index(self, items: list[dict], export_file: Path) -> None:
        self.connector_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "connector": self.connector_id,
                    "export_file": str(export_file),
                    "indexed_at": now_iso(),
                    "items": items,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _language(self, raw: dict) -> str:
        value = raw.get("language")
        if value:
            return str(value)
        value = raw.get("primaryLanguage")
        if isinstance(value, dict):
            return str(value.get("name") or "")
        return ""

    def _topics(self, raw: dict) -> list[str]:
        value = raw.get("topics")
        if isinstance(value, list):
            return [str(item) for item in value if item]
        value = raw.get("repositoryTopics")
        if isinstance(value, dict):
            nodes = value.get("nodes")
            if isinstance(nodes, list):
                topics = []
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    topic = node.get("topic")
                    if isinstance(topic, dict) and topic.get("name"):
                        topics.append(str(topic["name"]))
                return topics
        return []

    def _string(self, raw: dict, *keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value is not None:
                return str(value)
        return ""

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)
