from __future__ import annotations

import json

from alcove.cli import main
from alcove.profile_packs import ProfileInstallationPack
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


def test_profile_installation_pack_owns_entry_skill_and_agent_artifacts(tmp_path):
    root = tmp_path / "research_notes"
    pack = ProfileInstallationPack(profile="managed-kb", skill_name="alcove-kb")

    entry = pack.entry_section(home="~/.alcove", default_kb="research_notes", home_part="")
    skill = pack.skill_content(default_kb="research_notes", home_part="")
    codex = pack.codex_artifacts(root, default_kb="research_notes")
    claude = pack.claude_artifacts(root, default_kb="research_notes")

    assert "Alcove Managed KB Entry" in entry
    assert "Alcove Managed KB" in skill
    assert "本地个人知识库" in entry
    assert "Search returns candidate records" in entry
    assert "AI-led OKF/local-file investigation" in entry
    assert "CLI/MCP mutation commands" in entry
    assert "Use unrelated tools only when explicitly named" in entry
    assert "本地个人知识库" in skill
    assert "Alcove MCP/CLI search as candidate discovery" in skill
    assert "Home-wide search" in skill
    assert "Search results are leads, not final truth" in skill
    assert "AI-led investigation" in skill
    assert "Direct file edits are repair fallbacks only" in skill
    assert "unrelated global or project-specific tools" in skill
    assert {artifact.path for artifact in codex} >= {
        root / ".agents" / "skills" / "notes-search" / "SKILL.md",
        root / ".agents" / "skills" / "alcove-capture" / "SKILL.md",
    }
    notes_search = next(
        artifact.content
        for artifact in codex
        if artifact.path == root / ".agents" / "skills" / "notes-search" / "SKILL.md"
    )
    assert "Use Alcove MCP/CLI search for candidate discovery" in notes_search
    assert "本地个人知识库" in notes_search
    assert "Home-wide search" in notes_search
    assert "Omit `workspace`" in notes_search
    assert "Treat search results as leads, not final truth" in notes_search
    assert "This skill is read-only. Do not mutate files" in notes_search
    generated_text = "\n".join([entry, skill, notes_search])
    forbidden_terms = [
        "\u60a6\u6570",
        "ysin" + "sight",
        "Y" + "S/" + "\u60a6\u6570",
    ]
    assert all(term not in generated_text for term in forbidden_terms)
    assert {artifact.path for artifact in claude} >= {
        root / ".claude" / "commands" / "inbox-peek.md",
        root / ".claude" / "commands" / "into-kb.md",
    }


