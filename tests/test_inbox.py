from alcove.inbox import InboxModule, InboxNoteRequest
from alcove.workspace import Workspace


def _write_xhs_post(root, name):
    folder = root / "inbox" / "xhs" / name
    folder.mkdir(parents=True)
    (folder / "post.md").write_text("# short\n\n#tag", encoding="utf-8")
    (folder / "summary.md").write_text(
        "# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要",
        encoding="utf-8",
    )
    return folder


def test_peek_returns_oldest_and_prefers_xhs_summary(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260707-new")
    _write_xhs_post(tmp_path, "20260706-old")

    post = InboxModule(workspace).peek()

    assert post is not None
    assert post.name == "20260706-old"
    assert post.title == "代码图谱怎么选"
    assert post.content_source == "summary.md"
    assert post.source == "https://example.test/xhs"


def test_note_moves_post_to_archive_and_writes_knowledge(tmp_path):
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

    assert result.archive_path.is_dir()
    assert not (tmp_path / "inbox" / "xhs" / "20260706-old").exists()
    assert result.source_path.is_file()
    assert result.concept_path is not None
    assert result.concept_path.is_file()
