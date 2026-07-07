import json

from alcove.classify import ClassifyModule
from alcove.gardener import GardenerModule
from alcove.inbox import InboxModule, InboxNoteRequest
from alcove.knowledge import AddConceptRequest, AddEntityRequest, AddQuestionRequest, KnowledgeModule
from alcove.lifecycle import LifecycleModule, score_confidence
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.validate import ValidateModule
from alcove.workspace import Workspace


def _write_post(root, platform, name, content):
    folder = root / "inbox" / platform / name
    folder.mkdir(parents=True)
    (folder / "post.md").write_text(content, encoding="utf-8")
    return folder


def test_classify_suggests_topic_tags_summary_and_confidence(tmp_path):
    workspace = Workspace.init(tmp_path)
    (tmp_path / "knowledge" / "tags").mkdir(parents=True)
    MarkdownRepository().write_doc(
        tmp_path / "knowledge" / "tags" / "code-intelligence.md",
        MarkdownDoc({"type": "Tag", "tag": "code-intelligence"}, "# code-intelligence\n"),
    )
    _write_post(
        tmp_path,
        "web",
        "20260707-post",
        "# CodeGraph\n\nSource URL: https://example.test\n\n代码图谱需要验证调用路径和索引准确性。",
    )

    draft = ClassifyModule(workspace).classify("20260707-post", "agent-engineering/agent-harness")

    assert draft.topic == "agent-harness"
    assert draft.domain == "agent-engineering"
    assert "agent-harness" in draft.suggested_tags
    assert "agent-engineering-agent-harness" not in draft.suggested_tags
    assert draft.draft_summary
    assert 0 <= draft.confidence <= 1


def test_inbox_note_writes_human_notes_confidence_and_supersedes_similar_source(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    old_source = tmp_path / "knowledge" / "sources" / "web" / "agent-engineering" / "old.md"
    repo.write_doc(
        old_source,
        MarkdownDoc(
            {
                "type": "Source",
                "title": "Same Thing",
                "domain": "agent-engineering",
                "topic": "agent-harness",
                "tags": ["agent-harness"],
                "status": "active",
                "confidence": 0.1,
            },
            "# 摘要\n\nSame Thing repeated evidence.\n",
        ),
    )
    _write_post(
        tmp_path,
        "web",
        "20260707-new",
        "# Same Thing\n\nSource URL: https://example.test\n\nSame Thing repeated evidence with 123 numbers.",
    )

    result = InboxModule(workspace).note(
        InboxNoteRequest(
            name="20260707-new",
            topic="agent-engineering/agent-harness",
            summary="Same Thing repeated evidence.",
            selected_takeaways=["1", "2"],
            why="值得验证。",
            connection="连接到知识库迁移。",
            action="补测试。",
            personal_note="我的判断。",
            supersede_similar=True,
        )
    )

    source = repo.read_doc(result.source_path)
    concept = repo.read_doc(result.concept_path)
    old = repo.read_doc(old_source)

    assert source.frontmatter["status"] == "active"
    assert "confidence" in source.frontmatter
    assert old.frontmatter["status"] == "superseded"
    assert "我的判断" in concept.body
    assert "值得验证" in concept.body
    assert result.superseded == ["sources/web/agent-engineering/old.md"]


def test_lifecycle_refresh_topic_creates_new_concept_and_supersedes_old(tmp_path):
    workspace = Workspace.init(tmp_path)
    knowledge = KnowledgeModule(workspace)
    knowledge.add_concept(
        AddConceptRequest(
            topic="agent-engineering/agent-harness",
            title="Old Concept",
            summary="Old summary.",
            tags=["agent-harness"],
        )
    )
    repo = MarkdownRepository()
    repo.write_doc(
        tmp_path / "knowledge" / "sources" / "web" / "agent-engineering" / "source.md",
        MarkdownDoc(
            {
                "type": "Source",
                "title": "Source",
                "domain": "agent-engineering",
                "topic": "agent-harness",
                "tags": ["agent-harness"],
                "status": "active",
                "confidence": 0.8,
            },
            "# 摘要\n\nFresh source summary.\n",
        ),
    )

    result = LifecycleModule(workspace).refresh_topic("agent-engineering/agent-harness")

    assert result["status"] == "refreshed"
    assert result["source_refs"] == ["/sources/web/agent-engineering/source.md"]
    assert result["superseded"]


def test_validate_and_gardener_report_issues(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    repo.write_doc(
        tmp_path / "knowledge" / "concepts" / "broken.md",
        MarkdownDoc(
            {
                "type": "Knowledge Concept",
                "title": "Broken",
                "topic": "agent-harness",
                "source_refs": ["/sources/missing.md"],
            },
            "# Broken\n",
        ),
    )
    repo.write_doc(
        tmp_path / "knowledge" / "tags" / "unused.md",
        MarkdownDoc({"type": "Tag", "tag": "unused"}, "# unused\n"),
    )

    validation = ValidateModule(workspace).validate(strict_quality=True)
    report = GardenerModule(workspace).gardener()

    assert any(issue["kind"] == "dead_source_ref" for issue in validation)
    assert any(issue["kind"] == "empty_tag" for issue in report.issues)


def test_question_entity_and_concept_support_source_refs(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = KnowledgeModule(workspace)

    question = module.add_question(
        AddQuestionRequest(
            topic="agent-engineering/agent-harness",
            question="怎么选代码图谱？",
            answer="看索引准确性。",
            source_refs=["sources/web/a.md"],
        )
    )
    entity = module.add_entity(
        AddEntityRequest(
            topic="agent-engineering/agent-harness",
            name="CodeGraph",
            kind="tool",
            summary="代码图谱工具。",
            use_cases="分析调用路径。",
            open_questions="索引刷新策略？",
            source_refs=["/sources/web/a.md"],
        )
    )

    assert MarkdownRepository().read_doc(question.path).frontmatter["source_refs"] == ["/sources/web/a.md"]
    assert "分析调用路径" in MarkdownRepository().read_doc(entity.path).body
    json.dumps({"question": str(question.path), "entity": str(entity.path)}, ensure_ascii=False)
