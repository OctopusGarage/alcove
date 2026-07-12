from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AddProjectRequest:
    alias: str
    path: str
    note: str = ""


@dataclass(frozen=True)
class ProjectRecord:
    alias: str
    path: Path
    note: str = ""
    exists: bool = False
    source: str = "registry"
    created_at: str = ""
    updated_at: str = ""


class ProjectsModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.root = self.runtime.projects_root
        self.store_path = self.root / "projects.json"

    def add(self, request: AddProjectRequest) -> ProjectRecord:
        data = self._load()
        key = normalize_slug(request.alias)
        timestamp = now_iso()
        existing = data["projects"].get(key) or {}
        project_path = Path(request.path).expanduser().resolve()
        record = {
            "alias": key,
            "path": compact_user_path(project_path),
            "note": request.note,
            "created_at": existing.get("created_at") or timestamp,
            "updated_at": timestamp,
        }
        data["projects"][key] = record
        self._save(data)
        return self._record(record)

    def get(self, alias: str) -> ProjectRecord:
        key = normalize_slug(alias)
        data = self._load()
        if key not in data["projects"]:
            raise FileNotFoundError(f"Project not found: {alias}")
        return self._record(data["projects"][key])

    def list(self) -> builtins.list[ProjectRecord]:
        return [self._record(item) for _, item in sorted(self._load()["projects"].items())]

    def find(self, keyword: str) -> builtins.list[ProjectRecord]:
        query = str(keyword or "").casefold()
        data = self._load()
        matches: builtins.list[ProjectRecord] = []
        for item in data["projects"].values():
            record = self._record(item)
            text = f"{record.alias}\n{record.path}\n{record.note}".casefold()
            if not query or query in text:
                matches.append(record)
        if matches:
            return matches
        return self._scan_roots(query, data["roots"])

    def remove(self, alias: str) -> dict[str, Any]:
        key = normalize_slug(alias)
        data = self._load()
        if key not in data["projects"]:
            return {"status": "missing", "alias": key}
        removed = data["projects"].pop(key)
        self._save(data)
        return {"status": "removed", "project": self._record_dict(self._record(removed))}

    def configure_roots(self, roots: builtins.list[str]) -> dict[str, Any]:
        data = self._load()
        data["roots"] = [
            compact_user_path(Path(root).expanduser()) for root in roots if str(root).strip()
        ]
        self._save(data)
        return {"status": "configured", "roots": data["roots"]}

    def roots(self) -> builtins.list[str]:
        return [str(root) for root in self._load()["roots"]]

    def _scan_roots(
        self,
        query: str,
        roots: builtins.list[str],
    ) -> builtins.list[ProjectRecord]:
        matches: builtins.list[ProjectRecord] = []
        for root in roots:
            root_path = Path(root).expanduser()
            if not root_path.is_dir():
                continue
            for child in sorted(root_path.iterdir(), key=lambda path: path.name.casefold()):
                if not child.is_dir():
                    continue
                if query and query not in child.name.casefold():
                    continue
                matches.append(
                    ProjectRecord(
                        alias=normalize_slug(child.name),
                        path=child.resolve(),
                        exists=True,
                        source="root-scan",
                    )
                )
        return matches

    def _load(self) -> dict[str, Any]:
        if not self.store_path.is_file():
            return {"projects": {}, "roots": []}
        data = json.loads(self.store_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"projects": {}, "roots": []}
        projects = data.get("projects") if isinstance(data.get("projects"), dict) else {}
        roots = data.get("roots") if isinstance(data.get("roots"), list) else []
        return {"projects": projects, "roots": roots}

    def _save(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _record(self, item: dict[str, Any]) -> ProjectRecord:
        path = Path(str(item.get("path") or "")).expanduser()
        return ProjectRecord(
            alias=str(item.get("alias") or path.name),
            path=path,
            note=str(item.get("note") or ""),
            exists=path.exists(),
            source=str(item.get("source") or "registry"),
            created_at=str(item.get("created_at") or ""),
            updated_at=str(item.get("updated_at") or ""),
        )

    def _record_dict(self, record: ProjectRecord) -> dict[str, Any]:
        return {
            "alias": record.alias,
            "path": str(record.path),
            "note": record.note,
            "exists": record.exists,
            "source": record.source,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }
