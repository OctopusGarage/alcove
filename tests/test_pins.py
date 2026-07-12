from __future__ import annotations

from alcove.markdown import MarkdownRepository
from alcove.pins import AddPinRequest, PinsModule, UpdatePinRequest
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def test_pin_add_writes_markdown_pin_and_lists_active_pins(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = PinsModule(workspace)

    result = module.add(
        AddPinRequest(
            title="Japanese Edge Launcher",
            summary="Launch Edge with TZ=Asia/Tokyo for region-sensitive tests.",
            content="Use osacompile to wrap the command and keep the original Edge profile.",
            kind="regular",
            tags=["app-launcher", "edge"],
            priority="high",
            source_refs=["/sources/web/edge.md"],
            resources=["https://example.test/edge-launcher"],
        )
    )

    doc = MarkdownRepository().read_doc(result.path)
    pins = module.list()

    assert result.path == tmp_path / "pins" / "japanese-edge-launcher.md"
    assert doc.frontmatter["type"] == "Pin"
    assert doc.frontmatter["schema"] == "okf/pin/v1"
    assert doc.frontmatter["title"] == "Japanese Edge Launcher"
    assert doc.frontmatter["kind"] == "regular"
    assert doc.frontmatter["summary"] == (
        "Launch Edge with TZ=Asia/Tokyo for region-sensitive tests."
    )
    assert doc.frontmatter["content_format"] == "text"
    assert doc.frontmatter["status"] == "active"
    assert doc.frontmatter["priority"] == "high"
    assert doc.frontmatter["tags"] == ["app-launcher", "edge"]
    assert doc.frontmatter["source_refs"] == ["/sources/web/edge.md"]
    assert doc.frontmatter["resources"] == ["https://example.test/edge-launcher"]
    assert "## Content\n\nUse osacompile" in doc.body
    assert pins[0].title == "Japanese Edge Launcher"
    assert pins[0].kind == "regular"
    assert pins[0].content.startswith("Use osacompile")


def test_pin_list_filters_by_tag_and_archive_requires_confirmation(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = PinsModule(workspace)
    first = module.add(
        AddPinRequest(
            title="Pinned Command",
            description="uv run pytest -q",
            tags=["testing"],
        )
    )
    module.add(
        AddPinRequest(
            title="Pinned Thought",
            description="Keep capture separate from knowledge management.",
            tags=["architecture"],
        )
    )

    preview = module.archive("pinned-command")
    testing_pins = module.list(tag="testing")
    archived = module.archive("pinned-command", confirm=True)
    active_after_archive = module.list()

    assert preview == {
        "status": "preview",
        "path": str(first.path),
        "confirm_required": True,
    }
    assert [pin.title for pin in testing_pins] == ["Pinned Command"]
    assert archived["status"] == "archived"
    assert [pin.title for pin in active_after_archive] == ["Pinned Thought"]
    assert (tmp_path / "pins" / "index.json").is_file()
    assert (tmp_path / "pins" / "index.md").is_file()


def test_pin_get_update_search_and_rebuild_index(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = PinsModule(workspace)
    module.add(
        AddPinRequest(
            title="Future MCP Drill",
            summary="Try a deeper MCP connector workflow later.",
            content="Read the connector contract and test lazy fetch against local data.",
            kind="todo",
            tags=["mcp", "connector"],
            priority="low",
        )
    )

    updated = module.update(
        UpdatePinRequest(
            pin_id="future-mcp-drill",
            priority="high",
            content="Practice connector lazy fetch and write down edge cases.",
            tags=["mcp", "practice"],
        )
    )
    fetched = module.get("future-mcp-drill")
    results = module.search(query="lazy fetch", kind="todo", tag="practice")
    index_path = module.rebuild_index()
    index_doc = MarkdownRepository().read_doc(tmp_path / "pins" / "index.md")

    assert updated.pin.priority == "high"
    assert fetched.kind == "todo"
    assert fetched.tags == ["mcp", "practice"]
    assert fetched.content == "Practice connector lazy fetch and write down edge cases."
    assert [pin.id for pin in results] == ["future-mcp-drill"]
    assert index_path == tmp_path / "pins" / "index.json"
    assert '"schema": "alcove/pins-index/v1"' in index_path.read_text(encoding="utf-8")
    assert "## Todo" in index_doc.body
    assert "Future MCP Drill" in index_doc.body


def test_pin_write_normalizes_messy_content_without_changing_meaning(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = PinsModule(workspace)

    created = module.add(
        AddPinRequest(
            title="Messy Pin",
            summary="Keep useful but tidy.",
            content="Line one   \n\n\n===\n\n—\n\nLine two",
            content_format="markdown",
        )
    )
    updated = module.update(
        UpdatePinRequest(
            pin_id="messy-pin",
            content="Updated line   \n\n\n\nNext line",
            content_format="text",
        )
    )

    assert created.pin.content.rstrip() == "Line one\n\n---\n\n---\n\nLine two"
    assert updated.pin.content == "Updated line\n\nNext line"


def test_pin_render_html_groups_regular_and_todo_pins(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = PinsModule(workspace)
    module.add(
        AddPinRequest(
            title="Stable Reference",
            summary="A regular pin for repeated lookup.",
            content="Keep this close to the daily knowledge workflow.",
            kind="regular",
            tags=["workflow"],
        )
    )
    module.add(
        AddPinRequest(
            title="Try Later",
            summary="A todo pin for future exploration.",
            content="Test a richer connector idea when there is time.",
            kind="todo",
            tags=["idea"],
        )
    )

    html_path = module.render_html()
    html = html_path.read_text(encoding="utf-8")

    assert html_path == tmp_path / "pins" / "board.html"
    assert "<!doctype html>" in html
    assert "Pins Board" in html
    assert "常规置顶" in html
    assert "待实践 / 深入" in html
    assert "Stable Reference" in html
    assert "Try Later" in html
    assert "<svg" in html


def test_search_includes_active_pins(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = PinsModule(workspace)
    module.add(
        AddPinRequest(
            title="Pinned Workflow",
            description="Use Clipsmith for capture and Alcove for knowledge.",
            tags=["workflow"],
        )
    )
    module.archive("pinned-workflow", confirm=True)
    module.add(
        AddPinRequest(
            title="Active Workflow",
            description="Use Alcove search to find pinned snippets.",
            tags=["workflow"],
        )
    )

    rows = SearchModule(workspace).search(SearchRequest(query="pinned snippets"))

    assert len(rows) == 1
    assert {
        "root": "pins",
        "type": "Pin",
        "title": "Active Workflow",
        "domain": None,
        "topic": None,
        "platform": None,
        "tags": ["workflow"],
        "confidence": 0.5,
        "status": "active",
        "resource": None,
        "path": "pins/active-workflow.md",
    }.items() <= rows[0].items()
    assert rows[0]["date"]
