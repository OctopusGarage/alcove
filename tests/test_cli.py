import json
from types import SimpleNamespace

from alcove import cli_serve
from alcove.cli import build_parser, main
from alcove.connector_sources import ConnectorSourceRegistry
from alcove.connectors.apple_notes import AppleNotesAutomationError, write_apple_notes_export_tree
from alcove.connectors.github_stars import GitHubStarsConnector
from alcove.home import AlcoveHome
from alcove.pins import AddPinRequest, PinsModule
from alcove.usage import UsageRecorder


def _write_post(root, platform, name, files):
    folder = root / "inbox" / platform / name
    folder.mkdir(parents=True)
    for filename, content in files.items():
        (folder / filename).write_text(content, encoding="utf-8")
    return folder


def _write_xhs_post(root, name="20260707-post"):
    return _write_post(
        root,
        "xhs",
        name,
        {
            "post.md": "# sparse\n\n#tag",
            "summary.md": ("# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要"),
        },
    )


def test_cli_version_prints_package_version(capsys):
    code = main(["--version"])
    captured = capsys.readouterr()

    assert code == 0
    assert "alcove 0.1.0" in captured.out


def test_cli_init_creates_workspace(tmp_path, capsys):
    code = main(["init", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 0
    assert "Initialized Alcove workspace" in captured.out
    assert (tmp_path / ".alcove" / "config.yml").is_file()


def test_cli_status_json_reports_workspace(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    code = main(["status", str(tmp_path), "--json"])
    captured = capsys.readouterr()

    assert code == 0
    data = json.loads(captured.out)
    assert data["initialized"] is True
    assert data["root"] == str(tmp_path.resolve())


def test_cli_doctor_json_reports_workspace_health(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    code = main(["doctor", "--workspace", str(tmp_path), "--json"])
    captured = capsys.readouterr()

    payload = json.loads(captured.out)
    assert code == 0
    assert payload["status"] == "ok"
    workspace_check = next(check for check in payload["checks"] if check["name"] == "workspace")
    assert workspace_check["component"] == "Workspace config"
    assert workspace_check["remediation"] == ""
    assert "debug_path" not in json.dumps(payload)


def test_cli_inbox_discovers_current_workspace(tmp_path, monkeypatch, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    _write_xhs_post(tmp_path)
    monkeypatch.chdir(tmp_path)

    code = main(["inbox", "peek", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["identifier"] == "xhs/20260707-post"


def test_cli_parser_accepts_serve_mcp_command(tmp_path):
    args = build_parser().parse_args(["serve", "--mcp", "--workspace", str(tmp_path)])

    assert args.command == "serve"
    assert args.mcp is True
    assert args.workspace == str(tmp_path)


def test_cli_parser_accepts_serve_dashboard_command(tmp_path):
    args = build_parser().parse_args(
        ["serve", "--dashboard", "--home", str(tmp_path), "--port", "8123"]
    )

    assert args.command == "serve"
    assert args.dashboard is True
    assert args.home == str(tmp_path)
    assert args.port == 8123


def test_cli_serve_dispatches_mcp(monkeypatch, tmp_path):
    calls = {}

    def fake_run_mcp_server(workspace, home, *, toolset):
        calls["mcp"] = {"workspace": workspace, "home": home, "toolset": toolset}

    monkeypatch.setattr(cli_serve, "run_mcp_server", fake_run_mcp_server)
    args = SimpleNamespace(mcp=True, dashboard=False, home=str(tmp_path / "home"), toolset="lite")

    code = cli_serve.handle_serve_command(
        args,
        build_parser(),
        workspace_from_args=lambda _args: SimpleNamespace(root=tmp_path),
        argument_error=lambda _parser, _message: 2,
    )

    assert code == 0
    assert calls["mcp"] == {
        "workspace": str(tmp_path),
        "home": str(tmp_path / "home"),
        "toolset": "lite",
    }


def test_cli_serve_dispatches_dashboard(monkeypatch, tmp_path):
    calls = {}

    def fake_serve_dashboard(home, *, host, port):
        calls["dashboard"] = {"home": home.root, "host": host, "port": port}

    monkeypatch.setattr(cli_serve, "serve_dashboard", fake_serve_dashboard)
    args = SimpleNamespace(
        mcp=False,
        dashboard=True,
        home=str(tmp_path / "home"),
        host="127.0.0.1",
        port=8123,
    )

    code = cli_serve.handle_serve_command(
        args,
        build_parser(),
        workspace_from_args=lambda _args: None,
        argument_error=lambda _parser, _message: 2,
    )

    assert code == 0
    assert calls["dashboard"] == {
        "home": tmp_path / "home",
        "host": "127.0.0.1",
        "port": 8123,
    }


def test_cli_serve_requires_mode():
    args = SimpleNamespace(mcp=False, dashboard=False)

    code = cli_serve.handle_serve_command(
        args,
        build_parser(),
        workspace_from_args=lambda _args: None,
        argument_error=lambda _parser, message: 64 if "requires" in message else 2,
    )

    assert code == 64


def test_cli_search_records_privacy_safe_usage(tmp_path, capsys):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(
        AddPinRequest(title="CLI Usage Needle", content="Searchable usage content.")
    )

    code = main(["search", "usage needle", "--home", str(home.root), "--json"])
    output = capsys.readouterr()
    summary = UsageRecorder(home).summary()
    events = (home.paths().logs / "usage.jsonl").read_text(encoding="utf-8")

    assert code == 0
    assert json.loads(output.out)[0]["title"] == "CLI Usage Needle"
    assert summary["search"]["surfaces"] == {"cli": 1}
    assert summary["search"]["zero_result"] == 0
    assert "usage needle" not in events


def test_cli_usage_summary_and_prune(tmp_path, capsys):
    home = AlcoveHome.init(tmp_path / "home")
    recorder = UsageRecorder(home)
    recorder.record_search(surface="cli", query="usage summary secret", result_count=0)
    (home.paths().logs / "activity.jsonl").write_text(
        json.dumps(
            {
                "updated_at": "2026-06-01T00:00:00+08:00",
                "area": "pin",
                "action": "pin.add",
                "summary": "Old pin",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary_code = main(["usage", "summary", "--home", str(home.root), "--json"])
    summary_output = capsys.readouterr()
    prune_code = main(
        [
            "usage",
            "prune",
            "--home",
            str(home.root),
            "--days",
            "14",
            "--now",
            "2026-07-10T12:00:00+08:00",
            "--json",
        ]
    )
    prune_output = capsys.readouterr()

    assert summary_code == 0
    summary = json.loads(summary_output.out)
    assert summary["search"]["total"] == 1
    assert "usage summary secret" not in summary_output.out
    assert prune_code == 0
    assert json.loads(prune_output.out)["activity_removed"] == 1


def test_cli_install_prints_mcp_config_without_writing(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main(["init", str(tmp_path)])
    capsys.readouterr()

    code = main(
        [
            "install",
            "--workspace",
            str(tmp_path),
            "--target",
            "codex",
            "--print",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    payload = json.loads(captured.out)
    assert code == 0
    assert payload["files"] == []
    assert "mcp_servers.alcove" in payload["configs"]["codex"]
    assert not (home / ".codex" / "config.toml").exists()


def test_cli_install_status_and_uninstall(tmp_path, monkeypatch, capsys):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    main(["init", str(tmp_path)])
    capsys.readouterr()

    install_code = main(
        [
            "install",
            "--workspace",
            str(tmp_path),
            "--target",
            "codex",
            "--json",
        ]
    )
    capsys.readouterr()
    status_code = main(
        [
            "install",
            "--workspace",
            str(tmp_path),
            "--target",
            "codex",
            "--status",
            "--json",
        ]
    )
    status_output = capsys.readouterr()
    uninstall_code = main(
        [
            "install",
            "--workspace",
            str(tmp_path),
            "--target",
            "codex",
            "--uninstall",
            "--json",
        ]
    )
    uninstall_output = capsys.readouterr()

    assert install_code == 0
    assert status_code == 0
    assert json.loads(status_output.out)["files"][0]["installed"] is True
    assert uninstall_code == 0
    assert json.loads(uninstall_output.out)["files"][0]["action"] == "removed"


def test_cli_hub_status_reports_profile_files_without_writing(tmp_path, capsys):
    home = tmp_path / "home"
    hub = tmp_path / "hub"

    before_code = main(
        [
            "hub",
            "init",
            str(hub),
            "--home",
            str(home),
            "--default-kb",
            "research_notes",
            "--target",
            "codex",
            "--status",
            "--json",
        ]
    )
    before_output = capsys.readouterr()
    before = json.loads(before_output.out)
    assert before_code == 0
    assert before["profile"] == "hub"
    assert before["exists"] is False
    assert all(file["installed"] is False for file in before["files"])
    assert all(file["workspace_match"] is False for file in before["files"])
    assert not hub.exists()

    init_code = main(
        [
            "hub",
            "init",
            str(hub),
            "--home",
            str(home),
            "--default-kb",
            "research_notes",
            "--target",
            "codex",
            "--json",
        ]
    )
    capsys.readouterr()
    after_code = main(
        [
            "hub",
            "install",
            str(hub),
            "--home",
            str(home),
            "--default-kb",
            "research_notes",
            "--target",
            "codex",
            "--status",
            "--json",
        ]
    )
    after_output = capsys.readouterr()

    assert init_code == 0

    after = json.loads(after_output.out)
    assert after_code == 0
    assert after["exists"] is True
    assert all(file["installed"] is True for file in after["files"])
    assert all(file["workspace_match"] is True for file in after["files"])


def test_cli_kb_install_status_reports_managed_kb_profile_files(tmp_path, capsys):
    home = tmp_path / "home"
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    main(["kb", "--home", str(home), "add", "research_notes", str(kb_root), "--json"])
    capsys.readouterr()

    before_code = main(
        [
            "kb",
            "--home",
            str(home),
            "install",
            "research_notes",
            "--target",
            "codex",
            "--status",
            "--json",
        ]
    )
    before_output = capsys.readouterr()
    install_code = main(
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
    after_code = main(
        [
            "kb",
            "--home",
            str(home),
            "install",
            "research_notes",
            "--target",
            "codex",
            "--status",
            "--json",
        ]
    )
    after_output = capsys.readouterr()

    before = json.loads(before_output.out)
    after = json.loads(after_output.out)
    assert before_code == 0
    assert before["profile"] == "managed-kb"
    assert before["exists"] is True
    assert all(file["installed"] is False for file in before["files"])
    assert install_code == 0
    assert after_code == 0
    assert after["kb"] == "research_notes"
    assert all(file["installed"] is True for file in after["files"])
    assert all(file["workspace_match"] is True for file in after["files"])


def test_cli_init_existing_file_returns_controlled_error(tmp_path, capsys):
    target = tmp_path / "not-a-directory"
    target.write_text("content")

    code = main(["init", str(target)])
    captured = capsys.readouterr()

    assert code == 2
    assert "alcove: Could not initialize" in captured.err


def test_cli_missing_top_level_command_returns_error(capsys):
    code = main([])
    captured = capsys.readouterr()

    assert code == 2
    assert "error" in captured.err


def test_cli_missing_inbox_subcommand_returns_error_before_workspace_discovery(tmp_path, capsys):
    code = main(["inbox", "--workspace", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 2
    assert "error" in captured.err


def test_cli_missing_knowledge_subcommand_returns_error_before_workspace_discovery(
    tmp_path, capsys
):
    code = main(["knowledge", "--workspace", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 2
    assert "error" in captured.err


def test_cli_malformed_config_returns_controlled_error(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    (tmp_path / ".alcove" / "config.yml").write_text("paths: [unterminated\n")

    code = main(["status", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 2
    assert "alcove:" in captured.err
    assert str(tmp_path / ".alcove" / "config.yml") in captured.err


def test_cli_search_malformed_taxonomy_returns_controlled_error(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    taxonomy_path = tmp_path / "knowledge" / "taxonomy.yml"
    taxonomy_path.write_text("domains: [unterminated\n", encoding="utf-8")

    code = main(["search", "anything", "--workspace", str(tmp_path)])
    captured = capsys.readouterr()

    assert code == 2
    assert "alcove:" in captured.err
    assert str(taxonomy_path) in captured.err
    assert "Traceback" not in captured.err


def test_cli_inbox_peek_outputs_oldest_post_title_and_content_source(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    _write_xhs_post(tmp_path, "20260707-new")
    _write_post(tmp_path, "web", "20260706-old", {"article.md": "# Oldest Post\n\nBody"})

    code = main(["inbox", "--workspace", str(tmp_path), "peek"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Oldest Post" in captured.out
    assert "article.md" in captured.out
    assert "Body" in captured.out


def test_cli_inbox_peek_xhs_outputs_summary_content_source(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    _write_xhs_post(tmp_path)

    code = main(["inbox", "--workspace", str(tmp_path), "peek"])
    captured = capsys.readouterr()

    assert code == 0
    assert "代码图谱怎么选" in captured.out
    assert "summary.md" in captured.out


def test_cli_inbox_peek_json_outputs_post_payload(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    _write_xhs_post(tmp_path)

    code = main(["inbox", "--workspace", str(tmp_path), "peek", "--json"])
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["title"] == "代码图谱怎么选"
    assert payload["identifier"] == "xhs/20260707-post"
    assert payload["content_source"] == "summary.md"
    assert payload["content_truncated"] is False
    assert payload["full_content_command"] == "alcove inbox read xhs/20260707-post --full --json"
    assert payload["content_files"][0]["path"] == "summary.md"
    assert payload["content_files"][0]["included"] is True
    assert (
        payload["content_files"][0]["read_command"]
        == "alcove inbox read xhs/20260707-post --full --json"
    )


def test_cli_inbox_empty_prints_message(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    code = main(["inbox", "--workspace", str(tmp_path), "peek"])
    captured = capsys.readouterr()

    assert code == 0
    assert captured.out.strip() == "Inbox is empty."


def test_cli_inbox_manual_add_writes_readable_item(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    add_code = main(
        [
            "inbox",
            "--workspace",
            str(tmp_path),
            "manual-add",
            "Manual Thought",
            "--content",
            "Copied manual needle.",
            "--source",
            "chat://manual",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    read_code = main(
        ["inbox", "--workspace", str(tmp_path), "read", "manual/manual-thought", "--json"]
    )
    read_output = capsys.readouterr()

    assert add_code == 0
    assert json.loads(add_output.out)["status"] == "added"
    assert read_code == 0
    read_payload = json.loads(read_output.out)
    assert read_payload["title"] == "Manual Thought"
    assert read_payload["capture_status"] == "ready"


def test_cli_knowledge_note_source_followed_by_search_outputs_matching_title(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    note_code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "note-source",
            "--platform",
            "web",
            "--title",
            "CLI Source",
            "--topic",
            "agent-engineering/agent-harness",
            "--resource",
            "https://example.test/cli",
            "--summary",
            "Searchable CLI summary.",
            "--tag",
            "code-intelligence",
        ]
    )
    note_output = capsys.readouterr()
    search_code = main(["search", "Searchable", "--workspace", str(tmp_path)])
    search_output = capsys.readouterr()

    assert note_code == 0
    assert search_code == 0
    assert "source:" in note_output.out
    assert "concept:" in note_output.out
    assert "CLI Source" in search_output.out


def test_cli_knowledge_revise_updates_existing_note(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "add-note",
            "agent-engineering/agent-harness",
            "CLI Revision",
            "--summary",
            "Old CLI summary.",
            "--tag",
            "mcp",
        ]
    )
    capsys.readouterr()

    code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "revise",
            "concepts/agent-engineering/agent-harness/cli-revision.md",
            "--summary",
            "New CLI summary.",
            "--append",
            "AI 讨论后补充的修订内容。",
            "--tag",
            "managed-kb",
            "--source-ref",
            "sources/chat/agent-engineering/cli-discussion.md",
            "--reason",
            "AI discussion",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["status"] == "revised"
    assert payload["path"].endswith(
        "knowledge/concepts/agent-engineering/agent-harness/cli-revision.md"
    )


def test_cli_knowledge_delete_is_preview_first_and_hides_default_search(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "note-source",
            "--platform",
            "web",
            "--title",
            "Outdated Source",
            "--topic",
            "agent-engineering/agent-harness",
            "--resource",
            "https://example.test/outdated",
            "--summary",
            "Outdated cleanup needle.",
        ]
    )
    capsys.readouterr()

    preview_code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "delete",
            "sources/web/agent-engineering/outdated-source.md",
            "--json",
        ]
    )
    preview_output = capsys.readouterr()
    delete_code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "delete",
            "sources/web/agent-engineering/outdated-source.md",
            "--reason",
            "confirmed obsolete from search result",
            "--confirm",
            "--json",
        ]
    )
    delete_output = capsys.readouterr()
    search_code = main(["search", "Outdated", "--workspace", str(tmp_path), "--json"])
    search_output = capsys.readouterr()
    audit_code = main(
        [
            "search",
            "Outdated",
            "--workspace",
            str(tmp_path),
            "--status",
            "deleted",
            "--json",
        ]
    )
    audit_output = capsys.readouterr()

    preview = json.loads(preview_output.out)
    deleted = json.loads(delete_output.out)
    search_rows = json.loads(search_output.out)
    audit_rows = json.loads(audit_output.out)
    assert preview_code == 0
    assert preview["status"] == "preview"
    assert delete_code == 0
    assert deleted["status"] == "deleted"
    assert deleted["deleted_at"]
    assert search_code == 0
    assert search_rows == []
    assert audit_code == 0
    assert audit_rows[0]["status"] == "deleted"
    assert audit_rows[0]["deleted_at"] == deleted["deleted_at"]


def test_cli_search_json_outputs_valid_json_with_title_and_path(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "note-source",
            "--platform",
            "web",
            "--title",
            "JSON Source",
            "--topic",
            "agent-engineering/agent-harness",
            "--resource",
            "https://example.test/json",
            "--summary",
            "Needle JSON summary.",
        ]
    )
    capsys.readouterr()

    code = main(["search", "Needle", "--workspace", str(tmp_path), "--json"])
    captured = capsys.readouterr()

    assert code == 0
    rows = json.loads(captured.out)
    matching_paths = [row["path"] for row in rows if row["title"] == "JSON Source"]
    assert matching_paths
    assert any(path.endswith(".md") for path in matching_paths)


def test_cli_search_json_handles_yaml_native_frontmatter_values(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    source_path = tmp_path / "knowledge" / "sources" / "web" / "date-title.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "---\n"
        "type: Source\n"
        "title: 2026-07-07\n"
        "topic: agent-harness\n"
        "tags:\n"
        "  - code-intelligence\n"
        "---\n"
        "# 2026-07-07\n\nNeedle date title.\n",
        encoding="utf-8",
    )

    code = main(["search", "Needle", "--workspace", str(tmp_path), "--json"])
    captured = capsys.readouterr()

    assert code == 0
    rows = json.loads(captured.out)
    assert rows[0]["title"] == "2026-07-07"
    assert rows[0]["path"] == "sources/web/date-title.md"


def test_cli_search_supports_notes_search_browse_modes(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "note-source",
            "--platform",
            "web",
            "--title",
            "Browse Source",
            "--topic",
            "agent-engineering/agent-harness",
            "--resource",
            "https://example.test/browse",
            "--summary",
            "Browse summary.",
            "--tag",
            "Agent Harness",
        ]
    )
    capsys.readouterr()

    tag_code = main(["search", "--workspace", str(tmp_path), "--tags", "--json"])
    tag_output = capsys.readouterr()
    filtered_code = main(
        [
            "search",
            "--workspace",
            str(tmp_path),
            "--tag",
            "agent-harness",
            "--topic",
            "agent-harness",
            "--platform",
            "web",
            "--type",
            "Source",
            "--json",
        ]
    )
    filtered_output = capsys.readouterr()
    recent_code = main(["search", "--workspace", str(tmp_path), "--recent", "1", "--json"])
    recent_output = capsys.readouterr()

    assert tag_code == 0
    assert any(row["tag"] == "agent-harness" for row in json.loads(tag_output.out))
    assert filtered_code == 0
    assert json.loads(filtered_output.out)[0]["title"] == "Browse Source"
    assert recent_code == 0
    assert len(json.loads(recent_output.out)) == 1


def test_cli_search_unindexed_returns_validation_issues(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    broken = tmp_path / "knowledge" / "concepts" / "broken.md"
    broken.parent.mkdir(parents=True)
    broken.write_text(
        "---\n"
        "type: Knowledge Concept\n"
        "title: Broken\n"
        "source_refs:\n"
        "  - /sources/missing.md\n"
        "---\n"
        "# Broken\n",
        encoding="utf-8",
    )

    code = main(["search", "--workspace", str(tmp_path), "--unindexed", "--json"])
    captured = capsys.readouterr()

    assert code == 1
    assert any(issue["kind"] == "dead_source_ref" for issue in json.loads(captured.out)["issues"])


def test_cli_pin_add_list_archive_and_search(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    add_code = main(
        [
            "pin",
            "--workspace",
            str(tmp_path),
            "add",
            "Pinned Snippet",
            "--summary",
            "Use Alcove for durable personal notes.",
            "--content",
            "Pin exact commands and references that need repeated lookup.",
            "--kind",
            "regular",
            "--tag",
            "personal-notes",
            "--priority",
            "high",
            "--resource",
            "https://example.test/pin",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    get_code = main(["pin", "--workspace", str(tmp_path), "get", "pinned-snippet", "--json"])
    get_output = capsys.readouterr()
    update_code = main(
        [
            "pin",
            "--workspace",
            str(tmp_path),
            "update",
            "pinned-snippet",
            "--kind",
            "todo",
            "--content",
            "Practice this workflow and refine it later.",
            "--tag",
            "practice",
            "--json",
        ]
    )
    update_output = capsys.readouterr()
    list_code = main(["pin", "--workspace", str(tmp_path), "list", "--tag", "practice", "--json"])
    list_output = capsys.readouterr()
    pin_search_code = main(
        [
            "pin",
            "--workspace",
            str(tmp_path),
            "search",
            "practice",
            "--kind",
            "todo",
            "--json",
        ]
    )
    pin_search_output = capsys.readouterr()
    index_code = main(["pin", "--workspace", str(tmp_path), "rebuild-index", "--json"])
    index_output = capsys.readouterr()
    render_code = main(["pin", "--workspace", str(tmp_path), "render-html", "--json"])
    render_output = capsys.readouterr()
    search_code = main(["search", "durable", "--workspace", str(tmp_path), "--json"])
    search_output = capsys.readouterr()
    archive_code = main(
        [
            "pin",
            "--workspace",
            str(tmp_path),
            "archive",
            "pinned-snippet",
            "--confirm",
            "--json",
        ]
    )
    archive_output = capsys.readouterr()

    assert add_code == 0
    assert json.loads(add_output.out)["status"] == "pinned"
    assert json.loads(add_output.out)["pin"]["kind"] == "regular"
    assert get_code == 0
    assert json.loads(get_output.out)["pin"]["resources"] == ["https://example.test/pin"]
    assert update_code == 0
    assert json.loads(update_output.out)["pin"]["kind"] == "todo"
    assert list_code == 0
    assert json.loads(list_output.out)[0]["title"] == "Pinned Snippet"
    assert pin_search_code == 0
    pin_search_payload = json.loads(pin_search_output.out)
    assert pin_search_payload[0]["kind"] == "todo"
    assert pin_search_payload[0]["path"] == "pins/pinned-snippet.md"
    assert index_code == 0
    assert json.loads(index_output.out)["status"] == "rebuilt"
    assert render_code == 0
    assert json.loads(render_output.out)["path"].endswith("pins/board.html")
    assert search_code == 0
    assert json.loads(search_output.out)[0]["root"] == "pins"
    assert archive_code == 0
    assert json.loads(archive_output.out)["status"] == "archived"


def test_cli_dashboard_import_and_build(tmp_path, capsys):
    home = tmp_path / "home"
    regular = tmp_path / "regular.txt"
    todo = tmp_path / "todo.txt"
    regular.write_text(
        "开发参考\n\nClaude Code\n\n/plan\n\n===\n\n快捷键\n\nCtrl + U\n", encoding="utf-8"
    )
    todo.write_text("数据看板搜索记录使用记录\n\n===\n\ngithub star 索引\n", encoding="utf-8")

    import_code = main(
        [
            "dashboard",
            "--home",
            str(home),
            "import-pins",
            "--regular-file",
            str(regular),
            "--todo-file",
            str(todo),
            "--json",
        ]
    )
    import_output = capsys.readouterr()
    build_code = main(
        ["dashboard", "--home", str(home), "build", "--skip-frontend-build", "--json"]
    )
    build_output = capsys.readouterr()

    assert import_code == 0
    assert json.loads(import_output.out)["regular"]["imported"] == 1
    assert build_code == 0
    assert json.loads(build_output.out)["status"] == "built"
    assert (home / "dashboard" / "snapshot.json").is_file()


def test_cli_project_add_get_find_list_remove(tmp_path, capsys):
    home = tmp_path / "home"
    project_root = tmp_path / "work" / "alcove"
    project_root.mkdir(parents=True)

    add_code = main(
        [
            "project",
            "--home",
            str(home),
            "add",
            "alcove",
            str(project_root),
            "--note",
            "Knowledge manager.",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    get_code = main(["project", "--home", str(home), "get", "alcove", "--json"])
    get_output = capsys.readouterr()
    find_code = main(["project", "--home", str(home), "find", "knowledge", "--json"])
    find_output = capsys.readouterr()
    list_code = main(["project", "--home", str(home), "list", "--json"])
    list_output = capsys.readouterr()
    remove_code = main(["project", "--home", str(home), "remove", "alcove", "--json"])
    remove_output = capsys.readouterr()

    assert add_code == 0
    assert json.loads(add_output.out)["project"]["alias"] == "alcove"
    assert get_code == 0
    assert json.loads(get_output.out)["project"]["path"] == str(project_root.resolve())
    assert find_code == 0
    assert json.loads(find_output.out)["projects"][0]["alias"] == "alcove"
    assert list_code == 0
    assert json.loads(list_output.out)[0]["note"] == "Knowledge manager."
    assert remove_code == 0
    assert json.loads(remove_output.out)["status"] == "removed"


def test_cli_prompt_save_search_get_tags_archive(tmp_path, capsys):
    home = tmp_path / "home"

    propose_code = main(
        [
            "prompt",
            "--home",
            str(home),
            "propose",
            "Review Lens",
            "--content",
            (
                "Review the current diff for regressions, missing tests, unclear "
                "user-facing behavior, and incomplete verification. Return findings, "
                "risks, and the exact commands or artifacts used as evidence."
            ),
            "--description",
            "Review helper.",
            "--tag",
            "review",
            "--use-case",
            "PR review",
            "--source-ref",
            "pins/review.md",
            "--kind",
            "eval_prompt",
            "--domain",
            "review",
            "--surface",
            "codex",
            "--trigger",
            "regression review",
            "--output",
            "findings",
            "--json",
        ]
    )
    propose_output = capsys.readouterr()
    proposal = json.loads(propose_output.out)
    proposal_code = main(["prompt", "--home", str(home), "proposal", proposal["id"], "--json"])
    proposal_output = capsys.readouterr()
    save_code = main(
        [
            "prompt",
            "--home",
            str(home),
            "save",
            "--proposal-id",
            proposal["id"],
            "--json",
        ]
    )
    save_output = capsys.readouterr()
    search_code = main(
        [
            "prompt",
            "--home",
            str(home),
            "search",
            "regressions",
            "--tag",
            "review",
            "--kind",
            "eval_prompt",
            "--domain",
            "review",
            "--surface",
            "codex",
            "--json",
        ]
    )
    search_output = capsys.readouterr()
    recommend_code = main(
        [
            "prompt",
            "--home",
            str(home),
            "recommend",
            "need regression review",
            "--json",
        ]
    )
    recommend_output = capsys.readouterr()
    compose_code = main(
        [
            "prompt",
            "--home",
            str(home),
            "compose",
            "need regression review",
            "--json",
        ]
    )
    compose_output = capsys.readouterr()
    audit_code = main(["prompt", "--home", str(home), "audit", "--json"])
    audit_output = capsys.readouterr()
    get_code = main(["prompt", "--home", str(home), "get", "review-lens", "--json"])
    get_output = capsys.readouterr()
    tags_code = main(["prompt", "--home", str(home), "tags", "--json"])
    tags_output = capsys.readouterr()
    index_code = main(["prompt", "--home", str(home), "rebuild-index", "--json"])
    index_output = capsys.readouterr()
    archive_code = main(
        ["prompt", "--home", str(home), "archive", "review-lens", "--confirm", "--json"]
    )
    archive_output = capsys.readouterr()

    assert propose_code == 0
    assert proposal["action"] in {"create_new", "create_new_after_review"}
    assert proposal_code == 0
    assert json.loads(proposal_output.out)["id"] == proposal["id"]
    assert save_code == 0
    assert json.loads(save_output.out)["prompt"]["id"] == "review-lens"
    assert search_code == 0
    prompt_search_payload = json.loads(search_output.out)
    assert prompt_search_payload[0]["title"] == "Review Lens"
    assert prompt_search_payload[0]["path"] == "prompts/review-lens.md"
    assert prompt_search_payload[0]["kind"] == "eval_prompt"
    assert recommend_code == 0
    assert json.loads(recommend_output.out)[0]["prompt"]["title"] == "Review Lens"
    assert compose_code == 0
    compose_payload = json.loads(compose_output.out)
    assert compose_payload["sources"][0]["title"] == "Review Lens"
    assert "Review the current diff for regressions" in compose_payload["prompt"]
    assert audit_code == 0
    audit_payload = json.loads(audit_output.out)
    assert audit_payload["counts"]["prompts"] == 1
    assert audit_payload["counts"]["ready_prompts"] == 1
    assert get_code == 0
    assert (
        "Review the current diff for regressions" in json.loads(get_output.out)["prompt"]["content"]
    )
    assert tags_code == 0
    assert {"tag": "review", "count": 1} in json.loads(tags_output.out)
    assert index_code == 0
    assert json.loads(index_output.out)["count"] == 1
    assert (home / "prompts" / "index.json").is_file()
    assert archive_code == 0
    assert json.loads(archive_output.out)["status"] == "archived"


def test_cli_prompt_save_repeated_plural_metadata_options(tmp_path, capsys):
    home = tmp_path / "home"

    code = main(
        [
            "prompt",
            "--home",
            str(home),
            "save",
            "Layered Skill Design",
            "--force",
            "--content",
            "Design skills with policy, strategy, and execution layers.",
            "--tags",
            "skill,automation",
            "--tags",
            "robustness",
            "--use-cases",
            "Create reusable skills",
            "--use-cases",
            "Upgrade fragile scripts",
            "--source-refs",
            "~/prompts/create_skill_prompt.md",
            "--source-refs",
            "~/prompts/browser_prompt.md",
            "--surfaces",
            "codex,claude",
            "--surfaces",
            "skill",
            "--triggers",
            "skill,automation",
            "--triggers",
            "browser",
            "--inputs",
            "goal,constraints",
            "--inputs",
            "failure policy",
            "--outputs",
            "layered design",
            "--outputs",
            "validation contract",
            "--quality-status",
            "curated",
            "--quality-score",
            "0.93",
            "--quality-notes",
            "Reviewed by prompt eval.",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    prompt = json.loads(output.out)["prompt"]
    assert prompt["tags"] == ["automation", "robustness", "skill"]
    assert prompt["use_cases"] == ["Create reusable skills", "Upgrade fragile scripts"]
    assert prompt["source_refs"] == [
        "~/prompts/create_skill_prompt.md",
        "~/prompts/browser_prompt.md",
    ]
    assert prompt["surfaces"] == ["claude", "codex", "skill"]
    assert prompt["triggers"] == ["skill", "automation", "browser"]
    assert prompt["inputs"] == ["goal", "constraints", "failure policy"]
    assert prompt["outputs"] == ["layered design", "validation contract"]
    assert prompt["quality"] == {
        "status": "curated",
        "score": 0.93,
        "notes": "Reviewed by prompt eval.",
    }


def test_cli_prompt_save_requires_proposal_or_force(tmp_path, capsys):
    home = tmp_path / "home"

    code = main(
        [
            "prompt",
            "--home",
            str(home),
            "save",
            "Direct Prompt",
            "--content",
            "Direct prompt content should be proposed before saving.",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 2
    payload = json.loads(output.out)
    assert "requires a proposal" in payload["error"]["message"]


def test_cli_prompt_save_rejects_unready_proposal(tmp_path, capsys):
    home = tmp_path / "home"

    propose_code = main(
        [
            "prompt",
            "--home",
            str(home),
            "propose",
            "Short Command Fragment",
            "--content",
            "继续就继续做，提交就提交，别解释。",
            "--json",
        ]
    )
    proposal_output = capsys.readouterr()
    proposal = json.loads(proposal_output.out)
    save_code = main(
        [
            "prompt",
            "--home",
            str(home),
            "save",
            "--proposal-id",
            proposal["id"],
            "--json",
        ]
    )
    save_output = capsys.readouterr()

    assert propose_code == 0
    assert proposal["evaluation"]["verdict"] == "reject"
    assert save_code == 2
    payload = json.loads(save_output.out)
    assert "not ready" in payload["error"]["message"] or "recommends" in payload["error"]["message"]


def test_cli_idea_and_task_workflows(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    idea_code = main(
        [
            "idea",
            "--workspace",
            str(tmp_path),
            "add",
            "Explore mounts",
            "--notes",
            "Index local repos later.",
            "--tag",
            "mounts",
            "--json",
        ]
    )
    idea_output = capsys.readouterr()
    task_code = main(
        [
            "task",
            "--workspace",
            str(tmp_path),
            "add",
            "Ship MCP server",
            "--notes",
            "Expose search first.",
            "--tag",
            "mcp",
            "--priority",
            "high",
            "--json",
        ]
    )
    task_output = capsys.readouterr()
    list_code = main(["task", "--workspace", str(tmp_path), "list", "--json"])
    list_output = capsys.readouterr()
    complete_code = main(
        [
            "task",
            "--workspace",
            str(tmp_path),
            "complete",
            "ship-mcp-server",
            "--json",
        ]
    )
    complete_output = capsys.readouterr()

    assert idea_code == 0
    assert json.loads(idea_output.out)["idea"]["id"] == "explore-mounts"
    assert task_code == 0
    assert json.loads(task_output.out)["task"]["priority"] == "high"
    assert list_code == 0
    assert json.loads(list_output.out)[0]["title"] == "Ship MCP server"
    assert complete_code == 0
    assert json.loads(complete_output.out)["task"]["status"] == "done"


def test_cli_idea_promote_and_routine_materialize(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    main(
        [
            "idea",
            "--workspace",
            str(tmp_path),
            "add",
            "Review inbox process",
            "--notes",
            "Turn this into concrete work.",
            "--tag",
            "workflow",
            "--json",
        ]
    )
    capsys.readouterr()
    promote_code = main(
        [
            "idea",
            "--workspace",
            str(tmp_path),
            "promote",
            "review-inbox-process",
            "--priority",
            "high",
            "--due",
            "2026-07-09",
            "--notes",
            "Add checks.",
            "--json",
        ]
    )
    promote_output = capsys.readouterr()
    routine_code = main(
        [
            "task",
            "--workspace",
            str(tmp_path),
            "routine-add",
            "Weekly inbox review",
            "--every-days",
            "7",
            "--next-due",
            "2026-07-08",
            "--tag",
            "review",
            "--json",
        ]
    )
    routine_output = capsys.readouterr()
    materialize_code = main(
        [
            "task",
            "--workspace",
            str(tmp_path),
            "materialize-due",
            "--today",
            "2026-07-08",
            "--json",
        ]
    )
    materialize_output = capsys.readouterr()

    assert promote_code == 0
    assert json.loads(promote_output.out)["idea"]["status"] == "promoted"
    assert json.loads(promote_output.out)["task"]["priority"] == "high"
    assert routine_code == 0
    assert json.loads(routine_output.out)["routine"]["next_due"] == "2026-07-08"
    assert materialize_code == 0
    assert json.loads(materialize_output.out)["created"][0]["due"] == "2026-07-08"


def test_cli_task_full_lifecycle_and_digest(tmp_path, capsys, monkeypatch):
    home = tmp_path / ".alcove"
    sent: list[str] = []

    def fake_send(*, home, text):
        sent.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_telegram_message", fake_send)

    task_code = main(
        [
            "task",
            "--home",
            str(home),
            "add",
            "Review planner",
            "--due",
            "2026-07-01",
            "--json",
        ]
    )
    capsys.readouterr()
    edit_code = main(
        [
            "task",
            "--home",
            str(home),
            "edit",
            "review-planner",
            "--title",
            "Review planner module",
            "--priority",
            "high",
            "--json",
        ]
    )
    edit_output = capsys.readouterr()
    routine_code = main(
        [
            "task",
            "--home",
            str(home),
            "routine-add",
            "Weekly planner review",
            "--frequency",
            "weekly",
            "--weekday",
            "sun",
            "--next-due",
            "2026-07-12",
            "--json",
        ]
    )
    capsys.readouterr()
    pause_code = main(
        ["task", "--home", str(home), "routine-pause", "weekly-planner-review", "--json"]
    )
    pause_output = capsys.readouterr()
    resume_code = main(
        [
            "task",
            "--home",
            str(home),
            "routine-resume",
            "weekly-planner-review",
            "--today",
            "2026-07-12",
            "--json",
        ]
    )
    resume_output = capsys.readouterr()
    digest_code = main(
        [
            "task",
            "--home",
            str(home),
            "digest",
            "--period",
            "weekly",
            "--today",
            "2026-07-12",
            "--notify",
            "--json",
        ]
    )
    digest_output = capsys.readouterr()

    assert task_code == 0
    assert edit_code == 0
    assert json.loads(edit_output.out)["task"]["title"] == "Review planner module"
    assert routine_code == 0
    assert pause_code == 0
    assert json.loads(pause_output.out)["routine"]["status"] == "paused"
    assert resume_code == 0
    assert json.loads(resume_output.out)["routine"]["status"] == "active"
    assert digest_code == 0
    digest = json.loads(digest_output.out)
    assert digest["status"] == "sent"
    assert "Review planner module" in digest["text"]
    assert "Weekly planner review" in sent[0]


def test_cli_idea_edit_archive_and_promote_to_routine(tmp_path, capsys):
    home = tmp_path / ".alcove"
    main(["idea", "--home", str(home), "add", "Planner thought", "--json"])
    capsys.readouterr()
    edit_code = main(
        [
            "idea",
            "--home",
            str(home),
            "edit",
            "planner-thought",
            "--title",
            "Planner weekly thought",
            "--tag",
            "planner",
            "--json",
        ]
    )
    edit_output = capsys.readouterr()
    promote_code = main(
        [
            "idea",
            "--home",
            str(home),
            "promote-routine",
            "planner-weekly-thought",
            "--frequency",
            "weekly",
            "--weekday",
            "mon",
            "--next-due",
            "2026-07-13",
            "--json",
        ]
    )
    promote_output = capsys.readouterr()
    main(["idea", "--home", str(home), "add", "Archive this", "--json"])
    capsys.readouterr()
    archive_code = main(["idea", "--home", str(home), "archive", "archive-this", "--json"])
    archive_output = capsys.readouterr()

    assert edit_code == 0
    assert json.loads(edit_output.out)["idea"]["title"] == "Planner weekly thought"
    assert promote_code == 0
    assert json.loads(promote_output.out)["routine"]["schedule"]["weekdays"] == ["mon"]
    assert archive_code == 0
    assert json.loads(archive_output.out)["idea"]["status"] == "archived"


def test_cli_mount_add_list_scan_and_search(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    source = tmp_path / "external"
    source.mkdir()
    (source / "note.md").write_text("# External Note\n\nMounted CLI needle.", encoding="utf-8")

    add_code = main(
        [
            "mount",
            "--workspace",
            str(tmp_path),
            "add",
            str(source),
            "--name",
            "External",
            "--tag",
            "external",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    list_code = main(["mount", "--workspace", str(tmp_path), "list", "--json"])
    list_output = capsys.readouterr()
    scan_code = main(["mount", "--workspace", str(tmp_path), "scan", "--json"])
    scan_output = capsys.readouterr()
    search_code = main(["search", "mounted cli", "--workspace", str(tmp_path), "--json"])
    search_output = capsys.readouterr()

    assert add_code == 0
    assert json.loads(add_output.out)["mount"]["name"] == "External"
    assert list_code == 0
    assert json.loads(list_output.out)[0]["id"] == "external"
    assert scan_code == 0
    assert json.loads(scan_output.out)["scanned"] == 1
    assert search_code == 0
    assert json.loads(search_output.out)[0]["root"] == "mounts"


def test_cli_connector_apple_notes_index_and_search(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    export_dir = tmp_path / "apple-notes-export"
    note_dir = export_dir / "notes" / "x-coredata%3A%2F%2Fnote-cli"
    note_dir.mkdir(parents=True)
    (note_dir / "note.json").write_text(
        json.dumps(
            {
                "id": "x-coredata://note-cli",
                "title": "CLI Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Inbox",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "CLI connector needle.",
                "body_html": "<div>CLI connector needle.</div>",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    index_code = main(
        [
            "connector",
            "--workspace",
            str(tmp_path),
            "apple-notes",
            "index",
            str(export_dir),
            "--tag",
            "apple-notes",
            "--json",
        ]
    )
    index_output = capsys.readouterr()
    search_code = main(["search", "connector needle", "--workspace", str(tmp_path), "--json"])
    search_output = capsys.readouterr()
    fetch_code = main(
        [
            "connector",
            "--workspace",
            str(tmp_path),
            "fetch",
            "connectors/apple-notes#notes/x-coredata%3A%2F%2Fnote-cli/note.json",
            "--json",
        ]
    )
    fetch_output = capsys.readouterr()

    assert index_code == 0
    index_payload = json.loads(index_output.out)
    assert index_payload["scanned"] == 1
    assert index_payload["item_count"] == 1
    assert "items" not in index_payload
    assert search_code == 0
    assert json.loads(search_output.out)[0]["type"] == "Apple Note"
    assert fetch_code == 0
    fetch_payload = json.loads(fetch_output.out)
    assert fetch_payload["source"] == "local-export"
    assert fetch_payload["detail"]["body_html"] == "<div>CLI connector needle.</div>"
    assert "path" not in fetch_payload["item"]
    assert "path" not in fetch_payload["detail"]


def test_cli_connector_apple_notes_import_local_and_refresh(
    tmp_path,
    monkeypatch,
    capsys,
):
    home_root = tmp_path / "home"
    notes = [
        {
            "id": "x-coredata://note-cli-local",
            "title": "CLI Local Apple Note",
            "account": "iCloud",
            "folder_path": "iCloud/Inbox",
            "created_at": "2026-07-07T08:00:00Z",
            "updated_at": "2026-07-08T09:00:00Z",
            "plaintext": "CLI local connector needle.",
            "body_html": "<div>CLI local connector needle.</div>",
        }
    ]

    def fake_export(self, output_dir):
        return write_apple_notes_export_tree(notes, output_dir)

    monkeypatch.setattr(
        "alcove.connectors.apple_notes.LocalAppleNotesExporter.export_all", fake_export
    )

    import_code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "apple-notes",
            "import-local",
            "--tag",
            "apple-notes",
            "--json",
        ]
    )
    import_output = capsys.readouterr()
    notes[0]["plaintext"] = "CLI refreshed connector needle."
    notes[0]["updated_at"] = "2026-07-09T09:00:00Z"
    refresh_code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "apple-notes",
            "refresh",
            "local",
            "--force",
            "--json",
        ]
    )
    refresh_output = capsys.readouterr()
    reuse_code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "apple-notes",
            "refresh",
            "local",
            "--force",
            "--json",
        ]
    )
    reuse_output = capsys.readouterr()
    search_code = main(
        [
            "search",
            "--home",
            str(home_root),
            "refreshed connector",
            "--type",
            "Apple Note",
            "--json",
        ]
    )
    search_output = capsys.readouterr()

    import_payload = json.loads(import_output.out)
    refresh_payload = json.loads(refresh_output.out)
    assert import_code == 0
    assert import_payload["status"] == "imported"
    assert import_payload["scanned"] == 1
    assert import_payload["summary"]["added_count"] == 1
    assert "home" not in import_payload
    assert "export_dir" not in import_payload
    assert "index_path" not in import_payload
    assert "debug" not in import_payload
    assert refresh_code == 0
    assert refresh_payload["refreshed"] == 1
    assert "home" not in refresh_payload
    assert refresh_payload["sources"][0]["diff_summary"]["updated_count"] == 1
    assert "export_dir" not in refresh_payload["sources"][0]
    assert "index_path" not in refresh_payload["sources"][0]
    reuse_payload = json.loads(reuse_output.out)
    assert reuse_code == 0
    assert reuse_payload["reused"] == 1
    assert reuse_payload["sources"][0]["reused"] == 1
    assert search_code == 0
    assert json.loads(search_output.out)[0]["title"] == "CLI Local Apple Note"


def test_cli_connector_apple_notes_import_local_reports_diagnostic_error(
    tmp_path,
    monkeypatch,
    capsys,
):
    def fake_export(self, output_dir):
        raise AppleNotesAutomationError("Can't get object.")

    monkeypatch.setattr(
        "alcove.connectors.apple_notes.LocalAppleNotesExporter.export_all", fake_export
    )

    code = main(
        [
            "connector",
            "--home",
            str(tmp_path / "home"),
            "apple-notes",
            "import-local",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 2
    assert payload["error"]["error_code"] == "applenotesautomation"
    assert payload["error"]["connector"] == "apple-notes"
    assert payload["error"]["operation"] == "export-all-notes"
    assert payload["error"]["remediation_command"] == (
        "alcove connector apple-notes import-local --json"
    )
    assert "Automation access" in payload["error"]["remediation_hint"]


def test_cli_connector_github_stars_index_and_search(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Personal knowledge management core.",
                    "language": "Python",
                    "topics": ["pkm"],
                    "stargazers_count": 100,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    index_code = main(
        [
            "connector",
            "--workspace",
            str(tmp_path),
            "github-stars",
            "index",
            str(export_file),
            "--tag",
            "stars",
            "--json",
        ]
    )
    index_output = capsys.readouterr()
    search_code = main(["search", "knowledge management", "--workspace", str(tmp_path), "--json"])
    search_output = capsys.readouterr()
    tags_code = main(["search", "--workspace", str(tmp_path), "--tags", "--limit", "1", "--json"])
    tags_output = capsys.readouterr()

    assert index_code == 0
    index_payload = json.loads(index_output.out)
    assert index_payload["scanned"] == 1
    assert index_payload["item_count"] == 1
    assert "items" not in index_payload
    assert search_code == 0
    assert json.loads(search_output.out)[0]["type"] == "GitHub Star"
    assert tags_code == 0
    assert len(json.loads(tags_output.out)) == 1


def test_cli_connector_json_errors_are_structured(tmp_path, capsys):
    home_root = tmp_path / "home"

    code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "github-stars",
            "import-url",
            "https://example.com/octocat?tab=stars",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 2
    assert output.err == ""
    assert payload["error"]["connector"] == "github-stars"
    assert payload["error"]["error_code"] == "value"
    assert payload["error"]["message"] == "Unsupported GitHub Stars URL host: example.com"
    assert "GitHub profile URL" in payload["error"]["remediation_hint"]


def test_cli_connector_chrome_bookmarks_index_import_local_and_refresh(
    tmp_path,
    capsys,
):
    home_root = tmp_path / "home"
    bookmarks_file = tmp_path / "Bookmarks"
    bookmarks_file.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "type": "folder",
                        "name": "Bookmarks Bar",
                        "children": [
                            {
                                "type": "url",
                                "name": "Codegraph",
                                "url": "https://github.com/colbymchenry/codegraph",
                                "date_added": "13300000001000000",
                            }
                        ],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    import_code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "chrome-bookmarks",
            "import-local",
            "--source-file",
            str(bookmarks_file),
            "--tag",
            "bookmarks",
            "--json",
        ]
    )
    import_output = capsys.readouterr()
    search_code = main(["search", "codegraph", "--home", str(home_root), "--json"])
    search_output = capsys.readouterr()
    bookmarks_file.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "type": "folder",
                        "name": "Bookmarks Bar",
                        "children": [
                            {
                                "type": "url",
                                "name": "Codegraph",
                                "url": "https://github.com/colbymchenry/codegraph",
                                "date_added": "13300000001000000",
                            },
                            {
                                "type": "url",
                                "name": "Alcove",
                                "url": "https://github.com/OctopusGarage/alcove",
                                "date_added": "13300000002000000",
                            },
                        ],
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    refresh_code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "chrome-bookmarks",
            "refresh",
            "--force",
            "--json",
        ]
    )
    refresh_output = capsys.readouterr()

    import_payload = json.loads(import_output.out)
    search_payload = json.loads(search_output.out)
    refresh_payload = json.loads(refresh_output.out)
    assert import_code == 0
    assert import_payload["scanned"] == 1
    assert import_payload["item_count"] == 1
    assert "home" not in import_payload
    assert "source_file" not in import_payload
    assert (home_root / "connectors" / "chrome-bookmarks" / "index.json").is_file()
    assert search_code == 0
    assert search_payload[0]["type"] == "Chrome Bookmark"
    assert search_payload[0]["date"] == "2022-06-18"
    assert refresh_code == 0
    assert refresh_payload["refreshed"] == 1
    assert refresh_payload["sources"][0]["diff_summary"]["added_count"] == 1
    assert "source_file" not in refresh_payload["sources"][0]


def test_cli_kb_add_and_list_use_alcove_home_registry(tmp_path, capsys):
    kb_root = tmp_path / "research_notes"
    main(["init", str(kb_root)])
    capsys.readouterr()
    home_root = tmp_path / "home"

    add_code = main(
        [
            "kb",
            "--home",
            str(home_root),
            "add",
            "research_notes",
            str(kb_root),
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    list_code = main(["kb", "--home", str(home_root), "list", "--json"])
    list_output = capsys.readouterr()

    assert add_code == 0
    assert json.loads(add_output.out)["knowledge_base"]["name"] == "research_notes"
    assert (home_root / "knowledge-bases" / "research_notes.yml").is_file()
    assert list_code == 0
    assert json.loads(list_output.out)[0]["path"] == str(kb_root.resolve())


def test_cli_registered_kb_name_can_replace_workspace_path(tmp_path, capsys):
    kb_root = tmp_path / "research_notes"
    main(["init", str(kb_root)])
    capsys.readouterr()
    home_root = tmp_path / "home"
    main(
        [
            "kb",
            "--home",
            str(home_root),
            "add",
            "research_notes",
            str(kb_root),
            "--json",
        ]
    )
    capsys.readouterr()
    _write_post(kb_root, "web", "20260708-note", {"article.md": "# KB Name\n\nBody"})

    code = main(
        [
            "inbox",
            "--home",
            str(home_root),
            "--kb",
            "research_notes",
            "peek",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    assert json.loads(output.out)["title"] == "KB Name"


def test_cli_global_home_features_are_searchable_without_workspace(tmp_path, capsys):
    home_root = tmp_path / "home"
    mount_source = tmp_path / "external"
    mount_source.mkdir()
    (mount_source / "note.md").write_text(
        "# Global Mount\n\nGlobal mounted needle.",
        encoding="utf-8",
    )
    stars_file = tmp_path / "stars.json"
    stars_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Global connector needle.",
                    "language": "Python",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    pin_code = main(
        [
            "pin",
            "--home",
            str(home_root),
            "add",
            "Global Pin",
            "--description",
            "Global pin needle.",
            "--json",
        ]
    )
    capsys.readouterr()
    task_code = main(
        [
            "task",
            "--home",
            str(home_root),
            "add",
            "Global Task",
            "--notes",
            "Global task needle.",
            "--json",
        ]
    )
    capsys.readouterr()
    mount_code = main(
        [
            "mount",
            "--home",
            str(home_root),
            "add",
            str(mount_source),
            "--name",
            "Global Mount",
            "--json",
        ]
    )
    capsys.readouterr()
    scan_code = main(["mount", "--home", str(home_root), "scan", "--json"])
    capsys.readouterr()
    connector_code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "github-stars",
            "index",
            str(stars_file),
            "--json",
        ]
    )
    connector_output = capsys.readouterr()
    search_code = main(["search", "global", "--home", str(home_root), "--json"])
    search_output = capsys.readouterr()

    assert pin_code == 0
    assert task_code == 0
    assert mount_code == 0
    assert scan_code == 0
    assert connector_code == 0
    assert "home" not in json.loads(connector_output.out)
    assert (home_root / "pins" / "global-pin.md").is_file()
    assert (home_root / "tasks" / "tasks.json").is_file()
    assert (home_root / "mounts" / "indexes" / "global-mount.json").is_file()
    assert (home_root / "connectors" / "github-stars" / "index.json").is_file()
    assert search_code == 0
    roots = {row["root"] for row in json.loads(search_output.out)}
    assert {"pins", "tasks", "mounts", "connectors"}.issubset(roots)


def test_cli_github_stars_import_url_fetches_exports_and_indexes(
    tmp_path,
    monkeypatch,
    capsys,
):
    home_root = tmp_path / "home"

    def fake_fetch(self, username: str, *, page: int, per_page: int):
        assert username == "octocat"
        assert per_page == 100
        if page == 1:
            return [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Local-first personal knowledge core.",
                    "language": "Python",
                    "topics": ["knowledge-base"],
                    "stargazers_count": 100,
                }
            ]
        return []

    monkeypatch.setattr(GitHubStarsConnector, "_fetch_starred_page", fake_fetch)

    code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "github-stars",
            "import-url",
            "https://github.com/octocat?tab=stars",
            "--tag",
            "github-stars",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["username"] == "octocat"
    assert payload["exported"] == 1
    assert payload["scanned"] == 1
    assert payload["item_count"] == 1
    assert "home" not in payload
    assert "items" not in payload
    assert "export_file" not in payload
    assert "index_path" not in payload
    assert "debug" not in payload
    assert payload["diff_summary"]["added_count"] == 1
    assert "diff" not in payload
    assert (home_root / "connectors" / "github-stars" / "index.json").is_file()
    assert (
        home_root / "connectors" / "github-stars" / "exports" / "octocat-starred.json"
    ).is_file()


def test_cli_connector_status_lists_registered_sources(tmp_path, capsys):
    home_root = tmp_path / "home"
    registry = ConnectorSourceRegistry(home=AlcoveHome.init(home_root))
    registry.upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=home_root / "connectors" / "github-stars" / "exports" / "stars.json",
        index_path=home_root / "connectors" / "github-stars" / "index.json",
        item_count=445,
        checked_at="2026-07-07T00:00:00+00:00",
        changed_at="2026-07-07T00:00:00+00:00",
    )

    code = main(["connector", "--home", str(home_root), "status", "--json"])
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["count"] == 1
    assert payload["sources"][0]["connector"] == "github-stars"
    assert payload["sources"][0]["id"] == "octocat"
    assert "storage_path" not in payload["sources"][0]


def test_cli_connector_refresh_stale_refreshes_registered_github_stars(
    tmp_path,
    monkeypatch,
    capsys,
):
    home_root = tmp_path / "home"
    registry = ConnectorSourceRegistry(home=AlcoveHome.init(home_root))
    registry.upsert_github_stars(
        source_id="octocat",
        source="https://github.com/octocat?tab=stars",
        username="octocat",
        tags=["github-stars"],
        export_file=home_root / "connectors" / "github-stars" / "exports" / "stars.json",
        index_path=home_root / "connectors" / "github-stars" / "index.json",
        item_count=1,
        checked_at="2026-07-07T00:00:00+00:00",
        changed_at="2026-07-07T00:00:00+00:00",
    )

    def fake_fetch(self, username: str, *, page: int, per_page: int):
        if page > 1:
            return []
        return [{"full_name": "octopusgarage/alcove", "html_url": "https://github.com/x/y"}]

    monkeypatch.setattr(GitHubStarsConnector, "_fetch_starred_page", fake_fetch)

    code = main(["connector", "--home", str(home_root), "refresh", "--stale", "--json"])
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["refreshed"] == 1
    assert payload["sources"][0]["id"] == "octocat"
    assert payload["sources"][0]["diff_summary"]["added_count"] == 1
    assert "home" not in payload
    assert "diff" not in payload["sources"][0]
    assert "export_file" not in payload["sources"][0]
    assert "index_path" not in payload["sources"][0]


def test_cli_github_stars_import_url_can_include_items(
    tmp_path,
    monkeypatch,
    capsys,
):
    home_root = tmp_path / "home"

    def fake_fetch(self, username: str, *, page: int, per_page: int):
        if page > 1:
            return []
        return [
            {
                "full_name": "octopusgarage/alcove",
                "html_url": "https://github.com/OctopusGarage/alcove",
                "description": "Local-first personal knowledge core.",
                "language": "Python",
                "topics": ["knowledge-base"],
                "stargazers_count": 100,
            }
        ]

    monkeypatch.setattr(GitHubStarsConnector, "_fetch_starred_page", fake_fetch)

    code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "github-stars",
            "import-url",
            "octocat",
            "--include-items",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["item_count"] == 1
    assert payload["items"][0]["title"] == "octopusgarage/alcove"


def test_cli_github_stars_import_url_can_include_full_diff(
    tmp_path,
    monkeypatch,
    capsys,
):
    home_root = tmp_path / "home"

    def fake_fetch(self, username: str, *, page: int, per_page: int):
        if page > 1:
            return []
        return [
            {
                "full_name": "octopusgarage/alcove",
                "html_url": "https://github.com/OctopusGarage/alcove",
            }
        ]

    monkeypatch.setattr(GitHubStarsConnector, "_fetch_starred_page", fake_fetch)

    code = main(
        [
            "connector",
            "--home",
            str(home_root),
            "github-stars",
            "import-url",
            "octocat",
            "--include-diff",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["diff"]["added"] == ["octopusgarage/alcove"]
    assert "diff_summary" not in payload


def test_cli_global_pin_and_task_payloads_include_home_scope(tmp_path, capsys):
    home_root = tmp_path / "home"

    pin_code = main(
        [
            "pin",
            "--home",
            str(home_root),
            "add",
            "Scoped Pin",
            "--json",
        ]
    )
    pin_output = capsys.readouterr()
    task_code = main(
        [
            "task",
            "--home",
            str(home_root),
            "add",
            "Scoped Task",
            "--json",
        ]
    )
    task_output = capsys.readouterr()

    assert pin_code == 0
    assert json.loads(pin_output.out)["home"] == str(home_root.resolve())
    assert task_code == 0
    assert json.loads(task_output.out)["home"] == str(home_root.resolve())


def test_cli_pin_archive_payload_includes_home_scope(tmp_path, capsys):
    home_root = tmp_path / "home"
    main(["pin", "--home", str(home_root), "add", "Scoped Archive Pin", "--json"])
    capsys.readouterr()

    archive_code = main(
        [
            "pin",
            "--home",
            str(home_root),
            "archive",
            "scoped-archive-pin",
            "--confirm",
            "--json",
        ]
    )
    archive_output = capsys.readouterr()

    assert archive_code == 0
    assert json.loads(archive_output.out)["home"] == str(home_root.resolve())


def test_cli_task_family_payloads_include_home_scope(tmp_path, capsys):
    home_root = tmp_path / "home"

    idea_add_code = main(
        [
            "idea",
            "--home",
            str(home_root),
            "add",
            "Scoped Idea",
            "--json",
        ]
    )
    idea_add_output = capsys.readouterr()
    idea_promote_code = main(
        [
            "idea",
            "--home",
            str(home_root),
            "promote",
            "scoped-idea",
            "--json",
        ]
    )
    idea_promote_output = capsys.readouterr()
    task_list_code = main(["task", "--home", str(home_root), "list", "--json"])
    task_list_output = capsys.readouterr()
    task_complete_code = main(
        [
            "task",
            "--home",
            str(home_root),
            "complete",
            "scoped-idea",
            "--json",
        ]
    )
    task_complete_output = capsys.readouterr()
    routine_add_code = main(
        [
            "task",
            "--home",
            str(home_root),
            "routine-add",
            "Scoped Routine",
            "--next-due",
            "2026-07-08",
            "--json",
        ]
    )
    routine_add_output = capsys.readouterr()
    materialize_code = main(
        [
            "task",
            "--home",
            str(home_root),
            "materialize-due",
            "--today",
            "2026-07-08",
            "--json",
        ]
    )
    materialize_output = capsys.readouterr()

    assert idea_add_code == 0
    assert json.loads(idea_add_output.out)["home"] == str(home_root.resolve())
    assert idea_promote_code == 0
    assert json.loads(idea_promote_output.out)["home"] == str(home_root.resolve())
    assert task_list_code == 0
    assert json.loads(task_list_output.out)[0]["title"] == "Scoped Idea"
    assert task_complete_code == 0
    assert json.loads(task_complete_output.out)["home"] == str(home_root.resolve())
    assert routine_add_code == 0
    assert json.loads(routine_add_output.out)["home"] == str(home_root.resolve())
    assert materialize_code == 0
    assert json.loads(materialize_output.out)["home"] == str(home_root.resolve())


def test_cli_mount_write_payloads_include_home_scope(tmp_path, capsys):
    home_root = tmp_path / "home"
    source = tmp_path / "external"
    source.mkdir()
    (source / "note.md").write_text("# Scoped Mount\n\nNeedle.", encoding="utf-8")

    add_code = main(
        [
            "mount",
            "--home",
            str(home_root),
            "add",
            str(source),
            "--name",
            "Scoped Mount",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    scan_code = main(["mount", "--home", str(home_root), "scan", "--json"])
    scan_output = capsys.readouterr()

    assert add_code == 0
    assert json.loads(add_output.out)["home"] == str(home_root.resolve())
    assert scan_code == 0
    assert json.loads(scan_output.out)["home"] == str(home_root.resolve())


def test_cli_export_global_home_copies_user_state(tmp_path, capsys):
    home_root = tmp_path / "home"
    kb_root = tmp_path / "kb"
    main(["init", str(kb_root)])
    capsys.readouterr()
    main(
        [
            "kb",
            "--home",
            str(home_root),
            "add",
            "research_notes",
            str(kb_root),
            "--json",
        ]
    )
    capsys.readouterr()
    main(
        [
            "pin",
            "--home",
            str(home_root),
            "add",
            "Exported Pin",
            "--description",
            "Backup this pin.",
            "--json",
        ]
    )
    capsys.readouterr()
    main(["task", "--home", str(home_root), "add", "Exported Task", "--json"])
    capsys.readouterr()

    output_dir = tmp_path / "backup"
    code = main(["export", "--home", str(home_root), "global", str(output_dir), "--json"])
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "exported"
    assert (output_dir / "config.yml").is_file()
    assert (output_dir / "knowledge-bases" / "research_notes.yml").is_file()
    assert (output_dir / "pins" / "exported-pin.md").is_file()
    assert (output_dir / "tasks" / "tasks.json").is_file()
    assert (output_dir / "manifest.json").is_file()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["summary"]["file_count"] >= 4
    assert manifest["readback"]["status"] == "passed"
    assert any(entry["name"] == "pins" and entry["sha256"] for entry in manifest["entry_details"])
    assert payload["manifest_excerpt"]["entry_details"][0]["sha256"]


def test_cli_export_kb_and_all_copy_managed_kb_without_legacy_dirs(tmp_path, capsys):
    home_root = tmp_path / "home"
    kb_root = tmp_path / "kb"
    main(["init", str(kb_root)])
    capsys.readouterr()
    (kb_root / "knowledge" / "concepts").mkdir(parents=True)
    (kb_root / "knowledge" / "concepts" / "note.md").write_text("# Note\n", encoding="utf-8")
    (kb_root / "inbox" / "manual" / "draft").mkdir(parents=True)
    (kb_root / "inbox" / "manual" / "draft" / "note.md").write_text("# Draft\n", encoding="utf-8")
    main(["kb", "--home", str(home_root), "add", "research_notes", str(kb_root), "--json"])
    capsys.readouterr()

    kb_output = tmp_path / "kb-backup"
    kb_code = main(
        ["export", "--home", str(home_root), "kb", "research_notes", str(kb_output), "--json"]
    )
    kb_capture = capsys.readouterr()
    all_output = tmp_path / "all-backup"
    all_code = main(["export", "--home", str(home_root), "all", str(all_output), "--json"])
    all_capture = capsys.readouterr()

    kb_payload = json.loads(kb_capture.out)
    all_payload = json.loads(all_capture.out)
    assert kb_code == 0
    assert kb_payload["type"] == "kb"
    assert (kb_output / ".alcove" / "config.yml").is_file()
    assert (kb_output / "knowledge" / "concepts" / "note.md").is_file()
    assert (kb_output / "inbox" / "manual" / "draft" / "note.md").is_file()
    assert not (kb_output / "pins").exists()
    assert not (kb_output / "tasks").exists()
    assert not (kb_output / "mounts").exists()
    assert all_code == 0
    assert all_payload["type"] == "all"
    assert (all_output / "global" / "knowledge-bases" / "research_notes.yml").is_file()
    assert (
        all_output / "knowledge-bases" / "research_notes" / "knowledge" / "concepts" / "note.md"
    ).is_file()
    kb_manifest = json.loads((kb_output / "manifest.json").read_text(encoding="utf-8"))
    all_manifest = json.loads((all_output / "manifest.json").read_text(encoding="utf-8"))
    assert kb_manifest["summary"]["file_count"] >= 3
    assert kb_manifest["readback"]["status"] == "passed"
    assert all_manifest["summary"]["file_count"] >= kb_manifest["summary"]["file_count"]
    assert all_payload["manifest_excerpt"]["global"]["readback"]["status"] == "passed"
    assert all_payload["manifest_excerpt"]["knowledge_bases"][0]["kb"] == "research_notes"


def test_cli_link_source_promotes_connector_item(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Personal knowledge management core.",
                    "language": "Python",
                    "topics": ["pkm"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    main(
        [
            "connector",
            "--workspace",
            str(tmp_path),
            "github-stars",
            "index",
            str(export_file),
            "--json",
        ]
    )
    capsys.readouterr()

    code = main(
        [
            "link",
            "--workspace",
            str(tmp_path),
            "source",
            "connectors/github-stars#octopusgarage/alcove",
            "ai-knowledge/knowledge-base",
            "--summary",
            "Useful reference for personal knowledge tooling.",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    assert json.loads(output.out)["status"] == "linked"
    assert json.loads(output.out)["source_path"].endswith("octopusgarage-alcove.md")


def test_cli_inbox_note_moves_item_and_prints_paths(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    _write_xhs_post(tmp_path, "20260707-note")

    code = main(
        [
            "inbox",
            "--workspace",
            str(tmp_path),
            "note",
            "20260707-note",
            "agent-engineering/agent-harness",
            "--summary",
            "代码图谱选型要看索引准确性。",
            "--tag",
            "code-intelligence",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    assert "archive:" in captured.out
    assert "source:" in captured.out
    assert "concept:" in captured.out
    assert not (tmp_path / "inbox" / "xhs" / "20260707-note").exists()
    assert (tmp_path / "archive" / "agent-harness" / "[xhs] 20260707-note").is_dir()


def test_cli_inbox_note_ambiguous_name_returns_controlled_error(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    _write_post(tmp_path, "web", "20260707-same", {"article.md": "# Web\n\nBody"})
    _write_post(tmp_path, "x", "20260707-same", {"post.md": "# X\n\nBody"})

    code = main(
        [
            "inbox",
            "--workspace",
            str(tmp_path),
            "note",
            "20260707-same",
            "agent-engineering/agent-harness",
            "--summary",
            "Summary.",
        ]
    )
    captured = capsys.readouterr()

    assert code == 2
    assert "Ambiguous inbox item" in captured.err


def test_cli_inbox_archive_classify_todo_and_delete(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    _write_post(
        tmp_path,
        "web",
        "20260707-archive",
        {"article.md": "# Archive Me\n\nSource URL: https://example.test/a\n\nBody"},
    )
    _write_post(tmp_path, "web", "20260707-todo", {"article.md": "# Todo Me\n\nBody"})
    _write_post(tmp_path, "web", "20260707-delete", {"article.md": "# Delete Me\n\nBody"})

    classify_code = main(
        [
            "inbox",
            "--workspace",
            str(tmp_path),
            "classify",
            "20260707-archive",
            "agent-engineering/agent-harness",
        ]
    )
    classify_output = capsys.readouterr()
    archive_code = main(
        [
            "inbox",
            "--workspace",
            str(tmp_path),
            "archive",
            "20260707-archive",
            "agent-engineering/agent-harness",
            "--summary",
            "Archive summary.",
            "--json",
        ]
    )
    archive_output = capsys.readouterr()
    todo_code = main(
        ["inbox", "--workspace", str(tmp_path), "todo", "20260707-todo", "Need review"]
    )
    todo_output = capsys.readouterr()
    preview_code = main(["inbox", "--workspace", str(tmp_path), "delete", "20260707-delete"])
    preview_output = capsys.readouterr()
    delete_code = main(
        ["inbox", "--workspace", str(tmp_path), "delete", "20260707-delete", "--confirm"]
    )
    delete_output = capsys.readouterr()

    assert classify_code == 0
    assert json.loads(classify_output.out)["topic"] == "agent-harness"
    assert archive_code == 0
    assert json.loads(archive_output.out)["concept"] == ""
    assert todo_code == 0
    assert json.loads(todo_output.out)["status"] == "todo"
    assert preview_code == 0
    assert json.loads(preview_output.out)["confirm_required"] is True
    assert delete_code == 0
    assert json.loads(delete_output.out)["status"] == "deleted"


def test_cli_inbox_archive_supports_supersede_no_auto_tags_and_validate(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    source_dir = tmp_path / "knowledge" / "sources" / "web" / "agent-engineering"
    source_dir.mkdir(parents=True)
    (source_dir / "old.md").write_text(
        "---\n"
        "type: Source\n"
        "title: Same Source\n"
        "domain: agent-engineering\n"
        "topic: agent-harness\n"
        "tags: [agent-harness]\n"
        "status: active\n"
        "confidence: 0.1\n"
        "---\n"
        "# 摘要\n\nSame Source body.\n",
        encoding="utf-8",
    )
    _write_post(
        tmp_path,
        "web",
        "20260707-same-source",
        {
            "article.md": (
                "# Same Source\n\nSource URL: https://example.test/same\n\nSame Source body."
            )
        },
    )

    code = main(
        [
            "inbox",
            "--workspace",
            str(tmp_path),
            "archive",
            "20260707-same-source",
            "agent-engineering/agent-harness",
            "--summary",
            "Same Source body.",
            "--no-auto-tags",
            "--supersede-similar",
            "--validate",
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["tags"] == []
    assert payload["superseded"] == ["sources/web/agent-engineering/old.md"]
    assert "validation" in payload


def test_cli_knowledge_question_entity_promote_refresh_validate_gardener(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()
    main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "note-source",
            "--platform",
            "web",
            "--title",
            "Refresh Source",
            "--topic",
            "agent-engineering/agent-harness",
            "--resource",
            "https://example.test/refresh",
            "--summary",
            "Refresh source summary.",
            "--tag",
            "agent-harness",
        ]
    )
    capsys.readouterr()

    question_code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "add-question",
            "agent-engineering/agent-harness",
            "怎么刷新 topic？",
            "--answer",
            "汇总 active sources。",
            "--source-ref",
            "/sources/web/agent-engineering/refresh-source.md",
        ]
    )
    question_output = capsys.readouterr()
    entity_code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "add-entity",
            "agent-engineering/agent-harness",
            "Alcove",
            "--kind",
            "tool",
            "--summary",
            "个人知识库工具。",
            "--use-cases",
            "处理 inbox。",
        ]
    )
    entity_output = capsys.readouterr()
    promote_code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "promote",
            "sources/web/agent-engineering/refresh-source.md",
        ]
    )
    promote_output = capsys.readouterr()
    refresh_code = main(
        [
            "knowledge",
            "--workspace",
            str(tmp_path),
            "refresh",
            "agent-engineering/agent-harness",
        ]
    )
    refresh_output = capsys.readouterr()
    topics_code = main(["knowledge", "--workspace", str(tmp_path), "topics"])
    topics_output = capsys.readouterr()
    validate_code = main(["validate", "--workspace", str(tmp_path), "--json"])
    validate_output = capsys.readouterr()
    gardener_code = main(["gardener", "--workspace", str(tmp_path), "--json"])
    gardener_output = capsys.readouterr()

    assert question_code == 0
    assert "okf_question" in json.loads(question_output.out)
    assert entity_code == 0
    assert "okf_entity" in json.loads(entity_output.out)
    assert promote_code == 0
    assert "okf_concept" in json.loads(promote_output.out)
    assert refresh_code == 0
    assert json.loads(refresh_output.out)["status"] == "refreshed"
    assert topics_code == 0
    assert "agent-harness" in json.loads(topics_output.out)["topics"]
    assert validate_code in {0, 1}
    assert "issues" in json.loads(validate_output.out)
    assert gardener_code == 0
    assert "issues" in json.loads(gardener_output.out)
