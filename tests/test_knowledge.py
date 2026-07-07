from alcove.knowledge import KnowledgeModule, NoteSourceRequest, AddQuestionRequest, AddEntityRequest
from alcove.markdown import MarkdownRepository
from alcove.taxonomy import load_taxonomy, split_domain_topic
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

    repo = MarkdownRepository()
    source = repo.read_doc(result.source_path)
    concept = repo.read_doc(result.concept_path)
    topic = repo.read_doc(
        tmp_path / "knowledge" / "topics" / "agent-engineering" / "agent-harness.md"
    )
    tag = repo.read_doc(tmp_path / "knowledge" / "tags" / "agent-harness.md")
    index = repo.read_doc(tmp_path / "knowledge" / "index.md")

    assert source.frontmatter["type"] == "Source"
    assert source.frontmatter["platform"] == "xhs"
    assert source.frontmatter["published_date"] == "2026-07-06"
    assert source.frontmatter["legacy_path"] == "archive/agent-harness/demo"
    assert concept.frontmatter["type"] == "Knowledge Concept"
    assert concept.frontmatter["source_refs"] == [
        "/sources/xhs/agent-engineering/代码图谱怎么选.md"
    ]
    assert concept.frontmatter["legacy_paths"] == ["archive/agent-harness/demo"]
    assert topic.frontmatter["type"] == "Topic"
    assert topic.frontmatter["domain"] == "agent-engineering"
    assert tag.frontmatter["type"] == "Tag"
    assert tag.frontmatter["tag"] == "agent-harness"
    assert "- [Source] [代码图谱怎么选](sources/xhs/agent-engineering/代码图谱怎么选.md)" in index.body
    assert (
        "- [Knowledge Concept] [代码图谱怎么选]"
        "(concepts/agent-engineering/agent-harness/代码图谱怎么选.md)"
    ) in index.body


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

    repo = MarkdownRepository()
    question_doc = repo.read_doc(question.path)
    entity_doc = repo.read_doc(entity.path)
    index = repo.read_doc(tmp_path / "knowledge" / "index.md")

    assert question_doc.frontmatter["type"] == "Question"
    assert question_doc.frontmatter["question"] == "代码图谱工具怎么选？"
    assert question_doc.frontmatter["tags"] == ["code-intelligence"]
    assert entity_doc.frontmatter["type"] == "Entity"
    assert entity_doc.frontmatter["kind"] == "tool"
    assert entity_doc.frontmatter["tags"] == ["code-intelligence"]
    assert "- [Question] [代码图谱工具怎么选？]" in index.body
    assert "- [Entity] [CodeGraph](entities/tool/codegraph.md)" in index.body


def test_custom_taxonomy_domain_and_topic_entries_are_normalized(tmp_path):
    workspace = Workspace.init(tmp_path)
    (workspace.paths().knowledge / "taxonomy.yml").write_text(
        """
domains:
  AI Knowledge:
    title: AI Knowledge
    topics: [Cool Topic]
""".lstrip(),
        encoding="utf-8",
    )

    taxonomy = load_taxonomy(workspace.paths().knowledge)

    assert split_domain_topic("Cool Topic", taxonomy) == ("ai-knowledge", "cool-topic")
    assert split_domain_topic("AI Knowledge/Cool Topic", taxonomy) == (
        "ai-knowledge",
        "cool-topic",
    )


def test_note_source_reuses_existing_concept_and_appends_unique_provenance(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = KnowledgeModule(workspace)

    first = module.note_source(
        NoteSourceRequest(
            platform="xhs",
            title="Same Concept",
            topic="agent-engineering/agent-harness",
            resource="https://example.test/one",
            summary="First summary.",
            legacy_path="archive/one",
        )
    )
    second = module.note_source(
        NoteSourceRequest(
            platform="xhs",
            title="Same Concept",
            topic="agent-engineering/agent-harness",
            resource="https://example.test/two",
            summary="Second summary.",
            legacy_path="archive/two",
        )
    )

    concept_dir = tmp_path / "knowledge" / "concepts" / "agent-engineering" / "agent-harness"
    concept_paths = sorted(concept_dir.glob("same-concept*.md"))
    concept = MarkdownRepository().read_doc(concept_paths[0])

    assert first.concept_path == second.concept_path
    assert concept_paths == [concept_dir / "same-concept.md"]
    assert concept.frontmatter["source_refs"] == [
        "/sources/xhs/agent-engineering/same-concept.md",
        "/sources/xhs/agent-engineering/same-concept-2.md",
    ]
    assert concept.frontmatter["legacy_paths"] == ["archive/one", "archive/two"]
