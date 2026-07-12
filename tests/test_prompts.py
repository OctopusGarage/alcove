from __future__ import annotations

import json

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.search import SearchModule, SearchRequest


def test_prompt_save_writes_okf_markdown_and_gets_full_content(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)

    result = module.save(
        AddPromptRequest(
            title="Code Review Lens",
            content="Review for correctness, regressions, and missing tests.",
            description="Reusable code review prompt.",
            tags=["review", "quality"],
            use_cases=["PR review", "architecture review"],
            source_refs=["pins/review-principles.md"],
        )
    )
    doc = MarkdownRepository().read_doc(result.path)
    prompt = module.get("code-review-lens")

    assert result.path == home.paths().prompts / "code-review-lens.md"
    assert doc.frontmatter["type"] == "Prompt"
    assert doc.frontmatter["schema"] == "okf/prompt/v1"
    assert doc.frontmatter["title"] == "Code Review Lens"
    assert doc.frontmatter["status"] == "active"
    assert doc.frontmatter["tags"] == ["quality", "review"]
    assert doc.frontmatter["source_refs"] == ["/pins/review-principles.md"]
    assert doc.frontmatter["use_cases"] == ["PR review", "architecture review"]
    assert "## Prompt" in doc.body
    assert prompt.content == "Review for correctness, regressions, and missing tests."
    assert result.index_path == home.paths().prompts / "index.json"
    index = json.loads(result.index_path.read_text(encoding="utf-8"))
    assert index["schema"] == "alcove/prompts-index/v1"
    assert index["count"] == 1
    assert index["prompts"][0]["schema"] == "okf/prompt/v1"
    assert index["prompts"][0]["path"] == "prompts/code-review-lens.md"
    assert "missing tests" in index["prompts"][0]["search_text"]


def test_prompt_search_tags_and_archive(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    module.save(
        AddPromptRequest(
            title="Bug Hunt",
            content="Find the root cause before patching.",
            tags=["debug"],
        )
    )
    module.save(
        AddPromptRequest(
            title="Writing Shape",
            content="Shape fragments into a clear article.",
            tags=["writing"],
        )
    )

    debug_prompts = module.search(query="root cause", tag="debug")
    tags = module.tags()
    archived = module.archive("bug-hunt", confirm=True)
    active_after_archive = module.search(query="")

    assert [prompt.title for prompt in debug_prompts] == ["Bug Hunt"]
    assert tags == [{"tag": "debug", "count": 1}, {"tag": "writing", "count": 1}]
    assert archived["status"] == "archived"
    assert [prompt.title for prompt in active_after_archive] == ["Writing Shape"]


def test_prompt_save_infers_use_cases_when_omitted(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)

    result = module.save(
        AddPromptRequest(
            title="Debug Root Cause",
            content="Diagnose the failure before patching.",
            description="Find the root cause of a bug.",
            tags=["debug"],
        )
    )

    doc = MarkdownRepository().read_doc(result.path)
    prompt = module.get("debug-root-cause")

    assert doc.frontmatter["use_cases"] == ["Debugging"]
    assert prompt.use_cases == ["Debugging"]


def test_search_includes_active_prompts(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Review Prompt",
            content="Check edge cases and missing tests.",
            tags=["review"],
        )
    )

    rows = SearchModule(home=home).search(SearchRequest(query="edge cases", type_filter="Prompt"))

    assert rows[0]["root"] == "prompts"
    assert rows[0]["type"] == "Prompt"
    assert rows[0]["title"] == "Review Prompt"
    assert rows[0]["tags"] == ["review"]
    assert rows[0]["path"] == "prompts/review-prompt.md"


def test_prompt_search_rebuilds_stale_index_from_okf_markdown(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = PromptsModule(home=home)
    path = home.paths().prompts / "manual-prompt.md"
    MarkdownRepository().write_doc(
        path,
        MarkdownDoc(
            frontmatter={
                "type": "Prompt",
                "schema": "okf/prompt/v1",
                "title": "Manual Prompt",
                "description": "Manual prompt description.",
                "tags": ["manual"],
                "status": "active",
                "use_cases": ["manual testing"],
                "source_refs": [],
                "created_at": "2026-07-09T00:00:00+00:00",
                "updated_at": "2026-07-09T00:00:00+00:00",
            },
            body="# Manual Prompt\n\n## Prompt\n\nFind manual index needle.\n",
        ),
    )

    matches = module.search("manual index needle")
    index = json.loads((home.paths().prompts / "index.json").read_text(encoding="utf-8"))

    assert [prompt.title for prompt in matches] == ["Manual Prompt"]
    assert index["count"] == 1
    assert index["prompts"][0]["id"] == "manual-prompt"


def test_prompt_rebuild_index_rejects_non_okf_prompt_markdown(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    path = home.paths().prompts / "broken.md"
    path.write_text(
        "---\ntype: Prompt\ntitle: Broken\n---\n# Broken\n\n## Prompt\n\nMissing schema.\n",
        encoding="utf-8",
    )

    try:
        PromptsModule(home=home).rebuild_index()
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected invalid prompt frontmatter to fail index rebuild")

    assert "missing required fields" in message
    assert "schema" in message
