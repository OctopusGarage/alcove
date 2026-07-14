from __future__ import annotations

import builtins
from dataclasses import dataclass, field
import shutil
import subprocess
from pathlib import Path
from typing import Any

import yaml

from alcove.home import AlcoveHome
from alcove.knowledge import AddConceptRequest, KnowledgeModule, NoteSourceRequest
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path
from alcove.profile_installer import ProfileInstaller
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


WORKSPACE_CONFIG_FILE = ".alcove-workspace.yml"


@dataclass(frozen=True)
class AgentWorkspaceRecord:
    id: str
    path: Path
    profile: str = "workspace"
    name: str = ""
    default_kb: str = ""
    tags: builtins.list[str] = field(default_factory=list)
    modules: builtins.list[str] = field(default_factory=list)
    context: str = ""
    install_mode: str = "copy"
    targets: builtins.list[str] = field(default_factory=lambda: ["codex", "claude"])

    @property
    def skill_name(self) -> str:
        return "alcove-hub" if self.profile == "hub" else "alcove-workspace"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name or self.id,
            "profile": self.profile,
            "path": str(self.path),
            "default_kb": self.default_kb,
            "tags": list(self.tags),
            "modules": list(self.modules),
            "context": self.context,
            "install_mode": self.install_mode,
            "targets": list(self.targets),
        }


