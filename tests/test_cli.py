import json

from alcove.cli import main


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
            "summary.md": "# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要",
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