def test_profile_source_templates_match_default_generated_artifacts(tmp_path):
    root = tmp_path / "research_notes"
    hub_pack = ProfileInstallationPack(profile="hub", skill_name="alcove-hub")
    kb_pack = ProfileInstallationPack(profile="managed-kb", skill_name="alcove-kb")

    hub_source = hub_pack.skill_source_path()
    kb_source = kb_pack.skill_source_path()
    assert hub_source is not None
    assert kb_source is not None
    assert hub_source.read_text(encoding="utf-8") == hub_pack.skill_content(
        default_kb="research_notes", home_part=""
    )
    assert kb_source.read_text(encoding="utf-8") == kb_pack.skill_content(
        default_kb="research_notes", home_part=""
    )
    for artifact in kb_pack.codex_artifacts(root, default_kb="research_notes"):
        assert artifact.source_path is not None
        assert artifact.source_path.read_text(encoding="utf-8") == artifact.content
    for artifact in kb_pack.claude_artifacts(root, default_kb="research_notes"):
        assert artifact.source_path is not None
        assert artifact.source_path.read_text(encoding="utf-8") == artifact.content


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
            "research_notes",
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
    assert not (hub / ".agents" / "skills" / "alcove-hub" / "SKILL.md").is_symlink()
    claude_entry = (hub / "CLAUDE.md").read_text(encoding="utf-8")
    assert "alcove kb" in claude_entry
    assert "--kb <kb-name>" in claude_entry
    assert "If that skill is unavailable" in claude_entry
    assert "Check monitored blogs now" in claude_entry
    assert "alcove blog" in claude_entry
    assert "Run an information radar" in claude_entry
    assert "alcove radar" in claude_entry
    assert "Radar IDs are user data" in claude_entry
    hub_skill = (hub / ".agents" / "skills" / "alcove-hub" / "SKILL.md").read_text(encoding="utf-8")
    assert "Intent Routing" in hub_skill
    assert "ambiguous record" in hub_skill
    assert "alcove project" in hub_skill
    assert "alcove prompt" in hub_skill
    assert "alcove mount" in hub_skill
    assert "alcove connector" in hub_skill
    assert "alcove export" in hub_skill
    assert "Retrieval Model" in hub_skill
    assert "Fallback Routing Without Skills" in hub_skill
    assert "Broad personal knowledge question" in hub_skill
    assert "Governed write path" in hub_skill
    assert "Treat search results as leads, not final truth" in hub_skill
    assert "AI-led investigation" in hub_skill
    assert "Durable writes should go through Alcove CLI/MCP commands" in hub_skill
    assert "常用收藏" in hub_skill
    assert "update that existing collection pin" in hub_skill
    assert "do not save only the bare URL" in hub_skill
    assert "Verify through the user's intended entry point" in hub_skill
    assert "Save Completion Response" in hub_skill
    assert "`source_refs` are internal OKF/source references" in hub_skill
    assert "blog monitor" in hub_skill
    assert "alcove blog" in hub_skill
    assert "check --json" in hub_skill
    assert "Use `alcove blog check`, not `alcove service tick`" in hub_skill
    assert "information radar" in hub_skill
    assert "Radar Protocol" in hub_skill
    assert "alcove radar" in hub_skill
    assert "radar IDs are user data" in hub_skill
    assert "fetch and score deterministically first" in hub_skill
    assert "--skip-fetch --force --ai --notify" in hub_skill
    assert "Optional `ai_summary` is post-report analysis only" in hub_skill
    assert "Project Development Protocol" in hub_skill
    assert "entry-mode impact check" in hub_skill
    assert "project/worktree" in hub_skill
    assert "Do not save the" in hub_skill
    assert "request as a knowledge note" in hub_skill
    assert "prompt-quality reviewer yourself" in hub_skill
    assert "Do not treat the user wording as already" in hub_skill
    assert "rewrite the candidate into a concise copy-ready prompt body" in hub_skill
    assert "prefer updating/merging it instead of creating a new prompt" in hub_skill
    assert "--ai-eval-provider codex" in hub_skill
    assert "current agent's" in hub_skill
    assert "proposal's built-in eval" in hub_skill
    assert "evaluation.prompt_ai_eval.rounds" in hub_skill
    assert "professional_quality" in hub_skill
    assert "adversarial_reuse" in hub_skill
    assert "Article summaries, one-off project notes, and raw chat dumps" in hub_skill