class AgentWorkspacesModule:
    def __init__(self, home: AlcoveHome | None = None) -> None:
        self.home = home or AlcoveHome.init()
        self.root = self.home.root / "workspaces"
        self.data_root = self.root / "data"

    def init(
        self,
        workspace_id: str = "hub",
        *,
        path: str = "",
        default_kb: str = "",
        name: str = "",
        tags: builtins.list[str] | None = None,
        modules: builtins.list[str] | None = None,
        context: str = "",
        targets: builtins.list[str] | None = None,
        link: bool = False,
    ) -> dict[str, Any]:
        record = self._record_from_inputs(
            workspace_id,
            path=path,
            default_kb=default_kb,
            name=name,
            tags=tags or [],
            modules=modules or [],
            context=context,
            targets=targets or ["all"],
            install_mode="link" if link else "copy",
        )
        record.path.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self._write_registry(record)
        self._write_local_config(record)
        files = self._install_profile(record, link=link)
        return {
            "workspace": record.as_dict(),
            "registry": compact_user_path(self._registry_path(record.id)),
            "home": compact_user_path(self.home.root),
            "mode": "link" if link else "copy",
            "files": files,
        }

    def install(
        self,
        workspace_id: str,
        *,
        targets: builtins.list[str] | None = None,
        link: bool = False,
    ) -> dict[str, Any]:
        record = self.get(workspace_id)
        updated = AgentWorkspaceRecord(
            id=record.id,
            path=record.path,
            profile=record.profile,
            name=record.name,
            default_kb=record.default_kb,
            tags=record.tags,
            modules=record.modules,
            context=record.context,
            install_mode="link" if link else "copy",
            targets=targets or record.targets,
        )
        self._write_registry(updated)
        self._write_local_config(updated)
        files = self._install_profile(updated, link=link)
        return {
            "workspace": updated.as_dict(),
            "registry": compact_user_path(self._registry_path(updated.id)),
            "home": compact_user_path(self.home.root),
            "mode": "link" if link else "copy",
            "files": files,
        }

    def register_hub(
        self,
        path: str | Path,
        *,
        default_kb: str = "",
        targets: builtins.list[str] | None = None,
        install_mode: str = "copy",
    ) -> AgentWorkspaceRecord:
        record = self._record_from_inputs(
            "hub",
            path=str(path),
            default_kb=default_kb,
            name="Hub",
            tags=[],
            modules=[],
            context="",
            targets=targets or ["all"],
            install_mode=install_mode,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self._write_registry(record)
        return record

    def status(self, workspace_id: str) -> dict[str, Any]:
        record = self.get(workspace_id)
        files = ProfileInstaller(self.home).project_profile_status(
            record.path,
            profile=record.profile,
            skill_name=record.skill_name,
            default_kb=record.default_kb,
            targets=record.targets,
        )
        config_path = record.path / self._local_config_name(record)
        files.insert(
            0,
            {
                "path": str(config_path),
                "kind": "config",
                "installed": config_path.is_file(),
                "workspace_match": True,
                "is_symlink": config_path.is_symlink(),
            },
        )
        return {
            "workspace": record.as_dict(),
            "registry": compact_user_path(self._registry_path(record.id)),
            "exists": record.path.is_dir(),
            "files": files,
        }

    def list(self) -> builtins.list[AgentWorkspaceRecord]:
        records: builtins.list[AgentWorkspaceRecord] = []
        if not self.root.is_dir():
            return records
        for path in sorted(self.root.glob("*.yml")):
            try:
                records.append(self._read_record(path))
            except (OSError, ValueError, yaml.YAMLError):
                continue
        return records

    def get(self, workspace_id: str) -> AgentWorkspaceRecord:
        workspace_slug = self._slug(workspace_id)
        path = self._registry_path(workspace_slug)
        if not path.is_file():
            raise FileNotFoundError(f"Agent workspace not registered: {workspace_slug}")
        return self._read_record(path)

    def run_command(
        self,
        workspace_id: str,
        *,
        agent: str,
        prompt: str,
        print_command: bool = False,
    ) -> dict[str, Any]:
        record = self.get(workspace_id)
        command = self._agent_command(agent, record.path, prompt)
        payload: dict[str, Any] = {
            "workspace": record.as_dict(),
            "agent": agent,
            "cwd": str(record.path),
            "prompt": prompt,
            "command": command,
        }
        if print_command:
            payload["status"] = "planned"
            return payload
        result = subprocess.run(  # noqa: S603 - command is a fixed argv for codex/claude.
            command,
            cwd=record.path,
            text=True,
            capture_output=True,
            check=False,
        )
        payload.update(
            {
                "status": "ok" if result.returncode == 0 else "failed",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        return payload

    def okf_init(self, workspace_id: str, *, kb_name: str = "") -> dict[str, Any]:
        record = self.get(workspace_id)
        kb_slug = self._slug(kb_name or record.default_kb or record.id)
        okf_root = record.path / "okf"
        documents_root = record.path / "documents"
        documents_root.mkdir(parents=True, exist_ok=True)
        Workspace.init(okf_root)
        kb_record = self.home.register_knowledge_base(kb_slug, okf_root)
        updated = self._replace_record(record, default_kb=kb_record.name)
        self._write_registry(updated)
        self._write_local_config(updated)
        return {
            "status": "initialized",
            "workspace": updated.as_dict(),
            "okf": self._okf_payload(updated, kb_record.name),
            "registry": compact_user_path(self._registry_path(updated.id)),
            "kb_registry": compact_user_path(kb_record.config_path),
        }

    def okf_status(self, workspace_id: str) -> dict[str, Any]:
        record = self.get(workspace_id)
        return {
            "workspace": record.as_dict(),
            "okf": self._okf_payload(record, record.default_kb),
            "registry": compact_user_path(self._registry_path(record.id)),
        }

    def okf_add_note(
        self,
        workspace_id: str,
        *,
        topic: str,
        title: str,
        summary: str,
        tags: builtins.list[str] | None = None,
    ) -> dict[str, Any]:
        record = self._ensure_okf(workspace_id)
        scoped_tags = self._workspace_tags(record, tags or [])
        result = KnowledgeModule(Workspace.discover(record.path / "okf")).add_concept(
            AddConceptRequest(topic=topic, title=title, summary=summary, tags=scoped_tags)
        )
        return {
            "status": "noted",
            "workspace": record.as_dict(),
            "kb": record.default_kb,
            "path": compact_user_path(result.path),
            "tags": scoped_tags,
        }

    def okf_import_file(
        self,
        workspace_id: str,
        *,
        file_path: str,
        topic: str = "",
        title: str = "",
        tags: builtins.list[str] | None = None,
        copy: bool = True,
    ) -> dict[str, Any]:
        record = self._ensure_okf(workspace_id)
        source = Path(file_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"File not found: {source}")
        documents_root = record.path / "documents"
        documents_root.mkdir(parents=True, exist_ok=True)
        stored = documents_root / source.name
        if copy and source != stored:
            shutil.copy2(source, stored)
        else:
            stored = source
        content = self._read_import_text(stored)
        source_title = title or self._title_from_file(stored)
        scoped_tags = self._workspace_tags(record, tags or [])
        result = KnowledgeModule(Workspace.discover(record.path / "okf")).note_source(
            NoteSourceRequest(
                platform="workspace-file",
                title=source_title,
                topic=topic or f"{record.id}/documents",
                resource=compact_user_path(stored),
                summary=self._summary_from_text(content, source_title),
                source_excerpt=content[:1200],
                tags=scoped_tags,
                create_concept=True,
            )
        )
        return {
            "status": "imported",
            "workspace": record.as_dict(),
            "kb": record.default_kb,
            "file": compact_user_path(stored),
            "source_path": compact_user_path(result.source_path),
            "concept_path": compact_user_path(result.concept_path) if result.concept_path else "",
            "tags": scoped_tags,
        }

    def okf_search(
        self,
        workspace_id: str,
        *,
        query: str,
        limit: int = 20,
    ) -> dict[str, Any]:
        record = self._ensure_okf(workspace_id)
        search = SearchModule(workspace=Workspace.discover(record.path / "okf"))
        results = search.search(SearchRequest(query=query, limit=limit))
        if not results:
            results = self._relaxed_okf_search(search, query=query, limit=limit)
        return {
            "workspace": record.as_dict(),
            "kb": record.default_kb,
            "count": len(results),
            "results": results,
        }

    def _install_profile(
        self, record: AgentWorkspaceRecord, *, link: bool
    ) -> builtins.list[dict[str, str]]:
        installer = ProfileInstaller(self.home)
        if record.profile == "hub":
            result = installer.hub_init(
                record.path,
                default_kb=record.default_kb,
                targets=record.targets,
                link=link,
            )
            return list(result["files"])
        return installer.project_profile_install(
            record.path,
            profile=record.profile,
            skill_name=record.skill_name,
            default_kb=record.default_kb,
            targets=record.targets,
            link=link,
        )

    def _record_from_inputs(
        self,
        workspace_id: str,
        *,
        path: str,
        default_kb: str,
        name: str,
        tags: builtins.list[str],
        modules: builtins.list[str],
        context: str,
        targets: builtins.list[str],
        install_mode: str,
    ) -> AgentWorkspaceRecord:
        workspace_slug = self._slug(workspace_id or "hub")
        profile = "hub" if workspace_slug == "hub" else "workspace"
        workspace_path = (
            Path(path).expanduser().resolve()
            if path
            else (self.data_root / workspace_slug).expanduser().resolve()
        )
        normalized_tags = [self._slug(tag) for tag in tags if str(tag).strip()]
        if profile == "workspace" and workspace_slug not in normalized_tags:
            normalized_tags.insert(0, workspace_slug)
        normalized_modules = modules or self._default_modules(profile)
        return AgentWorkspaceRecord(
            id=workspace_slug,
            path=workspace_path,
            profile=profile,
            name=name or ("Hub" if profile == "hub" else workspace_slug),
            default_kb=default_kb,
            tags=normalized_tags,
            modules=normalized_modules,
            context=context,
            install_mode=install_mode,
            targets=targets,
        )

    def _write_registry(self, record: AgentWorkspaceRecord) -> None:
        data = self._record_yaml(record)
        self._registry_path(record.id).write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _write_local_config(self, record: AgentWorkspaceRecord) -> None:
        data = self._record_yaml(record)
        (record.path / self._local_config_name(record)).write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def _record_yaml(self, record: AgentWorkspaceRecord) -> dict[str, Any]:
        return {
            "version": 1,
            "id": record.id,
            "name": record.name or record.id,
            "kind": "agent-workspace",
            "profile": record.profile,
            "path": compact_user_path(record.path),
            "home": compact_user_path(self.home.root),
            "default_kb": record.default_kb,
            "scope": {
                "preferred_kbs": [record.default_kb] if record.default_kb else [],
                "tags": list(record.tags),
                "modules": list(record.modules),
            },
            "agent": {
                "targets": list(record.targets),
                "install_mode": record.install_mode,
            },
            "permissions": self._permissions(record.profile),
            "context": {
                "purpose": record.context,
                "default_write_policy": self._write_policy(record),
            },
        }

    def _read_record(self, path: Path) -> AgentWorkspaceRecord:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid workspace registry: {path}")
        raw_scope = data.get("scope")
        raw_agent = data.get("agent")
        raw_context = data.get("context")
        scope: dict[str, Any] = raw_scope if isinstance(raw_scope, dict) else {}
        agent: dict[str, Any] = raw_agent if isinstance(raw_agent, dict) else {}
        context: dict[str, Any] = raw_context if isinstance(raw_context, dict) else {}
        return AgentWorkspaceRecord(
            id=self._slug(str(data.get("id") or path.stem)),
            path=Path(str(data.get("path") or "")).expanduser().resolve(),
            profile=str(data.get("profile") or "workspace"),
            name=str(data.get("name") or ""),
            default_kb=str(data.get("default_kb") or ""),
            tags=[str(item) for item in scope.get("tags", []) if str(item).strip()],
            modules=[str(item) for item in scope.get("modules", []) if str(item).strip()],
            context=str(context.get("purpose") or ""),
            install_mode=str(agent.get("install_mode") or "copy"),
            targets=[str(item) for item in agent.get("targets", ["codex", "claude"])],
        )

    def _registry_path(self, workspace_id: str) -> Path:
        return self.root / f"{self._slug(workspace_id)}.yml"

    def _local_config_name(self, record: AgentWorkspaceRecord) -> str:
        return ".alcove-hub.yml" if record.profile == "hub" else WORKSPACE_CONFIG_FILE

    def _agent_command(self, agent: str, cwd: Path, prompt: str) -> builtins.list[str]:
        normalized = agent.strip().lower()
        if normalized == "codex":
            return ["codex", "exec", "-C", str(cwd), prompt]
        if normalized == "claude":
            return ["claude", "-p", prompt]
        raise ValueError("Agent must be one of: codex, claude")

    def _permissions(self, profile: str) -> dict[str, bool]:
        admin = profile == "hub"
        return {
            "admin": admin,
            "external_index_write": admin,
            "service_control": admin,
            "export": admin,
        }

    def _write_policy(self, record: AgentWorkspaceRecord) -> str:
        if record.profile == "hub":
            return "Route global writes through the matching Alcove module."
        tag = record.tags[0] if record.tags else record.id
        return f"Prefer this workspace's default KB and preserve the `{tag}` tag."

    def _default_modules(self, profile: str) -> builtins.list[str]:
        if profile == "hub":
            return [
                "knowledge",
                "pins",
                "tasks",
                "prompts",
                "projects",
                "mounts",
                "connectors",
                "radars",
                "service",
            ]
        return ["knowledge", "pins", "tasks", "ideas", "prompts"]

    def _slug(self, value: str) -> str:
        return normalize_slug(value).replace("-", "_")

    def _replace_record(
        self,
        record: AgentWorkspaceRecord,
        *,
        default_kb: str,
    ) -> AgentWorkspaceRecord:
        return AgentWorkspaceRecord(
            id=record.id,
            path=record.path,
            profile=record.profile,
            name=record.name,
            default_kb=default_kb,
            tags=record.tags,
            modules=record.modules,
            context=record.context,
            install_mode=record.install_mode,
            targets=record.targets,
        )

    def _ensure_okf(self, workspace_id: str) -> AgentWorkspaceRecord:
        record = self.get(workspace_id)
        if record.default_kb and (record.path / "okf" / ".alcove" / "config.yml").is_file():
            return record
        payload = self.okf_init(record.id)
        data = payload["workspace"]
        return AgentWorkspaceRecord(
            id=str(data["id"]),
            path=Path(str(data["path"])).expanduser().resolve(),
            profile=str(data["profile"]),
            name=str(data["name"]),
            default_kb=str(data["default_kb"]),
            tags=[str(item) for item in data.get("tags", [])],
            modules=[str(item) for item in data.get("modules", [])],
            context=str(data.get("context") or ""),
            install_mode=str(data.get("install_mode") or "copy"),
            targets=[str(item) for item in data.get("targets", [])],
        )

    def _okf_payload(self, record: AgentWorkspaceRecord, kb_name: str) -> dict[str, Any]:
        okf_root = record.path / "okf"
        documents_root = record.path / "documents"
        initialized = (okf_root / ".alcove" / "config.yml").is_file()
        knowledge_items = 0
        if initialized:
            knowledge_items = len(
                SearchModule(workspace=Workspace.discover(okf_root)).recent(1_000_000)
            )
        return {
            "initialized": initialized,
            "kb": kb_name,
            "root": str(okf_root.resolve()),
            "documents": str(documents_root.resolve()),
            "knowledge_items": knowledge_items,
        }

    def _workspace_tags(
        self,
        record: AgentWorkspaceRecord,
        tags: builtins.list[str],
    ) -> builtins.list[str]:
        merged: builtins.list[str] = []
        for tag in [*record.tags, *tags]:
            normalized = self._slug(tag)
            if normalized and normalized not in merged:
                merged.append(normalized)
        return merged

    def _read_import_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="ignore")

    def _title_from_file(self, path: Path) -> str:
        for line in self._read_import_text(path).splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                return stripped
        return path.stem.replace("-", " ").replace("_", " ").strip().title()

    def _summary_from_text(self, content: str, title: str) -> str:
        for line in content.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped and stripped != title:
                return stripped[:500]
        return f"Imported workspace file: {title}"

    def _relaxed_okf_search(
        self,
        search: SearchModule,
        *,
        query: str,
        limit: int,
    ) -> builtins.list[dict[str, Any]]:
        candidates: builtins.list[dict[str, Any]] = []
        seen: set[str] = set()
        query_without_spaces = "".join(query.split())
        terms = [term for term in query.split() if term.strip()]
        for relaxed_query in [query_without_spaces, *terms]:
            if not relaxed_query:
                continue
            for row in search.search(SearchRequest(query=relaxed_query, limit=limit)):
                key = str(row.get("path") or row.get("title") or row)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(row)
                if len(candidates) >= limit:
                    return candidates
        return candidates
