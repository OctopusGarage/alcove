from __future__ import annotations

import json

from alcove.cli import main
from alcove.workspace import Workspace


def test_cli_home_init_creates_alcove_home(tmp_path, capsys):
    home = tmp_path / "alcove-home"

    code = main(["home", "init", "--home", str(home), "--json"])
    output = capsys.readouterr()

    assert code == 0
    payload = json.loads(output.out)
    assert payload["home"] == str(home.resolve())
    assert (home / "config.yml").is_file()
    assert (home / "knowledge-bases").is_dir()
    assert (home / "pins").is_dir()
    assert (home / "tasks").is_dir()


def test_cli_hub_init_creates_project_local_entry_files(tmp_path, capsys):
    home = tmp_path / "alcove-home"
    hub = tmp_path / "AlcoveHub"

    code = main(
        [
            "hub",
            "init",
            str(hub),
            "--home",
            str(home),
            "--default-kb",
            "social_media_posts",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    payload = json.loads(output.out)
    assert payload["profile"] == "hub"
    assert (hub / ".alcove-hub.yml").is_file()
    assert (hub / "CLAUDE.md").is_file()
    assert (hub / "AGENTS.md").is_file()
    assert (hub / ".claude" / "skills" / "alcove-hub" / "SKILL.md").is_file()
    assert (hub / ".agents" / "skills" / "alcove-hub" / "SKILL.md").is_file()
    assert "social_media_posts" in (hub / "CLAUDE.md").read_text(encoding="utf-8")


def test_cli_hub_init_non_json_uses_default_home_and_prints_install_paths(
    tmp_path,
    monkeypatch,
    capsys,
):
    home = tmp_path / "default-home"
    hub = tmp_path / "AlcoveHub"
    monkeypatch.setenv("ALCOVE_HOME", str(home))

    code = main(
        [
            "hub",
            "init",
            str(hub),
            "--default-kb",
            "social_media_posts",
            "--target",
            "codex",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    assert "profile: hub" in output.out
    assert f"home: {home.resolve()}" in output.out
    assert f"path: {hub.resolve()}" in output.out
    assert str(hub / "AGENTS.md") in output.out


def test_cli_global_install_writes_lite_mcp_without_kb_or_workspace(
    tmp_path,
    monkeypatch,
    capsys,
):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    alcove_home = tmp_path / "alcove-home"

    code = main(
        [
            "global",
            "install",
            "--home",
            str(alcove_home),
            "--target",
            "codex",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    payload = json.loads(output.out)
    config = user_home / ".codex" / "config.toml"
    config_text = config.read_text(encoding="utf-8")
    assert payload["profile"] == "global-lite"
    assert '"--home"' in config_text
    assert str(alcove_home.resolve()) in config_text
    assert '"--workspace"' not in config_text
    assert '"--kb"' not in config_text


def test_cli_global_install_non_json_uses_default_home_and_prints_config_path(
    tmp_path,
    monkeypatch,
    capsys,
):
    user_home = tmp_path / "user-home"
    alcove_home = tmp_path / "default-alcove-home"
    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setenv("ALCOVE_HOME", str(alcove_home))

    code = main(["global", "install", "--target", "codex"])
    output = capsys.readouterr()

    assert code == 0
    assert "profile: global-lite" in output.out
    assert f"home: {alcove_home.resolve()}" in output.out
    assert str(user_home / ".codex" / "config.toml") in output.out


def test_cli_kb_install_uses_registry_and_writes_kb_local_entry_files(
    tmp_path,
    capsys,
):
    home = tmp_path / "alcove-home"
    kb_root = tmp_path / "social_media_posts"
    Workspace.init(kb_root)
    main(
        [
            "kb",
            "--home",
            str(home),
            "add",
            "social_media_posts",
            str(kb_root),
            "--json",
        ]
    )
    capsys.readouterr()

    code = main(
        [
            "kb",
            "--home",
            str(home),
            "install",
            "social_media_posts",
            "--target",
            "codex",
            "--target",
            "claude",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    payload = json.loads(output.out)
    assert payload["profile"] == "managed-kb"
    assert payload["kb"] == "social_media_posts"
    assert (kb_root / "CLAUDE.md").is_file()
    assert (kb_root / "AGENTS.md").is_file()
    assert (kb_root / ".claude" / "skills" / "alcove-kb" / "SKILL.md").is_file()
    assert (kb_root / ".agents" / "skills" / "alcove-kb" / "SKILL.md").is_file()
    assert "--kb social_media_posts" in (kb_root / "CLAUDE.md").read_text(encoding="utf-8")


def test_cli_kb_install_restores_full_managed_kb_workflow_wrappers(
    tmp_path,
    capsys,
):
    home = tmp_path / "alcove-home"
    kb_root = tmp_path / "social_media_posts"
    Workspace.init(kb_root)
    main(
        [
            "kb",
            "--home",
            str(home),
            "add",
            "social_media_posts",
            str(kb_root),
            "--json",
        ]
    )
    capsys.readouterr()

    code = main(
        [
            "kb",
            "--home",
            str(home),
            "install",
            "social_media_posts",
            "--target",
            "codex",
            "--target",
            "claude",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    installed_paths = {item["path"] for item in payload["files"]}
    assert code == 0
    assert (kb_root / ".claude" / "commands" / "inbox-peek.md").is_file()
    assert (kb_root / ".claude" / "commands" / "into-kb.md").is_file()
    assert (kb_root / ".claude" / "skills" / "notes-search" / "SKILL.md").is_file()
    assert (kb_root / ".claude" / "skills" / "social_post_manager" / "SKILL.md").is_file()
    assert (kb_root / ".agents" / "skills" / "notes-search" / "SKILL.md").is_file()
    assert (kb_root / ".agents" / "skills" / "social_post_manager" / "SKILL.md").is_file()
    assert not (kb_root / ".claude" / "skills" / "social_post_manager" / "scripts").exists()
    assert str(kb_root / ".claude" / "commands" / "inbox-peek.md") in installed_paths
    assert (
        str(kb_root / ".agents" / "skills" / "social_post_manager" / "SKILL.md") in installed_paths
    )

    claude_doc = (kb_root / "CLAUDE.md").read_text(encoding="utf-8")
    agents_doc = (kb_root / "AGENTS.md").read_text(encoding="utf-8")
    manager_skill = (kb_root / ".claude" / "skills" / "social_post_manager" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    notes_skill = (kb_root / ".agents" / "skills" / "notes-search" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert len(claude_doc.splitlines()) < 35
    assert claude_doc.startswith("<!-- ALCOVE ENTRY START -->")
    assert agents_doc.startswith("<!-- ALCOVE ENTRY START -->")
    assert "Skills and commands hold the detailed workflows" in claude_doc
    assert "Inbox posts require explicit per-post confirmation" in claude_doc
    assert "Clipsmith Capture Pipeline" not in claude_doc
    assert "clipsmith validate-bundle" not in claude_doc
    assert "--kb social_media_posts peek" in agents_doc
    assert "alcove inbox --kb social_media_posts note" in manager_skill
    assert "clipsmith sink alcove-inbox" in manager_skill
    assert "alcove search --kb social_media_posts" in notes_skill


def test_cli_kb_install_removes_blank_prefix_before_existing_entry_section(
    tmp_path,
    capsys,
):
    home = tmp_path / "alcove-home"
    kb_root = tmp_path / "social_media_posts"
    Workspace.init(kb_root)
    (kb_root / "CLAUDE.md").write_text(
        "\n\n<!-- ALCOVE ENTRY START -->\nstale\n<!-- ALCOVE ENTRY END -->\n",
        encoding="utf-8",
    )
    (kb_root / "AGENTS.md").write_text(
        "\n\n<!-- ALCOVE ENTRY START -->\nstale\n<!-- ALCOVE ENTRY END -->\n",
        encoding="utf-8",
    )
    main(
        [
            "kb",
            "--home",
            str(home),
            "add",
            "social_media_posts",
            str(kb_root),
            "--json",
        ]
    )
    capsys.readouterr()

    code = main(
        [
            "kb",
            "--home",
            str(home),
            "install",
            "social_media_posts",
            "--target",
            "codex",
            "--target",
            "claude",
            "--json",
        ]
    )
    capsys.readouterr()

    assert code == 0
    assert (
        (kb_root / "CLAUDE.md")
        .read_text(encoding="utf-8")
        .startswith("<!-- ALCOVE ENTRY START -->")
    )
    assert (
        (kb_root / "AGENTS.md")
        .read_text(encoding="utf-8")
        .startswith("<!-- ALCOVE ENTRY START -->")
    )