def test_cli_hub_init_can_link_project_skills_in_development_mode(
    tmp_path,
    monkeypatch,
    capsys,
):
    home = tmp_path / ".alcove"
    hub = tmp_path / "AlcoveHub"
    monkeypatch.setenv("ALCOVE_HOME", str(home))

    code = main(
        [
            "hub",
            "init",
            str(hub),
            "--default-kb",
            "research_notes",
            "--target",
            "codex",
            "--link",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    skill_path = hub / ".agents" / "skills" / "alcove-hub" / "SKILL.md"
    source_path = ProfileInstallationPack(
        profile="hub", skill_name="alcove-hub"
    ).skill_source_path()
    assert code == 0
    assert payload["mode"] == "link"
    assert skill_path.is_symlink()
    assert source_path is not None
    assert skill_path.resolve() == source_path.resolve()
    assert skill_path.read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8")
    assert not (hub / "AGENTS.md").is_symlink()


def test_cli_kb_install_can_link_skills_and_claude_commands_in_development_mode(
    tmp_path,
    monkeypatch,
    capsys,
):
    home = tmp_path / ".alcove"
    kb_root = tmp_path / "research_notes"
    monkeypatch.setenv("ALCOVE_HOME", str(home))
    Workspace.init(kb_root)
    main(["kb", "add", "research_notes", str(kb_root), "--json"])
    capsys.readouterr()

    code = main(
        [
            "kb",
            "install",
            "research_notes",
            "--target",
            "codex",
            "--target",
            "claude",
            "--link",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    linked_paths = [
        kb_root / ".agents" / "skills" / "alcove-kb" / "SKILL.md",
        kb_root / ".agents" / "skills" / "notes-search" / "SKILL.md",
        kb_root / ".agents" / "skills" / "alcove-capture" / "SKILL.md",
        kb_root / ".claude" / "commands" / "inbox-peek.md",
        kb_root / ".claude" / "commands" / "into-kb.md",
    ]
    assert code == 0
    assert payload["mode"] == "link"
    assert all(path.is_symlink() for path in linked_paths)
    assert not (kb_root / "AGENTS.md").is_symlink()
    assert not (kb_root / "CLAUDE.md").is_symlink()

    code = main(["kb", "install", "research_notes", "--status", "--json"])
    status_output = capsys.readouterr()
    status = json.loads(status_output.out)
    assert code == 0
    linked_records = [item for item in status["files"] if item["kind"] in {"skill", "artifact"}]
    assert any(item["is_symlink"] and item.get("source_match") for item in linked_records)


def test_cli_kb_copy_install_replaces_previous_linked_skills_and_commands(
    tmp_path,
    monkeypatch,
    capsys,
):
    home = tmp_path / ".alcove"
    kb_root = tmp_path / "research_notes"
    monkeypatch.setenv("ALCOVE_HOME", str(home))
    Workspace.init(kb_root)
    main(["kb", "add", "research_notes", str(kb_root), "--json"])
    capsys.readouterr()

    link_code = main(["kb", "install", "research_notes", "--link", "--json"])
    capsys.readouterr()
    assert link_code == 0

    copy_code = main(["kb", "install", "research_notes", "--json"])
    output = capsys.readouterr()

    payload = json.loads(output.out)
    copied_paths = [
        kb_root / ".agents" / "skills" / "alcove-kb" / "SKILL.md",
        kb_root / ".agents" / "skills" / "notes-search" / "SKILL.md",
        kb_root / ".agents" / "skills" / "alcove-capture" / "SKILL.md",
        kb_root / ".claude" / "skills" / "alcove-kb" / "SKILL.md",
        kb_root / ".claude" / "commands" / "inbox-peek.md",
        kb_root / ".claude" / "commands" / "into-kb.md",
    ]
    assert copy_code == 0
    assert payload["mode"] == "copy"
    assert all(path.is_file() for path in copied_paths)
    assert not any(path.is_symlink() for path in copied_paths)


def test_cli_linked_profile_install_rejects_explicit_non_default_home(
    tmp_path,
    capsys,
):
    home = tmp_path / "custom-home"
    hub = tmp_path / "AlcoveHub"

    code = main(
        [
            "hub",
            "init",
            str(hub),
            "--home",
            str(home),
            "--link",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 2
    assert "requires the default Alcove Home" in output.out


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
            "research_notes",
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
    assert [file["target"] for file in payload["files"]] == ["codex"]
    config = user_home / ".codex" / "config.toml"
    config_text = config.read_text(encoding="utf-8")
    assert payload["profile"] == "global-lite"
    assert payload["toolset"] == "lite"
    assert '"--toolset"' in config_text
    assert '"lite"' in config_text
    assert '"--home"' in config_text
    assert str(alcove_home.resolve()) in config_text
    assert '"--workspace"' not in config_text
    assert '"--kb"' not in config_text
    assert not (user_home / ".codex" / "skills").exists()


def test_cli_global_install_can_bind_default_kb_for_lite_mcp(
    tmp_path,
    monkeypatch,
    capsys,
):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    alcove_home = tmp_path / "alcove-home"
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    main(["kb", "--home", str(alcove_home), "add", "research_notes", str(kb_root), "--json"])
    capsys.readouterr()

    code = main(
        [
            "global",
            "install",
            "--home",
            str(alcove_home),
            "--default-kb",
            "research_notes",
            "--target",
            "codex",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    payload = json.loads(output.out)
    config_text = (user_home / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert payload["profile"] == "global-lite"
    assert payload["toolset"] == "lite"
    assert payload["kb"] == "research_notes"
    assert '"--kb"' in config_text
    assert '"research_notes"' in config_text


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
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    main(
        [
            "kb",
            "--home",
            str(home),
            "add",
            "research_notes",
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
            "research_notes",
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
    assert payload["kb"] == "research_notes"
    assert (kb_root / "CLAUDE.md").is_file()
    assert (kb_root / "AGENTS.md").is_file()
    assert (kb_root / ".claude" / "skills" / "alcove-kb" / "SKILL.md").is_file()
    assert (kb_root / ".agents" / "skills" / "alcove-kb" / "SKILL.md").is_file()
    assert "--kb research_notes" not in (kb_root / "CLAUDE.md").read_text(encoding="utf-8")


def test_cli_kb_install_restores_full_managed_kb_workflow_wrappers(
    tmp_path,
    capsys,
):
    home = tmp_path / "alcove-home"
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    main(
        [
            "kb",
            "--home",
            str(home),
            "add",
            "research_notes",
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
            "research_notes",
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
    assert (kb_root / ".claude" / "skills" / "alcove-capture" / "SKILL.md").is_file()
    assert (kb_root / ".agents" / "skills" / "notes-search" / "SKILL.md").is_file()
    assert (kb_root / ".agents" / "skills" / "alcove-capture" / "SKILL.md").is_file()
    assert not (kb_root / ".claude" / "skills" / "alcove-capture" / "scripts").exists()
    assert str(kb_root / ".claude" / "commands" / "inbox-peek.md") in installed_paths
    assert str(kb_root / ".agents" / "skills" / "alcove-capture" / "SKILL.md") in installed_paths

    claude_doc = (kb_root / "CLAUDE.md").read_text(encoding="utf-8")
    agents_doc = (kb_root / "AGENTS.md").read_text(encoding="utf-8")
    manager_skill = (kb_root / ".claude" / "skills" / "alcove-capture" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    inbox_peek_command = (kb_root / ".claude" / "commands" / "inbox-peek.md").read_text(
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
    assert "If a listed project skill is unavailable" in claude_doc
    assert "Global data outside this repo: pins, prompts, projects, tasks" in claude_doc
    assert "Search returns candidate records" in claude_doc
    assert "AI-led OKF/local-file investigation" in claude_doc
    assert "CLI/MCP mutation commands" in claude_doc
    assert "当前知识库" in claude_doc
    assert "Clipsmith Capture Pipeline" not in claude_doc
    assert "clipsmith validate-bundle" not in claude_doc
    assert "alcove inbox" in agents_doc
    assert "peek --json" in agents_doc
    assert "--kb research_notes" not in agents_doc
    assert "alcove inbox note" in manager_skill
    assert "clipsmith sink inbox" in manager_skill
    assert "Do not save article summaries as prompts" in manager_skill
    assert "alcove inbox read <identifier> --full --json" in inbox_peek_command
    assert "truncated, OCR-heavy, or too thin" in inbox_peek_command
    assert 'alcove search "query"' in notes_skill
    assert "candidate discovery" in notes_skill
    assert "Investigation Model" in notes_skill


def test_cli_kb_install_writes_user_paths_with_tilde(tmp_path, monkeypatch, capsys):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    home = user_home / ".alcove"
    kb_root = user_home / "projects" / "research_notes"
    Workspace.init(kb_root)
    main(
        [
            "kb",
            "--home",
            str(home),
            "add",
            "research_notes",
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
            "research_notes",
            "--target",
            "codex",
            "--json",
        ]
    )
    capsys.readouterr()

    agents_doc = (kb_root / "AGENTS.md").read_text(encoding="utf-8")
    manager_skill = (kb_root / ".agents" / "skills" / "alcove-capture" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert code == 0
    assert "- Home: configured Alcove Home" in agents_doc
    assert 'clipsmith sink inbox "<bundle_dir>" . --json' in manager_skill
    assert str(user_home) not in agents_doc
    assert str(user_home) not in manager_skill


def test_cli_kb_install_removes_blank_prefix_before_existing_entry_section(
    tmp_path,
    capsys,
):
    home = tmp_path / "alcove-home"
    kb_root = tmp_path / "research_notes"
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
            "research_notes",
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
            "research_notes",
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
