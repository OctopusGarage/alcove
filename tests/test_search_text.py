from __future__ import annotations

from alcove.search_text import deduplicated_search_text


def test_deduplicated_search_text_preserves_first_normalized_line() -> None:
    assert (
        deduplicated_search_text(
            [
                "Keep this exact line.\nExtra detail.",
                "  keep   this exact LINE.  ",
                "",
                "Another line.",
            ]
        )
        == "Keep this exact line.\nExtra detail.\nAnother line."
    )
