import json

from alcove.cli import build_parser, main


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
            "summary.md": (
                "# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要"
            ),
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
    assert any(check["name"] == "workspace" for check in payload["checks"])


def test_cli_parser_accepts_serve_mcp_command(tmp_path):
    args = build_parser().parse_args(
        ["serve", "--mcp", "--workspace", str(tmp_path)]
    )

    assert args.command == "serve"
    assert args.mcp is True
    assert args.workspace == str(tmp_path)


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
    assert payload["content_source"] == "summary.md"


def test_cli_inbox_empty_prints_message(tmp_path, capsys):
    main(["init", str(tmp_path)])
    capsys.readouterr()

    code = main(["inbox", "--workspace", str(tmp_path), "peek"])
    captured = capsys.readouterr()

    assert code == 0
    assert captured.out.strip() == "Inbox is empty."


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
    assert any(
        issue["kind"] == "dead_source_ref"
        for issue in json.loads(captured.out)["issues"]
    )


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
            "--description",
            "Use Alcove for durable personal notes.",
            "--tag",
            "personal-notes",
            "--priority",
            "high",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    list_code = main(
        ["pin", "--workspace", str(tmp_path), "list", "--tag", "personal-notes", "--json"]
    )
    list_output = capsys.readouterr()
    search_code = main(
        ["search", "durable", "--workspace", str(tmp_path), "--json"]
    )
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
    assert list_code == 0
    assert json.loads(list_output.out)[0]["title"] == "Pinned Snippet"
    assert search_code == 0
    assert json.loads(search_output.out)[0]["root"] == "pins"
    assert archive_code == 0
    assert json.loads(archive_output.out)["status"] == "archived"


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

    assert index_code == 0
    assert json.loads(index_output.out)["scanned"] == 1
    assert search_code == 0
    assert json.loads(search_output.out)[0]["type"] == "Apple Note"


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
                "# Same Source\n\n"
                "Source URL: https://example.test/same\n\n"
                "Same Source body."
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
