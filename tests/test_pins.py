from __future__ import annotations

from alcove.markdown import MarkdownRepository
from alcove.pins import AddPinRequest, PinsModule
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def test_pin_add_writes_markdown_pin_and_lists_active_pins(tmp_path):
    workspace = Workspace.init(tmp_path)
    module = PinsModule(workspace)

    result = module.add(
        AddPinRequest(
            title="Japanese Edge Launcher",
            description="Launch Edge with TZ=Asia/Tokyo for region-sensitive tests.",
            tags=["app-launcher", "edge"],
            priority="high",
            source_refs=["/sources/web/edge.md"],
        )
    )

    doc = MarkdownRepository().read_doc(result.path)
    pins = module.list()

    assert result.path == tmp_path / "pins" / "japanese-edge-launcher.md"
    assert doc.frontmatter["type"] == "Pin"
    assert doc.frontmatter["title"] == "Japanese Edge Launcher"
    assert doc.frontmatter["status"] == "active"
    assert doc.frontmatter["priority"] == "high"
    assert doc.frontmatter["tags"] == ["app-launcher", "edge"]
    assert doc.frontmatter["source_refs"] == ["/sources/web/edge.md"]
    assert pins[0].title == "Japanese Edge Launcher"


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
