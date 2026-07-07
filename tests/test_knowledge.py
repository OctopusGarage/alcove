from alcove.knowledge import KnowledgeModule, NoteSourceRequest, AddQuestionRequest, AddEntityRequest
from alcove.workspace import Workspace


def test_note_source_writes_source_concept_and_indexes(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = KnowledgeModule(workspace)

    result = module.note_source(
        NoteSourceRequest(
            platform="xhs",
            title="代码图谱怎么选",
            topic="agent-engineering/agent-harness",
            resource="https://example.test/post",
            summary="代码图谱选型要验证索引准确性、Agent 是否调用图谱、修改后是否刷新。",
            tags=["agent-harness", "code-intelligence"],
            published_date="2026-07-06",
            legacy_path="archive/agent-harness/demo",
        )
    )

    assert result.source_path.is_file()
    assert result.concept_path is not None
    assert result.concept_path.is_file()
    assert (tmp_path / "knowledge" / "topics" / "agent-engineering" / "agent-harness.md").is_file()
    assert (tmp_path / "knowledge" / "tags" / "agent-harness.md").is_file()
    assert (tmp_path / "knowledge" / "index.md").is_file()


def test_add_question_and_entity(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = KnowledgeModule(workspace)

    question = module.add_question(
        AddQuestionRequest(
            topic="agent-engineering/agent-harness",
            question="代码图谱工具怎么选？",
            answer="先验证索引准确性、Agent 调用率、刷新及时性和权限边界。",
            tags=["code-intelligence"],
        )
    )
    entity = module.add_entity(
        AddEntityRequest(
            topic="agent-engineering/agent-harness",
            name="CodeGraph",
            kind="tool",
            summary="面向 coding agent 的代码图谱工具。",
            tags=["code-intelligence"],
        )
    )

    assert question.path.is_file()
    assert entity.path.is_file()
    assert "type: Question" in question.path.read_text(encoding="utf-8")
    assert "type: Entity" in entity.path.read_text(encoding="utf-8")
