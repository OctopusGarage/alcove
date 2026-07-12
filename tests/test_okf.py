from __future__ import annotations

import pytest

from alcove.okf import OkfDocumentFactory, require_okf_frontmatter


def test_okf_document_factory_outputs_frontmatter_that_satisfies_type_rules():
    factory = OkfDocumentFactory(now="2026-07-08T00:00:00+00:00")

    source = factory.source_doc(
        title="Source",
        platform="web",
        resource="https://example.test/source",
        domain="agent-engineering",
        topic="agent-harness",
        tags=["agent-harness"],
        status="active",
        summary="Source summary.",
    )
    concept = factory.concept_doc(
        title="Concept",
        domain="agent-engineering",
        topic="agent-harness",
        tags=["agent-harness"],
        source_refs=["/sources/web/source.md"],
        status="active",
        summary="Concept summary.",
    )

    require_okf_frontmatter(source.frontmatter)
    require_okf_frontmatter(concept.frontmatter)
    assert source.frontmatter["schema"] == "alcove/source/v1"
    assert concept.frontmatter["schema"] == "alcove/knowledge-concept/v1"
    assert "## 摘要\n\nConcept summary." in concept.body
    assert "## 要点\n\nConcept summary." not in concept.body
    assert "## 来源" not in concept.body


def test_concept_doc_keeps_structured_key_points_and_non_empty_source_sections():
    factory = OkfDocumentFactory(now="2026-07-08T00:00:00+00:00")

    concept = factory.concept_doc(
        title="Concept",
        domain="agent-engineering",
        topic="agent-harness",
        tags=["agent-harness"],
        source_refs=["/sources/web/source.md"],
        status="active",
        summary="Summary.\n\n- First point\n- Second point",
        legacy_paths=["archive/item"],
    )

    assert "## 要点\n\n- First point\n- Second point" in concept.body
    assert "## 关系\n\n- [/sources/web/source.md](/sources/web/source.md)" in concept.body
    assert "## 来源\n\n- `archive/item`" in concept.body


def test_require_okf_frontmatter_reports_missing_required_fields():
    with pytest.raises(ValueError) as exc_info:
        require_okf_frontmatter({"type": "Source", "title": "Incomplete"})

    message = str(exc_info.value)
    assert "Source frontmatter missing required fields" in message
    assert "platform" in message
    assert "resource" in message
