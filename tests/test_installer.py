from __future__ import annotations

import json

from alcove.installer import InstallerModule
from alcove.workspace import Workspace


def test_installer_writes_codex_mcp_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = Workspace.init(tmp_path / "workspace")

    result = InstallerModule(workspace).install(["codex"])

    config = home / ".codex" / "config.toml"
    assert result["files"][0]["action"] == "created"
    assert config.is_file()
    assert "[mcp_servers.alcove]" in config.read_text(encoding="utf-8")
    assert 'command = "alcove"' in config.read_text(encoding="utf-8")
    assert str(workspace.root) in config.read_text(encoding="utf-8")


def test_installer_updates_claude_mcp_config_preserving_other_servers(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    claude_config = home / ".claude.json"
    claude_config.parent.mkdir(parents=True)
    claude_config.write_text(
        json.dumps({"mcpServers": {"other": {"command": "other"}}}),
        encoding="utf-8",
    )
    workspace = Workspace.init(tmp_path / "workspace")

    result = InstallerModule(workspace).install(["claude"])

    payload = json.loads(claude_config.read_text(encoding="utf-8"))
    assert result["files"][0]["action"] == "updated"
    assert payload["mcpServers"]["other"] == {"command": "other"}
    assert payload["mcpServers"]["alcove"] == {
        "command": "alcove",
        "args": ["serve", "--mcp", "--workspace", str(workspace.root)],
    }


def test_installer_print_config_does_not_write_files(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = Workspace.init(tmp_path / "workspace")

    result = InstallerModule(workspace).install(["codex", "claude"], dry_run=True)

    assert result["files"] == []
    assert "mcp_servers.alcove" in result["configs"]["codex"]
    assert '"alcove"' in result["configs"]["claude"]
    assert not (home / ".codex" / "config.toml").exists()
    assert not (home / ".claude.json").exists()
