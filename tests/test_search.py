import json
from datetime import date

import pytest

from alcove.errors import AlcoveError
from alcove.home import AlcoveHome
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.pins import AddPinRequest, PinsModule
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace
from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest


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

    assert any(
        {
            "root": "knowledge",
            "type": "Source",
            "title": "代码图谱",
            "topic": "agent-harness",
            "tags": ["code-intelligence"],
            "path": "sources/web/agent-engineering/代码图谱.md",
        }.items()
        <= row.items()
        for row in rows
    )
    json.dumps(rows, ensure_ascii=False)


def test_home_scoped_search_includes_registered_managed_knowledge_bases(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb = Workspace.init(tmp_path / "research_notes")
    home.register_knowledge_base("research_notes", kb.root)
    KnowledgeModule(kb).note_source(
        NoteSourceRequest(
            platform="web",
            title="OKF Managed KB",
            topic="ai-knowledge/knowledge-base",
            resource="https://example.test/okf",
            summary="OKF managed knowledge base search needle.",
            tags=["okf"],
        )
    )

    rows = SearchModule(home=home).search(SearchRequest(query="OKF", limit=10))

    assert any(
        {
            "root": "knowledge",
            "type": "Source",
            "title": "OKF Managed KB",
            "kb": "research_notes",
            "path": "knowledge-bases/research_notes/sources/web/ai-knowledge/okf-managed-kb.md",
        }.items()
        <= row.items()
        for row in rows
    )


def test_home_scoped_search_deduplicates_pin_summary_content(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(
        AddPinRequest(
            title="Repeated Pin",
            summary="Use Alcove search as candidate discovery.",
            content=(
                "Use Alcove search as candidate discovery.\n"
                "Then inspect OKF source refs and connector refs."
            ),
            kind="regular",
            tags=["okf"],
        )
    )

    rows = SearchModule(home=home).search(SearchRequest(query="candidate discovery", limit=10))

    row = next(row for row in rows if row["root"] == "pins")
    assert row["notes"].count("Use Alcove search as candidate discovery.") == 1
    assert "Then inspect OKF source refs and connector refs." in row["notes"]


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


def test_search_browse_modes_skip_infrastructure_docs_by_default(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    repo.write_doc(
        knowledge / "sources" / "web" / "source.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Source",
                "topic": "agent-harness",
                "tags": ["agent-harness"],
                "published_date": "2026-07-08",
            },
            body="# Source\n\nNeedle.\n",
        ),
    )
    for doc_type, path in [
        ("Tag", "tags/agent-harness.md"),
        ("Topic", "topics/agent-engineering/agent-harness.md"),
        ("Domain", "domains/agent-engineering.md"),
    ]:
        repo.write_doc(
            knowledge / path,
            MarkdownDoc(
                frontmatter={
                    "type": doc_type,
                    "title": doc_type,
                    "tags": ["taxonomy"],
                    "created_at": "2026-07-09",
                },
                body=f"# {doc_type}\n\nNeedle.\n",
            ),
        )

    module = SearchModule(workspace)

    assert [row["title"] for row in module.search(SearchRequest(query="needle"))] == ["Source"]
    assert module.tags() == [{"tag": "agent-harness", "count": 1}]
    assert [row["title"] for row in module.recent(10)] == ["Source"]
    assert [
        row["title"] for row in module.search(SearchRequest(query="needle", type_filter="Tag"))
    ] == ["Tag"]


def test_search_filters_github_star_connector_type(tmp_path):
    workspace = Workspace.init(tmp_path)
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopus/alcove",
                    "html_url": "https://github.com/octopus/alcove",
                    "description": "knowledge management",
                    "language": "Python",
                    "updated_at": "2026-07-10T00:00:00Z",
                }
            ]
        ),
        encoding="utf-8",
    )
    GitHubStarsConnector(workspace).import_export(
        GitHubStarsImportRequest(export_file=str(export_file))
    )

    rows = SearchModule(workspace).search(
        SearchRequest(query="knowledge", type_filter="GitHub Star")
    )

    assert [row["title"] for row in rows] == ["octopus/alcove"]
    assert rows[0]["display_id"] == "github-stars/octopus-alcove"
    assert rows[0]["date"] == "2026-07-10"
    assert rows[0]["source_id"] == "github-stars"
    assert rows[0]["source_label"] == "GitHub Stars · github / Python"
    assert rows[0]["origin_label"] == "GitHub Stars"
    assert rows[0]["fetch_ref"] == "connectors/github-stars#octopus/alcove"
    assert (
        rows[0]["fetch_command"]
        == "alcove connector fetch connectors/github-stars#octopus/alcove --json"
    )


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

    assert len(rows) == 1
    assert {
        "root": "knowledge",
        "type": "Source",
        "title": "untitled-doc",
        "topic": "topic",
        "tags": ["tag"],
        "path": "untitled-doc.md",
    }.items() <= rows[0].items()


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

    assert len(rows) == 1
    assert {
        "root": "knowledge",
        "type": "123",
        "title": "2026-07-07",
        "topic": "456",
        "tags": ["tag", "2026-07-08"],
        "path": "native-values.md",
    }.items() <= rows[0].items()
    json.dumps(rows, ensure_ascii=False)


