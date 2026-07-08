from __future__ import annotations

from pathlib import Path

import yaml

from alcove.home import AlcoveHome


VALID_PROFILE_TARGETS = {"codex", "claude"}
ALCOVE_SECTION_START = "<!-- ALCOVE ENTRY START -->"
ALCOVE_SECTION_END = "<!-- ALCOVE ENTRY END -->"


class ProfileInstaller:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def hub_init(
        self,
        path: Path | str,
        default_kb: str = "",
        targets: list[str] | None = None,
    ) -> dict:
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
    ) -> dict:
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
    ) -> dict:
        record = self.home.get_knowledge_base(kb)
        root = record.path
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
    ) -> list[dict]:
        resolved_targets = _targets(targets)
        files: list[dict] = []
        if "claude" in resolved_targets:
            files.append(self._upsert_entry_doc(root / "CLAUDE.md", profile, default_kb))
            files.append(
                self._write_skill(root / ".claude" / "skills" / skill_name, profile, default_kb)
            )
        if "codex" in resolved_targets:
            files.append(self._upsert_entry_doc(root / "AGENTS.md", profile, default_kb))
            files.append(
                self._write_skill(root / ".agents" / "skills" / skill_name, profile, default_kb)
            )
        return files

    def _upsert_entry_doc(self, path: Path, profile: str, default_kb: str) -> dict:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        section = self._entry_section(profile, default_kb)
        content = _upsert_marked_section(existing, section)
        path.parent.mkdir(parents=True, exist_ok=True)
        action = "updated" if path.is_file() else "created"
        if path.is_file() and existing == content:
            action = "unchanged"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "action": action}

    def _write_skill(self, root: Path, profile: str, default_kb: str) -> dict:
        path = root / "SKILL.md"
        root.mkdir(parents=True, exist_ok=True)
        content = self._skill_content(profile, default_kb)
        action = "updated" if path.is_file() else "created"
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            action = "unchanged"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "action": action}

    def _entry_section(self, profile: str, default_kb: str) -> str:
        kb_part = f" --kb {default_kb}" if default_kb else ""
        home_part = self._home_arg()
        if profile == "hub":
            description = "This directory is the Alcove hub workspace."
        else:
            description = "This directory is an Alcove managed knowledge base workspace."
        return (
            f"{ALCOVE_SECTION_START}\n"
            "## Alcove Entry\n\n"
            f"{description}\n\n"
            f"- Home: `{self.home.root}`\n"
            f"- Default KB: `{default_kb or '(none)'}`\n\n"
            "Common commands:\n\n"
            "```sh\n"
            f'alcove search{home_part}{kb_part} "query"\n'
            f"alcove inbox{home_part}{kb_part} peek\n"
            f"alcove pin{home_part} list\n"
            f"alcove task{home_part} list\n"
            "```\n"
            f"{ALCOVE_SECTION_END}\n"
        )

    def _skill_content(self, profile: str, default_kb: str) -> str:
        kb_part = f" --kb {default_kb}" if default_kb else ""
        home_part = self._home_arg()
        if profile == "hub":
            description = "Use for Alcove hub conversations: search, pins, tasks, mounts, connectors, and managed KB routing."
        else:
            description = "Use inside an Alcove managed knowledge base for inbox review, OKF notes, validation, and gardening."
        return (
            "# Alcove Entry\n\n"
            f"{description}\n\n"
            "## Commands\n\n"
            "```sh\n"
            f'alcove search{home_part}{kb_part} "query"\n'
            f"alcove inbox{home_part}{kb_part} peek --json\n"
            f"alcove validate{home_part}{kb_part} --json\n"
            "```\n"
        )

    def _home_arg(self) -> str:
        if self.home.root == AlcoveHome.default_root().expanduser().resolve():
            return ""
        return f" --home {self.home.root}"


def _targets(targets: list[str]) -> list[str]:
    if not targets or "all" in targets:
        return ["codex", "claude"]
    normalized = []
    for target in targets:
        for item in str(target).split(","):
            value = item.strip().lower()
            if not value:
                continue
            if value not in VALID_PROFILE_TARGETS:
                raise ValueError(f"Unknown install target: {value}")
            if value not in normalized:
                normalized.append(value)
    return normalized


def _upsert_marked_section(existing: str, section: str) -> str:
    if ALCOVE_SECTION_START not in existing:
        prefix = existing.rstrip()
        if prefix:
            return f"{prefix}\n\n{section}"
        return section
    start = existing.index(ALCOVE_SECTION_START)
    end = existing.index(ALCOVE_SECTION_END, start) + len(ALCOVE_SECTION_END)
    return f"{existing[:start].rstrip()}\n\n{section}{existing[end:].lstrip()}"
