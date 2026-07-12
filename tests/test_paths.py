from __future__ import annotations

from alcove.paths import compact_user_paths_in_text


def test_compact_user_paths_in_text_redacts_common_user_home_shapes() -> None:
    text = "/Users/example/private note /home/runner/work/alcove /opt/shared/location"

    compacted = compact_user_paths_in_text(text)

    assert "~/private" in compacted
    assert "~/work/alcove" in compacted
    assert "/Users/example" not in compacted
    assert "/home/runner" not in compacted
    assert "/opt/shared/location" in compacted
