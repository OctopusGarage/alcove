from __future__ import annotations

import json

from alcove.home import AlcoveHome
from alcove.installer import InstallerModule
from alcove.workspace import Workspace


def test_installer_writes_codex_mcp_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = Workspace.init(tmp_path / "workspace")
    alcove_home = AlcoveHome.init(tmp_path / "alcove-home")

    result = InstallerModule(workspace, home=alcove_home).install(["codex"])

    config = home / ".codex" / "config.toml"
    assert result["files"][0]["action"] == "created"
    assert config.is_file()
    assert "[mcp_servers.alcove]" in config.read_text(encoding="utf-8")
    assert 'command = "alcove"' in config.read_text(encoding="utf-8")
    assert str(workspace.root) in config.read_text(encoding="utf-8")
    assert str(alcove_home.root) in config.read_text(encoding="utf-8")


def test_installer_persists_home_scoped_args_with_tilde(tmp_path, monkeypatch):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    workspace = Workspace.init(user_home / "projects" / "workspace")
    alcove_home = AlcoveHome.init(user_home / ".alcove")

    result = InstallerModule(workspace, home=alcove_home).install(["codex", "claude"])

    codex_config = (user_home / ".codex" / "config.toml").read_text(encoding="utf-8")
    claude_config = json.loads((user_home / ".claude.json").read_text(encoding="utf-8"))
    claude_settings = json.loads(
        (user_home / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    assert result["home"] == "~/.alcove"
    assert result["workspace"] == "~/projects/workspace"
    assert '"~/.alcove"' in codex_config
    assert '"~/projects/workspace"' in codex_config
    assert str(user_home) not in codex_config
    expected_args = [
        "serve",
        "--mcp",
        "--toolset",
        "full",
        "--home",
        "~/.alcove",
        "--workspace",
        "~/projects/workspace",
    ]
    assert claude_config["mcpServers"]["alcove"]["args"] == expected_args
    assert claude_settings["mcpServers"]["alcove"]["args"] == expected_args


def test_installer_prefers_registered_kb_name_over_workspace_path(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = Workspace.init(tmp_path / "workspace")
    alcove_home = AlcoveHome.init(tmp_path / "alcove-home")
    alcove_home.register_knowledge_base("research_notes", workspace.root)

    InstallerModule(workspace, home=alcove_home).install(["codex"])

    config_text = (home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert '"--kb"' in config_text
    assert '"research_notes"' in config_text
    assert '"--workspace"' not in config_text


def test_installer_updates_claude_mcp_config_preserving_other_servers(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    claude_config = home / ".claude.json"
    claude_settings = home / ".claude" / "settings.json"
    claude_config.parent.mkdir(parents=True)
    claude_config.write_text(
        json.dumps({"mcpServers": {"other": {"command": "other"}}}),
        encoding="utf-8",
    )
    claude_settings.parent.mkdir(parents=True)
    claude_settings.write_text(
        json.dumps({"mcpServers": {"settings-other": {"command": "settings-other"}}}),
        encoding="utf-8",
    )
    workspace = Workspace.init(tmp_path / "workspace")
    alcove_home = AlcoveHome.init(tmp_path / "alcove-home")

    result = InstallerModule(workspace, home=alcove_home).install(["claude"])

    payload = json.loads(claude_config.read_text(encoding="utf-8"))
    settings_payload = json.loads(claude_settings.read_text(encoding="utf-8"))
    assert result["files"][0]["action"] == "updated"
    assert result["files"][1]["action"] == "updated"
    assert payload["mcpServers"]["other"] == {"command": "other"}
    assert settings_payload["mcpServers"]["settings-other"] == {"command": "settings-other"}
    assert payload["mcpServers"]["alcove"] == {
        "command": "alcove",
        "args": [
            "serve",
            "--mcp",
            "--toolset",
            "full",
            "--home",
            str(alcove_home.root),
            "--workspace",
            str(workspace.root),
        ],
    }
    assert settings_payload["mcpServers"]["alcove"] == payload["mcpServers"]["alcove"]


def test_installer_creates_claude_config_parent_directory(tmp_path, monkeypatch):
    home = tmp_path / "missing-home"
    monkeypatch.setenv("HOME", str(home))
    workspace = Workspace.init(tmp_path / "workspace")
    alcove_home = AlcoveHome.init(tmp_path / "alcove-home")

    result = InstallerModule(workspace, home=alcove_home).install(["claude"])

    claude_config = home / ".claude.json"
    claude_settings = home / ".claude" / "settings.json"
    assert result["files"][0]["action"] == "created"
    assert result["files"][1]["action"] == "created"
    assert claude_config.is_file()
    assert claude_settings.is_file()


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
    assert not (home / ".claude" / "settings.json").exists()


def test_installer_status_reports_installed_workspace_match(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = Workspace.init(tmp_path / "workspace")
    installer = InstallerModule(workspace)
    installer.install(["codex", "claude"])

    result = installer.status(["all"])

    assert result["workspace"] == str(workspace.root)
    assert {item["target"] for item in result["files"]} == {"codex", "claude"}
    assert all(item["installed"] for item in result["files"])
    assert all(item["workspace_match"] for item in result["files"])


def test_installer_uninstall_removes_only_alcove_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    codex_config = home / ".codex" / "config.toml"
    codex_config.parent.mkdir(parents=True)
    codex_config.write_text(
        '[mcp_servers.other]\ncommand = "other"\n\n'
        '[mcp_servers.alcove]\ncommand = "alcove"\nargs = ["serve"]\n',
        encoding="utf-8",
    )
    claude_config = home / ".claude.json"
    claude_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "other": {"command": "other"},
                    "alcove": {"command": "alcove", "args": ["serve"]},
                }
            }
        ),
        encoding="utf-8",
    )
    claude_settings = home / ".claude" / "settings.json"
    claude_settings.parent.mkdir(parents=True)
    claude_settings.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "settings-other": {"command": "settings-other"},
                    "alcove": {"command": "alcove", "args": ["serve"]},
                }
            }
        ),
        encoding="utf-8",
    )
    workspace = Workspace.init(tmp_path / "workspace")

    result = InstallerModule(workspace).uninstall(["all"])

    assert {item["action"] for item in result["files"]} == {"removed"}
    assert "[mcp_servers.other]" in codex_config.read_text(encoding="utf-8")
    assert "[mcp_servers.alcove]" not in codex_config.read_text(encoding="utf-8")
    payload = json.loads(claude_config.read_text(encoding="utf-8"))
    settings_payload = json.loads(claude_settings.read_text(encoding="utf-8"))
    assert payload["mcpServers"] == {"other": {"command": "other"}}
    assert settings_payload["mcpServers"] == {"settings-other": {"command": "settings-other"}}


def test_installer_uninstall_dry_run_does_not_write_files(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    workspace = Workspace.init(tmp_path / "workspace")
    installer = InstallerModule(workspace)
    installer.install(["codex"])
    config = home / ".codex" / "config.toml"
    before = config.read_text(encoding="utf-8")

    result = installer.uninstall(["codex"], dry_run=True)

    assert result["files"][0]["action"] == "removed"
    assert config.read_text(encoding="utf-8") == before
