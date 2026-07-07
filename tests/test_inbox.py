from __future__ import annotations

import pytest

from alcove.inbox import InboxModule, InboxNoteRequest
from alcove.markdown import MarkdownRepository
from alcove.workspace import Workspace


class RaisingKnowledge:
    def note_source(self, request):
        raise RuntimeError("knowledge write failed")


def _write_post(root, platform, name, files):
    folder = root / "inbox" / platform / name
    folder.mkdir(parents=True)
    for filename, content in files.items():
        (folder / filename).write_text(content, encoding="utf-8")
    return folder


def _write_xhs_post(root, name):
    return _write_post(
        root,
        "xhs",
        name,
        {
            "post.md": "# short\n\n#tag",
            "summary.md": "# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要",
        },
    )


def test_xhs_prefers_summary_over_sparse_post(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260707-new")

    post = InboxModule(workspace).read("20260707-new")

    assert post.title == "代码图谱怎么选"
    assert post.content_source == "summary.md"
    assert post.content == "# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要"


def test_peek_returns_oldest_across_platforms(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260707-new")
    _write_post(tmp_path, "wechat", "no-date", {"article.md": "# No Date\n\nbody"})
    _write_post(tmp_path, "web", "20260706-old", {"article.md": "# Old\n\nbody"})

    post = InboxModule(workspace).peek()

    assert post is not None
    assert post.name == "20260706-old"
    assert post.platform == "web"


def test_peek_returns_none_when_inbox_empty(tmp_path):
    workspace = Workspace.init(tmp_path)

    assert InboxModule(workspace).peek() is None


def test_read_extracts_title_source_date_and_content_source(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "wechat",
        "20260706-old",
        {
            "article.md": (
                "intro\n"
                "# Extracted Title\n\n"
                "Source URL: https://example.test/source\n\n"
                "Body"
            )
        },
    )

    post = InboxModule(workspace).read("20260706-old")

    assert post.title == "Extracted Title"
    assert post.source == "https://example.test/source"
    assert post.date == "2026-07-06"
    assert post.content_source == "article.md"


def test_note_moves_post_to_archive_writes_source_concept_and_records_legacy_path(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260706-old")
    module = InboxModule(workspace)

    result = module.note(
        InboxNoteRequest(
            name="20260706-old",
            topic="agent-engineering/agent-harness",
            summary="代码图谱选型要看索引准确性和 Agent 是否实际使用。",
            tags=["agent-harness", "code-intelligence"],
        )
    )

    assert result.archive_path == tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old"
    assert result.archive_path.is_dir()
    assert not (tmp_path / "inbox" / "xhs" / "20260706-old").exists()
    assert result.source_path.is_file()
    assert result.concept_path is not None
    assert result.concept_path.is_file()

    repo = MarkdownRepository()
    source = repo.read_doc(result.source_path)
    concept = repo.read_doc(result.concept_path)
    assert source.frontmatter["resource"] == "https://example.test/xhs"
    assert source.frontmatter["legacy_path"] == "archive/agent-harness/[xhs] 20260706-old"
    assert concept.frontmatter["legacy_paths"] == [
        "archive/agent-harness/[xhs] 20260706-old"
    ]


def test_archive_source_only_uses_fallback_content_when_summary_blank(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "x",
        "20260705-post",
        {"post.md": "# Source Only\n\nPlain body with https://example.test/fallback"},
    )

    result = InboxModule(workspace).archive(
        "20260705-post",
        "agent-engineering/agent-harness",
        tags=["code-intelligence"],
    )

    assert result.concept_path is None
    source = MarkdownRepository().read_doc(result.source_path)
    assert source.frontmatter["resource"] == "https://example.test/fallback"
    assert source.body == "# Source Only\n\n# Source Only\n\nPlain body with https://example.test/fallback\n"


def test_archive_uses_archived_path_as_resource_when_source_missing(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(tmp_path, "web", "20260704-nosource", {"article.md": "# No Source\n\nBody"})

    result = InboxModule(workspace).archive(
        "20260704-nosource",
        "agent-engineering/agent-harness",
        summary="Manual summary.",
    )

    source = MarkdownRepository().read_doc(result.source_path)
    assert source.frontmatter["resource"] == "archive/agent-harness/[web] 20260704-nosource"


def test_archive_destination_collision_gets_numeric_suffix(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260706-old")
    collision = tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old"
    collision.mkdir(parents=True)

    result = InboxModule(workspace).archive(
        "20260706-old",
        "agent-engineering/agent-harness",
        summary="Manual summary.",
    )

    assert result.archive_path == tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old-2"
    assert result.archive_path.is_dir()
    assert collision.is_dir()


def test_note_rolls_back_archive_move_when_knowledge_write_fails(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260706-old")
    archive_path = tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old"

    with pytest.raises(RuntimeError, match="knowledge write failed"):
        InboxModule(workspace, knowledge=RaisingKnowledge()).note(
            InboxNoteRequest(
                name="20260706-old",
                topic="agent-engineering/agent-harness",
                summary="Summary.",
            )
        )

    assert (tmp_path / "inbox" / "xhs" / "20260706-old").is_dir()
    assert not archive_path.exists()


def test_platform_name_identifier_disambiguates_duplicate_folder_names(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(tmp_path, "web", "20260706-same", {"article.md": "# Web Post\n\nBody"})
    _write_post(tmp_path, "x", "20260706-same", {"post.md": "# X Post\n\nBody"})

    with pytest.raises(ValueError, match="Ambiguous inbox item.*platform/name"):
        InboxModule(workspace).archive(
            "20260706-same",
            "agent-engineering/agent-harness",
            summary="Manual summary.",
        )

    result = InboxModule(workspace).archive(
        "x/20260706-same",
        "agent-engineering/agent-harness",
        summary="Manual summary.",
    )

    assert result.archive_path == tmp_path / "archive" / "agent-harness" / "[x] 20260706-same"
    assert result.archive_path.is_dir()
    assert (tmp_path / "inbox" / "web" / "20260706-same").is_dir()
    assert not (tmp_path / "inbox" / "x" / "20260706-same").exists()


def test_missing_content_file_raises_file_not_found(tmp_path):
    workspace = Workspace.init(tmp_path)
    (tmp_path / "inbox" / "xhs" / "20260706-empty").mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        InboxModule(workspace).read("20260706-empty")
