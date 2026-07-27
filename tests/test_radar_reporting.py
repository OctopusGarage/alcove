from __future__ import annotations

from alcove.radars.models import RadarDefinition, RadarItem
from alcove.radars.reporting import RadarReportSelection, selected_report_items


def test_radar_report_selection_owns_limits_topics_and_source_counts() -> None:
    definition = RadarDefinition(
        id="report-quality",
        name="Report Quality",
        report={"max_items": 3, "max_per_source": 2},
    )
    items = [
        RadarItem(
            source_id="source-a",
            adapter="fixture",
            title="OpenAI launches agent orchestration for coding teams",
            url="https://example.test/openai-agent-a",
            score=0.99,
            included=True,
        ),
        RadarItem(
            source_id="source-a",
            adapter="fixture",
            title="OpenAI launches agent orchestration for coding teams - analysis",
            url="https://example.test/openai-agent-b",
            score=0.98,
            included=True,
        ),
        RadarItem(
            source_id="source-a",
            adapter="fixture",
            title="AI database indexing improves retrieval infrastructure",
            url="https://example.test/ai-db",
            score=0.97,
            included=True,
        ),
        RadarItem(
            source_id="source-a",
            adapter="fixture",
            title="Cloud security teams adopt AI review gates",
            url="https://example.test/ai-security",
            score=0.96,
            included=True,
        ),
        RadarItem(
            source_id="source-b",
            adapter="fixture",
            title="Developer tools market shifts toward local-first agents",
            url="https://example.test/local-agents",
            score=0.95,
            included=True,
        ),
        RadarItem(
            source_id="source-c",
            adapter="fixture",
            title="Excluded baseline item",
            url="https://example.test/excluded",
            score=0.94,
            included=False,
        ),
    ]

    selection = RadarReportSelection.from_items(definition, items)
    selected_urls = [item.url for item in selection.items]

    assert selected_urls == [
        "https://example.test/openai-agent-a",
        "https://example.test/ai-db",
        "https://example.test/local-agents",
    ]
    assert selection.included_count == 3
    assert selection.total_count == 6
    assert selection.source_count == 3
    assert selection.source_counts == {"source-a": 4, "source-b": 1, "source-c": 1}
    assert [item.url for item in selected_report_items(definition, items)] == selected_urls


def test_radar_report_selection_source_counts_are_copied() -> None:
    definition = RadarDefinition(id="copy-check", name="Copy Check")
    selection = RadarReportSelection.from_items(
        definition,
        [
            RadarItem(
                source_id="source-a",
                adapter="fixture",
                title="AI signal",
                score=0.8,
                included=True,
            )
        ],
    )

    counts = selection.source_counts
    counts["source-a"] = 99

    assert selection.source_counts == {"source-a": 1}