def test_search_filters_by_platform_status_confidence_and_date(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    rows = [
        {
            "path": "match.md",
            "platform": "web",
            "status": "active",
            "confidence": 0.9,
            "published_date": "2026-07-07",
            "title": "Matching",
        },
        {
            "path": "wrong-platform.md",
            "platform": "x",
            "status": "active",
            "confidence": 0.9,
            "published_date": "2026-07-07",
            "title": "Wrong Platform",
        },
        {
            "path": "wrong-status.md",
            "platform": "web",
            "status": "superseded",
            "confidence": 0.9,
            "published_date": "2026-07-07",
            "title": "Wrong Status",
        },
        {
            "path": "low-confidence.md",
            "platform": "web",
            "status": "active",
            "confidence": 0.4,
            "published_date": "2026-07-07",
            "title": "Low Confidence",
        },
        {
            "path": "outside-date.md",
            "platform": "web",
            "status": "active",
            "confidence": 0.9,
            "published_date": "2026-06-30",
            "title": "Outside Date",
        },
        {
            "path": "missing-date.md",
            "platform": "web",
            "status": "active",
            "confidence": 0.9,
            "title": "Missing Date",
        },
    ]
    for item in rows:
        frontmatter = {
            "type": "Source",
            "title": item["title"],
            "topic": "agent-harness",
            "tags": ["agent-harness"],
            "platform": item["platform"],
            "status": item["status"],
            "confidence": item["confidence"],
        }
        if "published_date" in item:
            frontmatter["published_date"] = item["published_date"]
        repo.write_doc(
            knowledge / "sources" / "web" / item["path"],
            MarkdownDoc(frontmatter=frontmatter, body="# Source\n\nNeedle.\n"),
        )

    results = SearchModule(workspace).search(
        SearchRequest(
            query="needle",
            platform="web",
            status="active",
            min_confidence=0.8,
            date_from="2026-07-01",
            date_to="2026-07-31",
        )
    )

    assert [row["title"] for row in results] == ["Matching"]


def test_search_rows_include_lifecycle_dates_for_cleanup_decisions(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    repo.write_doc(
        knowledge / "sources" / "web" / "cleanup.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Cleanup Candidate",
                "topic": "agent-harness",
                "tags": ["cleanup"],
                "platform": "web",
                "status": "active",
                "published_date": "2026-06-01",
                "created_at": "2026-07-10T08:00:00+08:00",
                "updated_at": "2026-07-11T09:00:00+08:00",
            },
            body="# Source\n\nCleanup decision needle.\n",
        ),
    )

    rows = SearchModule(workspace).search(SearchRequest(query="needle"))

    assert rows[0]["published_at"] == "2026-06-01"
    assert rows[0]["collected_at"] == "2026-07-10T08:00:00+08:00"
    assert rows[0]["updated_at"] == "2026-07-11T09:00:00+08:00"
    assert rows[0]["deleted_at"] == ""


def test_search_prefers_active_records_without_hiding_explicit_status_filters(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    for title, status in [
        ("Review Candidate", "needs-review"),
        ("Superseded Candidate", "superseded"),
        ("Active Candidate", "active"),
    ]:
        repo.write_doc(
            knowledge / "sources" / "web" / f"{title.lower().replace(' ', '-')}.md",
            MarkdownDoc(
                frontmatter={
                    "type": "Source",
                    "title": title,
                    "topic": "agent-harness",
                    "tags": ["search"],
                    "platform": "web",
                    "status": status,
                },
                body="# Source\n\nCandidate ranking needle.\n",
            ),
        )

    default_results = SearchModule(workspace).search(SearchRequest(query="candidate"))
    review_results = SearchModule(workspace).search(
        SearchRequest(query="candidate", status="needs-review")
    )

    assert [row["title"] for row in default_results] == [
        "Active Candidate",
        "Review Candidate",
        "Superseded Candidate",
    ]
    assert [row["title"] for row in review_results] == ["Review Candidate"]


def test_search_hides_deleted_records_unless_status_is_explicit(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    for title, status in [
        ("Active Candidate", "active"),
        ("Deleted Candidate", "deleted"),
    ]:
        repo.write_doc(
            knowledge / "sources" / "web" / f"{title.lower().replace(' ', '-')}.md",
            MarkdownDoc(
                frontmatter={
                    "type": "Source",
                    "title": title,
                    "topic": "agent-harness",
                    "tags": ["cleanup"],
                    "platform": "web",
                    "status": status,
                },
                body="# Source\n\nCleanup candidate needle.\n",
            ),
        )

    default_results = SearchModule(workspace).search(SearchRequest(query="candidate"))
    deleted_results = SearchModule(workspace).search(
        SearchRequest(query="candidate", status="deleted")
    )

    assert [row["title"] for row in default_results] == ["Active Candidate"]
    assert [row["title"] for row in deleted_results] == ["Deleted Candidate"]


def test_tag_doctor_reports_normalized_tag_variants(tmp_path):
    workspace = Workspace.init(tmp_path)
    repo = MarkdownRepository()
    knowledge = workspace.paths().knowledge
    repo.write_doc(
        knowledge / "sources" / "web" / "english.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "English",
                "topic": "agent-harness",
                "tags": ["code-intelligence"],
            },
            body="# English\n",
        ),
    )
    repo.write_doc(
        knowledge / "sources" / "web" / "alias.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "title": "Alias",
                "topic": "agent-harness",
                "tags": ["代码图谱"],
            },
            body="# Alias\n",
        ),
    )

    rows = SearchModule(workspace).tag_doctor()

    assert rows == [
        {
            "canonical": "code-intelligence",
            "variants": ["code-intelligence", "代码图谱"],
            "count": 2,
        }
    ]
