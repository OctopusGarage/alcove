from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, TypeAlias

import yaml

from alcove.agent_targets import resolve_agent_targets
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.profile_packs import (
    ALCOVE_SECTION_END,
    ALCOVE_SECTION_START,
    ProfileArtifact,
    ProfileInstallationPack,
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
        link: bool = False,
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
            link=link,
        )
        return {
            "profile": "hub",
            "mode": "link" if link else "copy",
            "path": compact_user_path(root),
            "home": compact_user_path(self.home.root),
            "default_kb": default_kb,
            "files": files,
        }

    def hub_status(
        self,
        path: Path | str,
        default_kb: str = "",
        targets: list[str] | None = None,
    ) -> ProfileReport:
        root = Path(path).expanduser().resolve()
        files = [
            self._file_status(
                root / ".alcove-hub.yml",
                self._hub_config_content(default_kb),
                match_mode="exact",
            )
        ]
        files.extend(
            self._project_profile_status(
                root,
                profile="hub",
                skill_name="alcove-hub",
                default_kb=default_kb,
                targets=targets or ["all"],
            )
        )
        return {
            "profile": "hub",
            "path": compact_user_path(root),
            "home": compact_user_path(self.home.root),
            "default_kb": default_kb,
            "exists": root.is_dir(),
            "files": files,
        }

    def hub_install(
        self,
        path: Path | str,
        default_kb: str = "",
        targets: list[str] | None = None,
        link: bool = False,
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
            link=link,
        )
        return {
            "profile": "hub",
            "mode": "link" if link else "copy",
            "path": compact_user_path(root),
            "home": compact_user_path(self.home.root),
            "default_kb": default_kb,
            "files": files,
        }

    def kb_status(
        self,
        kb: str,
        targets: list[str] | None = None,
    ) -> ProfileReport:
        record = self.home.get_knowledge_base(kb)
        root = record.path
        files = self._project_profile_status(
            root,
            profile="managed-kb",
            skill_name="alcove-kb",
            default_kb=record.name,
            targets=targets or ["all"],
        )
        return {
            "profile": "managed-kb",
            "kb": record.name,
            "path": compact_user_path(root),
            "home": compact_user_path(self.home.root),
            "exists": root.is_dir(),
            "files": files,
        }

    def kb_install(
        self,
        kb: str,
        targets: list[str] | None = None,
        link: bool = False,
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
            link=link,
        )
        return {
            "profile": "managed-kb",
            "mode": "link" if link else "copy",
            "kb": record.name,
            "path": compact_user_path(root),
            "home": compact_user_path(self.home.root),
            "files": files,
        }

    def _write_hub_config(self, root: Path, default_kb: str) -> None:
        config_path = root / ".alcove-hub.yml"
        config_path.write_text(self._hub_config_content(default_kb), encoding="utf-8")

    def _hub_config_content(self, default_kb: str) -> str:
        content: str = yaml.safe_dump(
            {
                "version": 1,
                "home": compact_user_path(self.home.root),
                "default_kb": default_kb,
            },
            sort_keys=False,
        )
        return content

    def _install_project_profile(
        self,
        root: Path,
        profile: str,
        skill_name: str,
        default_kb: str,
        targets: list[str],
        link: bool = False,
    ) -> list[InstallRecord]:
        if link:
            self._ensure_link_mode_supported()
        resolved_targets = resolve_agent_targets(targets)
        pack = ProfileInstallationPack(profile=profile, skill_name=skill_name)
        files: list[InstallRecord] = []
        if "claude" in resolved_targets:
            files.append(self._upsert_entry_doc(root / "CLAUDE.md", pack, default_kb))
            files.append(
                self._write_skill(
                    root / ".claude" / "skills" / skill_name,
                    pack,
                    default_kb,
                    link=link,
                )
            )
            files.extend(
                self._install_profile_artifacts(pack.claude_artifacts(root, default_kb), link=link)
            )
        if "codex" in resolved_targets:
            files.append(self._upsert_entry_doc(root / "AGENTS.md", pack, default_kb))
            files.append(
                self._write_skill(
                    root / ".agents" / "skills" / skill_name,
                    pack,
                    default_kb,
                    link=link,
                )
            )
            files.extend(
                self._install_profile_artifacts(pack.codex_artifacts(root, default_kb), link=link)
            )
        return files

    def _project_profile_status(
        self,
        root: Path,
        profile: str,
        skill_name: str,
        default_kb: str,
        targets: list[str],
    ) -> list[dict[str, Any]]:
        resolved_targets = resolve_agent_targets(targets)
        pack = ProfileInstallationPack(profile=profile, skill_name=skill_name)
        files: list[dict[str, Any]] = []
        entry_section = pack.entry_section(
            compact_user_path(self.home.root), default_kb, self._home_arg()
        )
        skill_content = pack.skill_content(default_kb, self._home_arg()).rstrip() + "\n"
        if "claude" in resolved_targets:
            files.append(
                self._file_status(
                    root / "CLAUDE.md",
                    entry_section,
                    target="claude",
                    kind="entry",
                    match_mode="marked-section",
                )
            )
            files.append(
                self._file_status(
                    root / ".claude" / "skills" / skill_name / "SKILL.md",
                    skill_content,
                    target="claude",
                    kind="skill",
                    match_mode="exact",
                    expected_source=pack.skill_source_path(),
                )
            )
            files.extend(
                self._artifact_status(
                    pack.claude_artifacts(root, default_kb),
                    target="claude",
                )
            )
        if "codex" in resolved_targets:
            files.append(
                self._file_status(
                    root / "AGENTS.md",
                    entry_section,
                    target="codex",
                    kind="entry",
                    match_mode="marked-section",
                )
            )
            files.append(
                self._file_status(
                    root / ".agents" / "skills" / skill_name / "SKILL.md",
                    skill_content,
                    target="codex",
                    kind="skill",
                    match_mode="exact",
                    expected_source=pack.skill_source_path(),
                )
            )
            files.extend(
                self._artifact_status(
                    pack.codex_artifacts(root, default_kb),
                    target="codex",
                )
            )
        return files

    def _artifact_status(
        self, artifacts: list[ProfileArtifact], *, target: str
    ) -> list[dict[str, Any]]:
        return [
            self._file_status(
                artifact.path,
                artifact.content.rstrip() + "\n",
                target=target,
                kind="artifact",
                match_mode="exact",
                expected_source=artifact.source_path,
            )
            for artifact in artifacts
        ]

    def _file_status(
        self,
        path: Path,
        expected: str,
        *,
        target: str = "",
        kind: str = "config",
        match_mode: str,
        expected_source: Path | None = None,
    ) -> dict[str, Any]:
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        expected_content = expected.rstrip() + "\n"
        if match_mode == "marked-section":
            workspace_match = self._extract_marked_section(content) == expected_content
        elif match_mode == "exact":
            workspace_match = content == expected_content
        else:
            raise ValueError(f"Unknown profile status match mode: {match_mode}")
        payload: dict[str, Any] = {
            "path": str(path),
            "kind": kind,
            "installed": path.is_file(),
            "workspace_match": workspace_match,
            "is_symlink": path.is_symlink(),
        }
        if path.is_symlink():
            link_target = path.readlink()
            payload["link_target"] = str(link_target)
            if expected_source is not None:
                payload["source_match"] = path.resolve() == expected_source.resolve()
        if target:
            payload["target"] = target
        return payload

    def _extract_marked_section(self, content: str) -> str:
        if ALCOVE_SECTION_START not in content:
            return ""
        start = content.index(ALCOVE_SECTION_START)
        try:
            end = content.index(ALCOVE_SECTION_END, start) + len(ALCOVE_SECTION_END)
        except ValueError:
            return ""
        return content[start:end].rstrip() + "\n"

    def _upsert_entry_doc(
        self, path: Path, pack: ProfileInstallationPack, default_kb: str
    ) -> InstallRecord:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        section = pack.entry_section(
            compact_user_path(self.home.root), default_kb, self._home_arg()
        )
        content = upsert_marked_section(existing, section)
        path.parent.mkdir(parents=True, exist_ok=True)
        action = "updated" if path.is_file() else "created"
        if path.is_file() and existing == content:
            action = "unchanged"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "action": action}

    def _write_skill(
        self, root: Path, pack: ProfileInstallationPack, default_kb: str, *, link: bool = False
    ) -> InstallRecord:
        path = root / "SKILL.md"
        if root.is_symlink():
            root.unlink()
        root.mkdir(parents=True, exist_ok=True)
        if link:
            source_path = pack.skill_source_path()
            if source_path is None:
                raise ValueError(f"Profile does not support linked skill install: {pack.profile}")
            return self._link_text_file(path, source_path)
        content = pack.skill_content(default_kb, self._home_arg())
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

    def _link_text_file(self, path: Path, source_path: Path) -> InstallRecord:
        source = source_path.resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Profile template not found: {source}")
        if path.parent.is_symlink():
            path.parent.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        action = "updated"
        if path.is_symlink() and path.resolve() == source:
            return {
                "path": str(path),
                "action": "unchanged",
                "mode": "link",
                "source": compact_user_path(source),
            }
        elif not path.exists() and not path.is_symlink():
            action = "linked"
        if path.exists() or path.is_symlink():
            path.unlink()
        path.symlink_to(source)
        return {
            "path": str(path),
            "action": action,
            "mode": "link",
            "source": compact_user_path(source),
        }

    def _install_profile_artifacts(
        self, artifacts: list[ProfileArtifact], *, link: bool = False
    ) -> list[InstallRecord]:
        files: list[InstallRecord] = []
        for artifact in artifacts:
            if link:
                if artifact.source_path is None:
                    raise ValueError(
                        f"Profile artifact does not support linked install: {artifact.path}"
                    )
                files.append(self._link_text_file(artifact.path, artifact.source_path))
            else:
                files.append(self._write_text_file(artifact.path, artifact.content))
        return files

    def _remove_legacy_kb_artifacts(self, root: Path) -> None:
        legacy_scripts = root / ".claude" / "skills" / "social_post_manager" / "scripts"
        if legacy_scripts.exists() and legacy_scripts.is_dir():
            shutil.rmtree(legacy_scripts)

    def _home_arg(self) -> str:
        if self.home.root == AlcoveHome.default_root().expanduser().resolve():
            return ""
        return f" --home {compact_user_path(self.home.root)}"

    def _ensure_link_mode_supported(self) -> None:
        if self._home_arg():
            raise ValueError("Linked profile install requires the default Alcove Home (~/.alcove).")
