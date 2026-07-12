from __future__ import annotations

import json
import os
from pathlib import Path

from alcove.agent_targets import resolve_agent_targets
from alcove.home import AlcoveHome
from alcove.mcp_toolsets import resolve_mcp_toolset
from alcove.paths import compact_user_path
from alcove.workspace import Workspace


class InstallerModule:
    def __init__(
        self,
        workspace: Workspace | None = None,
        home: AlcoveHome | None = None,
        mcp_toolset: str = "full",
        default_kb: str = "",
    ) -> None:
        self.workspace = workspace
        self.home = home or AlcoveHome.init()
        self.mcp_toolset = resolve_mcp_toolset(mcp_toolset)[0]
        if default_kb:
            self.home.get_knowledge_base(default_kb)
        self.kb_name = default_kb or self._registered_kb_name()

    def install(self, targets: list[str], dry_run: bool = False) -> dict:
        resolved_targets = self._targets(targets)
        configs = {target: self._config_text(target) for target in resolved_targets}
        if dry_run:
            return {**self._scope(), "files": [], "configs": configs}

        files = []
        for target in resolved_targets:
            if target == "codex":
                files.append(self._write_codex())
            elif target == "claude":
                files.extend(self._write_claude())
        return {**self._scope(), "files": files, "configs": configs}

    def status(self, targets: list[str]) -> dict:
        files = []
        for target in self._targets(targets):
            if target == "codex":
                files.append(self._codex_status())
            elif target == "claude":
                files.append(self._claude_status())
        return {**self._scope(), "files": files}

    def uninstall(self, targets: list[str], dry_run: bool = False) -> dict:
        files = []
        for target in self._targets(targets):
            if target == "codex":
                files.append(self._remove_codex(dry_run=dry_run))
            elif target == "claude":
                files.append(self._remove_claude(dry_run=dry_run))
        return {**self._scope(), "files": files}

    def _targets(self, targets: list[str]) -> list[str]:
        return resolve_agent_targets(targets)

    def _mcp_config(self) -> dict:
        args = [
            "serve",
            "--mcp",
            "--toolset",
            self.mcp_toolset,
            "--home",
            compact_user_path(self.home.root),
        ]
        if self.kb_name:
            args.extend(["--kb", self.kb_name])
        elif self.workspace is not None:
            args.extend(["--workspace", compact_user_path(self.workspace.root)])
        return {
            "command": "alcove",
            "args": args,
        }

    def _registered_kb_name(self) -> str:
        if self.workspace is None:
            return ""
        workspace_root = self.workspace.root.resolve()
        for record in self.home.list_knowledge_bases():
            if record.path.resolve() == workspace_root:
                return record.name
        return ""

    def _scope(self) -> dict:
        payload = {"home": compact_user_path(self.home.root), "toolset": self.mcp_toolset}
        if self.workspace is not None:
            payload["workspace"] = compact_user_path(self.workspace.root)
        if self.kb_name:
            payload["kb"] = self.kb_name
        return payload

    def _config_text(self, target: str) -> str:
        if target == "codex":
            return self._codex_block()
        if target == "claude":
            return json.dumps(
                {"mcpServers": {"alcove": self._mcp_config()}},
                ensure_ascii=False,
                indent=2,
            )
        raise ValueError(f"Unknown install target: {target}")

    def _write_codex(self) -> dict:
        path = self._codex_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        action = "updated" if existing else "created"
        content = self._upsert_toml_table(existing, "mcp_servers.alcove", self._codex_block())
        if path.is_file() and existing == content:
            action = "unchanged"
        path.write_text(content, encoding="utf-8")
        return {"target": "codex", "path": str(path), "action": action}

    def _write_claude(self) -> list[dict]:
        records = [self._write_claude_json(self._claude_path(), config_kind="legacy")]
        records.append(
            self._write_claude_json(self._claude_settings_path(), config_kind="settings")
        )
        return records

    def _write_claude_json(self, path: Path, *, config_kind: str) -> dict:
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_json(path)
        before = existing.get("mcpServers", {}).get("alcove")
        existing.setdefault("mcpServers", {})["alcove"] = self._mcp_config()
        if before == self._mcp_config():
            action = "unchanged"
        else:
            action = "updated" if path.is_file() else "created"
        path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"target": "claude", "path": str(path), "action": action, "kind": config_kind}

    def _codex_status(self) -> dict:
        path = self._codex_path()
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        block = self._extract_toml_table(existing, "mcp_servers.alcove")
        return {
            "target": "codex",
            "path": str(path),
            "installed": bool(block),
            "workspace_match": block == self._codex_block(),
        }

    def _claude_status(self) -> dict:
        legacy = self._claude_config_status(self._claude_path(), config_kind="legacy")
        settings = self._claude_config_status(self._claude_settings_path(), config_kind="settings")
        return {
            "target": "claude",
            "path": str(self._claude_path()),
            "settings_path": str(self._claude_settings_path()),
            "installed": legacy["installed"] and settings["installed"],
            "workspace_match": legacy["workspace_match"] and settings["workspace_match"],
            "configs": [legacy, settings],
        }

    def _claude_config_status(self, path: Path, *, config_kind: str) -> dict:
        data = self._read_json(path)
        server = data.get("mcpServers", {}).get("alcove")
        return {
            "kind": config_kind,
            "path": str(path),
            "installed": isinstance(server, dict),
            "workspace_match": server == self._mcp_config(),
        }

    def _remove_codex(self, dry_run: bool = False) -> dict:
        path = self._codex_path()
        if not path.is_file():
            return {"target": "codex", "path": str(path), "action": "not_found"}
        existing = path.read_text(encoding="utf-8")
        content, removed = self._remove_toml_table(existing, "mcp_servers.alcove")
        if not removed:
            return {"target": "codex", "path": str(path), "action": "not_found"}
        if not dry_run:
            path.write_text(content, encoding="utf-8")
        return {"target": "codex", "path": str(path), "action": "removed"}

    def _remove_claude(self, dry_run: bool = False) -> dict:
        records = [
            self._remove_claude_json(self._claude_path(), dry_run=dry_run, config_kind="legacy"),
            self._remove_claude_json(
                self._claude_settings_path(),
                dry_run=dry_run,
                config_kind="settings",
            ),
        ]
        actions = {record["action"] for record in records}
        if actions == {"not_found"}:
            action = "not_found"
        elif "removed" in actions:
            action = "removed"
        else:
            action = "unchanged"
        return {
            "target": "claude",
            "path": str(self._claude_path()),
            "settings_path": str(self._claude_settings_path()),
            "action": action,
            "configs": records,
        }

    def _remove_claude_json(
        self,
        path: Path,
        *,
        dry_run: bool = False,
        config_kind: str,
    ) -> dict:
        data = self._read_json(path)
        servers = data.get("mcpServers")
        if not isinstance(servers, dict) or "alcove" not in servers:
            return {
                "target": "claude",
                "path": str(path),
                "action": "not_found",
                "kind": config_kind,
            }
        next_data = {
            **data,
            "mcpServers": {k: v for k, v in servers.items() if k != "alcove"},
        }
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(next_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return {"target": "claude", "path": str(path), "action": "removed", "kind": config_kind}

    def _codex_path(self) -> Path:
        return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"

    def _claude_path(self) -> Path:
        return Path.home() / ".claude.json"

    def _claude_settings_path(self) -> Path:
        return Path.home() / ".claude" / "settings.json"

    def _read_json(self, path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _codex_block(self) -> str:
        args = ", ".join(json.dumps(arg) for arg in self._mcp_config()["args"])
        return f'[mcp_servers.alcove]\ncommand = "alcove"\nargs = [{args}]\n'

    def _upsert_toml_table(self, existing: str, header: str, block: str) -> str:
        lines = existing.splitlines()
        start = None
        end = len(lines)
        table_prefix = f"[{header}]"
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == table_prefix:
                start = index
                continue
            if start is not None and index > start and stripped.startswith("["):
                end = index
                break
        block_lines = block.rstrip().splitlines()
        if start is None:
            next_lines = [*lines]
            if next_lines and next_lines[-1].strip():
                next_lines.append("")
            next_lines.extend(block_lines)
        else:
            next_lines = [*lines[:start], *block_lines, *lines[end:]]
        return "\n".join(next_lines).rstrip() + "\n"

    def _extract_toml_table(self, existing: str, header: str) -> str:
        lines = existing.splitlines()
        start, end = self._toml_table_bounds(lines, header)
        if start is None:
            return ""
        return "\n".join(lines[start:end]).rstrip() + "\n"

    def _remove_toml_table(self, existing: str, header: str) -> tuple[str, bool]:
        lines = existing.splitlines()
        start, end = self._toml_table_bounds(lines, header)
        if start is None:
            return existing, False
        next_lines = [*lines[:start], *lines[end:]]
        while next_lines and not next_lines[-1].strip():
            next_lines.pop()
        return ("\n".join(next_lines).rstrip() + "\n") if next_lines else "", True

    def _toml_table_bounds(
        self,
        lines: list[str],
        header: str,
    ) -> tuple[int | None, int]:
        start = None
        end = len(lines)
        table_prefix = f"[{header}]"
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped == table_prefix:
                start = index
                continue
            if start is not None and index > start and stripped.startswith("["):
                end = index
                break
        return start, end
