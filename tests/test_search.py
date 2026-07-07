import json
from datetime import date

import pytest

from alcove.errors import AlcoveError
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def test_search_finds_knowledge_doc_by_body_text_from_note_source(tmp_path):
    workspace = Workspace.init(tmp_path)
    KnowledgeModule(workspace).note_source(
        NoteSourceRequest(
            platform="web",
            title="代码图谱",
            topic="agent-engineering/agent-harness",
            resource="https://example.test/code-map",
            summary="复杂系统里要先看清调用路径，再决定怎么拆模块。",
            tags=["code-intelligence"],
        )
    )

    rows = SearchModule(workspace).search(SearchRequest(query="调用路径"))

    assert {
        "root": "knowledge",
        "type": "Source",
        "title": "代码图谱",
        "topic": "agent-harness",
        "tags": ["code-intelligence"],
        "path": "sources/web/agent-engineering/代码图谱.md",
    } in rows
    json.dumps(rows, ensure_ascii=False)


def test_search_module_reports_invalid_taxonomy_domain_definition(tmp_path):
    workspace = Workspace.init(tmp_path)
    (workspace.paths().knowledge / "taxonomy.yml").write_text(
        """
domains:
  bad-domain: [not, a, mapping]
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(AlcoveError) as exc_info:
        SearchModule(workspace)

    message = str(exc_info.value)
    assert str(workspace.paths().knowledge / "taxonomy.yml") in message
    assert "domains.bad-domain" in message


def test_search_filters_by_type_tag_and_topic(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    repo.write_doc(
        knowledge / "sources" / "web" / "matching.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Matching",
                "topic": "agent-harness",
                "tags": ["code-intelligence", "search"],
            },
            body="# Matching\n\nNeedle body.\n",
        ),
    )
    repo.write_doc(
        knowledge / "concepts" / "wrong-type.md",
        MarkdownDoc(
            frontmatter={
                "type": "Knowledge Concept",
                "title": "Wrong Type",
                "topic": "agent-harness",
                "tags": ["code-intelligence", "search"],
            },
            body="# Wrong Type\n\nNeedle body.\n",
        ),
    )
    repo.write_doc(
        knowledge / "sources" / "web" / "wrong-tag.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Wrong Tag",
                "topic": "agent-harness",
                "tags": ["other"],
            },
            body="# Wrong Tag\n\nNeedle body.\n",
        ),
    )
    repo.write_doc(
        knowledge / "sources" / "web" / "wrong-topic.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Wrong Topic",
                "topic": "other-topic",
                "tags": ["code-intelligence", "search"],
            },
            body="# Wrong Topic\n\nNeedle body.\n",
        ),
    )

    rows = SearchModule(workspace).search(
        SearchRequest(
            query="needle",
            type_filter="Source",
            tag="search",
            topic="agent-harness",
        )
    )

    assert [row["title"] for row in rows] == ["Matching"]


def test_search_normalizes_tag_and_domain_topic_filters(tmp_path):
    workspace = Workspace.init(tmp_path)
    KnowledgeModule(workspace).note_source(
        NoteSourceRequest(
            platform="web",
            title="Normalized Filters",
            topic="agent-engineering/agent-harness",
            resource="https://example.test/normalized-filters",
            summary="Needle body.",
            tags=["code-intelligence"],
            create_concept=False,
        )
    )

    rows = SearchModule(workspace).search(
        SearchRequest(
            query="needle",
            tag="代码图谱",
            topic="agent-engineering/agent-harness",
        )
    )

    assert [row["title"] for row in rows] == ["Normalized Filters"]


def test_search_domain_topic_filter_respects_domain_when_topics_share_slug(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    repo.write_doc(
        knowledge / "agent-shared.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Agent Shared",
                "domain": "agent-engineering",
                "topic": "shared",
                "tags": [],
            },
            body="# Agent Shared\n",
        ),
    )
    repo.write_doc(
        knowledge / "software-shared.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Software Shared",
                "domain": "software-engineering",
                "topic": "shared",
                "tags": [],
            },
            body="# Software Shared\n",
        ),
    )

    domain_rows = SearchModule(workspace).search(
        SearchRequest(query="", topic="agent-engineering/shared")
    )
    topic_rows = SearchModule(workspace).search(SearchRequest(query="", topic="shared"))

    assert [row["title"] for row in domain_rows] == ["Agent Shared"]
    assert [row["title"] for row in topic_rows] == ["Agent Shared", "Software Shared"]


def test_search_empty_query_matches_all_docs_subject_to_limit_and_skips_reserved_docs(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    repo.write_doc(
        knowledge / "index.md",
        MarkdownDoc(frontmatter={"type": "Index", "title": "Index"}, body="# Index\n"),
    )
    repo.write_doc(
        knowledge / "log.md",
        MarkdownDoc(frontmatter={"type": "Log", "title": "Log"}, body="# Log\n"),
    )
    for title in ["One", "Two", "Three"]:
        repo.write_doc(
            knowledge / f"{title.lower()}.md",
            MarkdownDoc(
                frontmatter={"type": "Source", "title": title, "topic": "topic", "tags": []},
                body=f"# {title}\n",
            ),
        )

    rows = SearchModule(workspace).search(SearchRequest(query="", limit=2))

    assert [row["title"] for row in rows] == ["One", "Three"]
    assert len(rows) == 2
    assert "Index" not in [row["title"] for row in rows]
    assert "Log" not in [row["title"] for row in rows]
    assert SearchModule(workspace).search(SearchRequest(query="", limit=0)) == []


def test_search_uses_path_stem_when_title_missing_and_skips_docs_without_path(tmp_path):
    workspace = Workspace.init(tmp_path)

    class PathlessRepository(MarkdownRepository):
        def list_docs(self, root, type_filter=None):
            return [
                MarkdownDoc(
                    frontmatter={"type": "Source", "topic": "topic", "tags": ["tag"]},
                    body="Needle",
                    path=workspace.paths().knowledge / "untitled-doc.md",
                ),
                MarkdownDoc(
                    frontmatter={"type": "Source", "title": "Pathless", "tags": ["tag"]},
                    body="Needle",
                    path=None,
                ),
            ]

    rows = SearchModule(workspace, repo=PathlessRepository()).search(SearchRequest(query="needle"))

    assert rows == [
        {
            "root": "knowledge",
            "type": "Source",
            "title": "untitled-doc",
            "topic": "topic",
            "tags": ["tag"],
            "path": "untitled-doc.md",
        }
    ]


def test_search_rows_coerce_frontmatter_values_to_json_safe_schema(tmp_path):
    workspace = Workspace.init(tmp_path)

    class NativeValueRepository(MarkdownRepository):
        def list_docs(self, root, type_filter=None):
            return [
                MarkdownDoc(
                    frontmatter={
                        "type": 123,
                        "title": date(2026, 7, 7),
                        "topic": 456,
                        "tags": ["tag", date(2026, 7, 8)],
                    },
                    body="Needle",
                    path=workspace.paths().knowledge / "native-values.md",
                )
            ]

    rows = SearchModule(workspace, repo=NativeValueRepository()).search(
        SearchRequest(query="needle")
    )

    assert rows == [
        {
            "root": "knowledge",
            "type": "123",
            "title": "2026-07-07",
            "topic": "456",
            "tags": ["tag", "2026-07-08"],
            "path": "native-values.md",
        }
    ]
    json.dumps(rows, ensure_ascii=False)
