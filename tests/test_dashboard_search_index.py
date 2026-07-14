from alcove.dashboard_search_index import build_dashboard_search_index


def test_dashboard_search_index_projection_filters_and_summarizes_external_rows():
    snapshot = {
        "pins": {
            "all": [
                {
                    "title": "Repeated Pin",
                    "summary": "Keep this exact line.",
                    "tags": ["lookup"],
                    "content": "Keep this exact line.\nExtra detail.",
                }
            ]
        },
        "tasks": {"pending": [], "ideas": [], "routines": []},
        "modules": [],
        "prompts": [],
        "projects": [],
        "radars": [],
        "knowledge": {
            "managed": [
                {
                    "name": "research_notes",
                    "item_count": 2,
                    "omitted_item_count": 0,
                    "inbox_count": 0,
                    "archive_count": 0,
                    "items": [
                        {
                            "title": "Knowledge Index",
                            "relative_path": "knowledge/index.md",
                            "notes": "# Knowledge Index",
                        },
                        {
                            "title": "Real Source",
                            "type": "Source",
                            "relative_path": "knowledge/sources/web/real.md",
                            "notes": "---\ntype: Source\n---\n# Real Source\n- Useful detail",
                        },
                    ],
                }
            ]
        },
        "sources": {
            "mounts": [
                {
                    "id": "archive",
                    "name": "Archive",
                    "type": "local-folder",
                    "status": "active",
                    "count": 1,
                    "items": [
                        {
                            "title": "Mounted Note",
                            "type": "Mounted Item",
                            "resource": "mounts/archive#note.md",
                            "status": "active",
                            "notes": "# Mounted Note\nMounted detail",
                        }
                    ],
                }
            ],
            "connectors": [
                {
                    "id": "github-stars",
                    "connector": "github-stars",
                    "source": "GitHub Stars",
                    "status": "fresh",
                    "count": 1,
                    "items": [
                        {
                            "title": "octopusgarage/alcove",
                            "type": "GitHub Star",
                            "resource": "https://github.com/OctopusGarage/alcove",
                            "status": "active",
                            "notes": "Local-first knowledge core.",
                        }
                    ],
                }
            ],
        },
    }

    rows = build_dashboard_search_index(snapshot)

    pin = next(row for row in rows if row["type"] == "pin")
    assert pin["text"].count("Keep this exact line.") == 1
    kb_row = next(row for row in rows if row["type"] == "knowledge-base")
    assert kb_row["text"] == "2 knowledge items 0 inbox items 0 archived items"
    assert "omitted:" not in kb_row["text"]
    knowledge_titles = {row["title"] for row in rows if row["type"] == "knowledge-item"}
    assert knowledge_titles == {"Real Source"}
    assert "Useful detail" in next(row for row in rows if row["title"] == "Real Source")["text"]
    assert "Mounted detail" in next(row for row in rows if row["title"] == "Mounted Note")["text"]
    assert (
        "https://github.com/OctopusGarage/alcove"
        in next(row for row in rows if row["title"] == "octopusgarage/alcove")["text"]
    )
