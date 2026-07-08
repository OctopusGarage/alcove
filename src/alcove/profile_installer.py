from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, TypeAlias

import yaml

from alcove.agent_targets import resolve_agent_targets
from alcove.home import AlcoveHome
from alcove.profile_packs import (
    entry_section,
    managed_kb_claude_artifacts,
    managed_kb_codex_artifacts,
    skill_content,
    upsert_marked_section,
)


InstallRecord: TypeAlias = dict[str, str]
ProfileReport: TypeAlias = dict[str, Any]


class ProfileInstaller:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def hub_init(
        self,
        path: Path | str,
        default_kb: str = "",
        targets: list[str] | None = None,
    ) -> ProfileReport:
        root = Path(path).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        self._write_hub_config(root, default_kb)
        files = self._install_project_profile(
            root,
            profile="hub",
            skill_name="alcove-hub",
            default_kb=default_kb,
            targets=targets or ["all"],
        )
        return {
            "profile": "hub",
            "path": str(root),
            "home": str(self.home.root),
            "default_kb": default_kb,
            "files": files,
        }

    def hub_install(
        self,
        path: Path | str,
        default_kb: str = "",
        targets: list[str] | None = None,
    ) -> ProfileReport:
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Hub directory not found: {root}")
        files = self._install_project_profile(
            root,
            profile="hub",
            skill_name="alcove-hub",
            default_kb=default_kb,
            targets=targets or ["all"],
        )
        return {
            "profile": "hub",
            "path": str(root),
            "home": str(self.home.root),
            "default_kb": default_kb,
            "files": files,
        }

    def kb_install(
        self,
        kb: str,
        targets: list[str] | None = None,
    ) -> ProfileReport:
        record = self.home.get_knowledge_base(kb)
        root = record.path
        self._remove_legacy_kb_artifacts(root)
        files = self._install_project_profile(
            root,
            profile="managed-kb",
            skill_name="alcove-kb",
            default_kb=record.name,
            targets=targets or ["all"],
        )
        return {
            "profile": "managed-kb",
            "kb": record.name,
            "path": str(root),
            "home": str(self.home.root),
            "files": files,
        }

    def _write_hub_config(self, root: Path, default_kb: str) -> None:
        config_path = root / ".alcove-hub.yml"
        config_path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "home": str(self.home.root),
                    "default_kb": default_kb,
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def _install_project_profile(
        self,
        root: Path,
        profile: str,
        skill_name: str,
        default_kb: str,
        targets: list[str],
    ) -> list[InstallRecord]:
        resolved_targets = resolve_agent_targets(targets)
        files: list[InstallRecord] = []
        if "claude" in resolved_targets:
            files.append(self._upsert_entry_doc(root / "CLAUDE.md", profile, default_kb))
            files.append(
                self._write_skill(root / ".claude" / "skills" / skill_name, profile, default_kb)
            )
            if profile == "managed-kb":
                files.extend(self._install_managed_kb_claude(root, default_kb))
        if "codex" in resolved_targets:
            files.append(self._upsert_entry_doc(root / "AGENTS.md", profile, default_kb))
            files.append(
                self._write_skill(root / ".agents" / "skills" / skill_name, profile, default_kb)
            )
            if profile == "managed-kb":
                files.extend(self._install_managed_kb_codex(root, default_kb))
        return files

    def _upsert_entry_doc(self, path: Path, profile: str, default_kb: str) -> InstallRecord:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        section = entry_section(profile, self.home.root, default_kb, self._home_arg())
        content = upsert_marked_section(existing, section)
        path.parent.mkdir(parents=True, exist_ok=True)
        action = "updated" if path.is_file() else "created"
        if path.is_file() and existing == content:
            action = "unchanged"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "action": action}

    def _write_skill(self, root: Path, profile: str, default_kb: str) -> InstallRecord:
        path = root / "SKILL.md"
        if root.is_symlink():
            root.unlink()
        root.mkdir(parents=True, exist_ok=True)
        content = skill_content(profile, default_kb, self._home_arg())
        action = "updated" if path.is_file() else "created"
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            action = "unchanged"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "action": action}

    def _write_text_file(self, path: Path, content: str) -> InstallRecord:
        if path.parent.is_symlink():
            path.parent.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized = content.rstrip() + "\n"
        action = "updated" if path.is_file() else "created"
        if path.is_file() and path.read_text(encoding="utf-8") == normalized:
            action = "unchanged"
        path.write_text(normalized, encoding="utf-8")
        return {"path": str(path), "action": action}

    def _install_managed_kb_claude(self, root: Path, default_kb: str) -> list[InstallRecord]:
        return [
            self._write_text_file(artifact.path, artifact.content)
            for artifact in managed_kb_claude_artifacts(root, default_kb)
        ]

    def _install_managed_kb_codex(self, root: Path, default_kb: str) -> list[InstallRecord]:
        return [
            self._write_text_file(artifact.path, artifact.content)
            for artifact in managed_kb_codex_artifacts(root, default_kb)
        ]

    def _remove_legacy_kb_artifacts(self, root: Path) -> None:
        legacy_scripts = root / ".claude" / "skills" / "social_post_manager" / "scripts"
        if legacy_scripts.exists() and legacy_scripts.is_dir():
            shutil.rmtree(legacy_scripts)

    def _home_arg(self) -> str:
        if self.home.root == AlcoveHome.default_root().expanduser().resolve():
            return ""
        return f" --home {self.home.root}"
