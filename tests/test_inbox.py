from __future__ import annotations

import json

import pytest

from alcove.inbox import InboxModule, InboxNoteRequest
from alcove.markdown import MarkdownRepository
from alcove.workspace import Workspace


class RaisingKnowledge:
    def note_source(self, request):
        raise RuntimeError("knowledge write failed")


def _write_post(root, platform, name, files):
    folder = root / "inbox" / platform / name
    folder.mkdir(parents=True)
    for filename, content in files.items():
        (folder / filename).write_text(content, encoding="utf-8")
    return folder


def _write_xhs_post(root, name):
    return _write_post(
        root,
        "xhs",
        name,
        {
            "post.md": "# short\n\n#tag",
            "summary.md": ("# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要"),
        },
    )


def test_xhs_prefers_summary_over_sparse_post(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260707-new")

    post = InboxModule(workspace).read("20260707-new")

    assert post.title == "代码图谱怎么选"
    assert post.content_source == "summary.md"
    assert post.content == "# 代码图谱怎么选\n\n来源：https://example.test/xhs\n\n详细摘要"


def test_peek_returns_oldest_across_platforms(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260707-new")
    _write_post(tmp_path, "wechat", "no-date", {"article.md": "# No Date\n\nbody"})
    _write_post(tmp_path, "web", "20260706-old", {"article.md": "# Old\n\nbody"})

    post = InboxModule(workspace).peek()

    assert post is not None
    assert post.name == "20260706-old"
    assert post.platform == "web"


def test_peek_returns_none_when_inbox_empty(tmp_path):
    workspace = Workspace.init(tmp_path)

    assert InboxModule(workspace).peek() is None


def test_add_manual_note_writes_readable_inbox_item(tmp_path):
    workspace = Workspace.init(tmp_path)

    result = InboxModule(workspace).add_manual(
        title="Clipboard Note",
        content="Copied text from another channel.",
        source="chat://manual",
    )
    post = InboxModule(workspace).read("manual/clipboard-note")

    assert result["status"] == "added"
    assert result["path"] == str(tmp_path / "inbox" / "manual" / "clipboard-note")
    assert (tmp_path / "inbox" / "manual" / "clipboard-note" / "note.md").is_file()
    assert post.title == "Clipboard Note"
    assert post.source == "chat://manual"
    assert post.content_source == "note.md"


def test_read_extracts_title_source_date_and_content_source(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "wechat",
        "20260706-old",
        {
            "article.md": (
                "intro\n# Extracted Title\n\nSource URL: https://example.test/source\n\nBody"
            )
        },
    )

    post = InboxModule(workspace).read("20260706-old")

    assert post.title == "Extracted Title"
    assert post.source == "https://example.test/source"
    assert post.date == "2026-07-06"
    assert post.content_source == "article.md"


def test_read_uses_clipsmith_capture_metadata_as_fallback(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "clipsmith-web-bundle",
        {
            "summary.md": "# Summary\n\nBody without inline source.",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "clipsmith-web-bundle",
                    "platform": "web",
                    "source_url": "https://example.test/article",
                    "canonical_url": "https://canonical.example.test/article",
                    "title": "Clipsmith Article Title",
                    "published_at": "2026-07-07",
                    "content_files": [
                        {
                            "path": "summary.md",
                            "kind": "summary",
                            "required_for_review": True,
                        }
                    ],
                    "assets": [],
                    "warnings": [],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("clipsmith-web-bundle")

    assert post.title == "Clipsmith Article Title"
    assert post.source == "https://example.test/article"
    assert post.date == "2026-07-07"
    assert post.content_source == "summary.md"


def test_read_clipsmith_bundle_uses_declared_ocr_content_file(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "image-ocr",
        "receipt-ocr",
        {
            "ocr.md": "# OCR Text\n\nTotal: 42",
            "post.md": "# Sparse OCR\n\nfallback",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "receipt-ocr",
                    "platform": "image-ocr",
                    "source_url": "~/Downloads/receipt.png",
                    "title": "Receipt OCR",
                    "captured_at": "2026-07-09T16:20:00+08:00",
                    "content_files": [
                        {
                            "path": "ocr.md",
                            "kind": "ocr-text",
                            "required_for_review": True,
                        },
                        {
                            "path": "post.md",
                            "kind": "post",
                            "required_for_review": True,
                        },
                    ],
                    "assets": [{"path": "receipt.png", "kind": "ocr-image"}],
                    "warnings": [],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("image-ocr/receipt-ocr")

    assert post.title == "OCR Text"
    assert post.source == "~/Downloads/receipt.png"
    assert post.date == "2026-07-09"
    assert "# OCR Text\n\nTotal: 42" in post.content
    assert "# Sparse OCR\n\nfallback" in post.content
    assert post.content_source == "ocr.md, post.md"


def test_read_clipsmith_bundle_includes_summary_post_and_ocr_text(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "image-ocr",
        "receipt-ocr",
        {
            "summary.md": "# Summary\n\nGenerated OCR summary.",
            "ocr.md": "# OCR Text\n\nTotal: 42",
            "post.md": "# Sparse OCR\n\nfallback",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "receipt-ocr",
                    "platform": "image-ocr",
                    "source_url": "~/Downloads/receipt.png",
                    "title": "Receipt OCR",
                    "captured_at": "2026-07-09T16:20:00+08:00",
                    "content_files": [
                        {
                            "path": "summary.md",
                            "kind": "summary",
                            "required_for_review": True,
                        },
                        {
                            "path": "ocr.md",
                            "kind": "ocr-text",
                            "required_for_review": True,
                        },
                        {
                            "path": "post.md",
                            "kind": "post",
                            "required_for_review": True,
                        },
                    ],
                    "assets": [{"path": "receipt.png", "kind": "ocr-image"}],
                    "warnings": [],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("image-ocr/receipt-ocr")

    assert post.title == "Receipt OCR"
    assert post.identifier == "image-ocr/receipt-ocr"
    assert post.content_truncated is False
    assert post.full_content_command == "alcove inbox read image-ocr/receipt-ocr --full --json"
    assert "# Summary\n\nGenerated OCR summary." in post.content
    assert "# OCR Text\n\nTotal: 42" in post.content
    assert "# Sparse OCR\n\nfallback" in post.content
    assert post.content_source == "summary.md, ocr.md, post.md"
    assert post.content_files == [
        {
            "path": "summary.md",
            "kind": "summary",
            "byte_count": 33,
            "char_count": 33,
            "included": True,
            "duplicate_of": "",
            "merged_into": "",
            "truncated": False,
            "omitted_chars": 0,
            "review_excerpt": "Generated OCR summary.",
            "review_excerpt_truncated": False,
            "review_excerpt_omitted_chars": 0,
            "tail_excerpt": "",
            "read_command": "alcove inbox read image-ocr/receipt-ocr --full --json",
            "read_hint": (
                "Use read_command for the full merged payload; use path to locate this "
                "source file inside the inbox item when exact file provenance is needed."
            ),
        },
        {
            "path": "ocr.md",
            "kind": "ocr-text",
            "byte_count": 21,
            "char_count": 21,
            "included": True,
            "duplicate_of": "",
            "merged_into": "",
            "truncated": False,
            "omitted_chars": 0,
            "review_excerpt": "Total: 42",
            "review_excerpt_truncated": False,
            "review_excerpt_omitted_chars": 0,
            "tail_excerpt": "",
            "read_command": "alcove inbox read image-ocr/receipt-ocr --full --json",
            "read_hint": (
                "Use read_command for the full merged payload; use path to locate this "
                "source file inside the inbox item when exact file provenance is needed."
            ),
        },
        {
            "path": "post.md",
            "kind": "post",
            "byte_count": 22,
            "char_count": 22,
            "included": True,
            "duplicate_of": "",
            "merged_into": "",
            "truncated": False,
            "omitted_chars": 0,
            "review_excerpt": "fallback",
            "review_excerpt_truncated": False,
            "review_excerpt_omitted_chars": 0,
            "tail_excerpt": "",
            "read_command": "alcove inbox read image-ocr/receipt-ocr --full --json",
            "read_hint": (
                "Use read_command for the full merged payload; use path to locate this "
                "source file inside the inbox item when exact file provenance is needed."
            ),
        },
    ]
    assert post.review_content == "Generated OCR summary. Total: 42 fallback"
    assert post.review_summary == "Generated OCR summary. OCR: Total: 42"
    assert post.review_outline == []
    assert post.review_content_truncated is False
    assert post.review_content_omitted_chars == 0


def test_read_clipsmith_bundle_deduplicates_identical_declared_content_files(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "image-ocr",
        "receipt-ocr",
        {
            "summary.md": "# Summary\n\nGenerated OCR summary.",
            "ocr.md": "Clipsmith OCR smoke test\nOCR result should be saved to ocr.md",
            "post.md": "Clipsmith OCR smoke test\nOCR result should be saved to ocr.md",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "receipt-ocr",
                    "platform": "image-ocr",
                    "source_url": "~/Downloads/receipt.png",
                    "title": "Receipt OCR",
                    "content_files": [
                        {"path": "summary.md", "kind": "summary", "required_for_review": True},
                        {"path": "ocr.md", "kind": "ocr-text", "required_for_review": True},
                        {"path": "post.md", "kind": "post", "required_for_review": True},
                    ],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("image-ocr/receipt-ocr")

    assert post.content.count("OCR result should be saved to ocr.md") == 1
    assert post.content_source == "summary.md, ocr.md"
    assert post.content_files[2]["path"] == "post.md"
    assert post.content_files[2]["included"] is False
    assert post.content_files[2]["duplicate_of"] == "ocr.md"
    assert (
        post.review_summary
        == "Generated OCR summary. OCR: Clipsmith OCR smoke test OCR result should be saved to ocr.md"
    )


def test_read_keeps_short_summary_visible_when_duplicate_of_post(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "summary-duplicate",
        {
            "summary.md": "Why it exists Capture is not knowledge management.",
            "post.md": (
                "Why it exists Capture is not knowledge management. "
                "Workflow One protocol, different capture strategies."
            ),
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "summary-duplicate",
                    "platform": "web",
                    "content_files": [
                        {"path": "summary.md", "kind": "summary"},
                        {"path": "post.md", "kind": "post"},
                    ],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/summary-duplicate")

    assert post.content_files[0]["included"] is False
    assert post.content_files[0]["duplicate_of"] == ""
    assert post.content_files[0]["merged_into"] == "post.md"
    assert (
        post.review_summary
        == "Capture is not knowledge management. One protocol, different capture strategies."
    )


def test_read_marks_content_truncated_when_source_contains_truncation_marker(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "truncated-web",
        {
            "post.md": "# Web Post\n\nLead sentence...[truncated 1498 chars]",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "truncated-web",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/truncated-web")

    assert post.content_truncated is True
    assert post.full_content_command == "alcove inbox read web/truncated-web --full --json"
    assert post.content_files[0]["truncated"] is True
    assert post.content_files[0]["omitted_chars"] == 1498
    assert post.content_files[0]["review_excerpt"] == "# Web Post Lead sentence..."
    assert post.content_outline == [
        {
            "path": "post.md",
            "kind": "post",
            "truncated": True,
            "omitted_chars": 1498,
            "excerpt": "# Web Post Lead sentence...",
            "tail_excerpt": "# Web Post Lead sentence...",
        }
    ]


def test_read_web_bundle_prefers_denoised_review_content(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "noisy-web",
        {
            "post.md": (
                "# Clipsmith - Local-first capture bundles\n\n"
                "Source: https://octopusgarage.github.io/clipsmith/\n\n"
                "Clipsmith - Local-first capture bundles Clipsmith Workflow Contract GitHub "
                "Capture locally, carry anywhere. Why it exists Capture is not knowledge "
                "management. Small contract Every capture becomes a portable directory."
            ),
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "noisy-web",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/noisy-web")

    assert post.review_content.startswith("Why it exists Capture is not knowledge management.")
    assert post.review_content.count("Why it exists") == 1
    assert "Workflow Contract GitHub" not in post.review_content
    assert post.review_content_truncated is False
    assert post.content_files[0]["review_excerpt"].startswith(
        "Why it exists Capture is not knowledge management."
    )


def test_read_web_bundle_preserves_lightweight_review_structure(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "structured-web",
        {
            "post.md": (
                "# Article\n\n"
                "Overview\n"
                "- First point\n"
                "- Second point\n\n"
                "Commands\n"
                '`alcove search "query" --json`'
            ),
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "structured-web",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/structured-web")

    assert "Overview\n- First point\n- Second point" in post.review_content
    assert "Commands\n`alcove search" in post.review_content
    assert post.review_outline[0]["path"] == "post.md"
    assert [section["title"] for section in post.review_outline[0]["sections"]] == [
        "Overview",
        "Commands",
    ]
    assert post.review_outline[0]["sections"][0]["excerpt"] == "First point - Second point"
    assert post.review_outline[0]["sections"][1]["excerpt"] == '`alcove search "query" --json`'


def test_read_web_bundle_extracts_outline_from_flat_capture_text(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "flat-web",
        {
            "post.md": (
                "Why it exists Capture is not knowledge management. "
                "Workflow One protocol, different capture strategies. "
                "01 Start Select a provider. "
                "02 Capture Run the provider skill. "
                "Commands clipsmith providers --json."
            ),
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "flat-web",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/flat-web")

    sections = post.review_outline[0]["sections"]
    assert [section["title"] for section in sections[:4]] == [
        "Why it exists",
        "Workflow",
        "01 Start",
        "02 Capture",
    ]
    assert sections[0]["excerpt"].startswith("Capture is not knowledge management.")
    assert not sections[0]["excerpt"].startswith("Why it exists")
    assert post.review_summary == (
        "Capture is not knowledge management. "
        "One protocol, different capture strategies. "
        "clipsmith providers --json."
    )


def test_read_web_bundle_summarizes_uppercase_rich_capture_sections(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "uppercase-rich-web",
        {
            "post.md": (
                "WHY IT EXISTS\n"
                "Capture is not knowledge management.\n"
                "WORKFLOW\n"
                "Use platform skills, validation, and sinks.\n"
                "COMMANDS\n"
                "clipsmith providers --json.\n"
                "BUNDLE\n"
                "Portable by default."
            ),
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "uppercase-rich-web",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/uppercase-rich-web")

    sections = post.review_outline[0]["sections"]
    assert [section["title"] for section in sections[:4]] == [
        "WHY IT EXISTS",
        "WORKFLOW",
        "COMMANDS",
        "BUNDLE",
    ]
    assert post.review_summary == (
        "Capture is not knowledge management. "
        "Use platform skills, validation, and sinks. "
        "clipsmith providers --json."
    )


def test_read_web_bundle_does_not_promote_lowercase_continuation_word_to_section(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "lowercase-continuation-web",
        {
            "post.md": (
                "WHY IT EXISTS\n"
                "Capture is not knowledge management.\n"
                "04 Sink\n"
                "Copy the validated\n"
                "bundle only when explicitly requested.\n"
                "COMMANDS\n"
                "clipsmith providers --json."
            ),
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "lowercase-continuation-web",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/lowercase-continuation-web")

    sections = post.review_outline[0]["sections"]
    assert [section["title"] for section in sections] == [
        "WHY IT EXISTS",
        "04 Sink",
        "COMMANDS",
    ]
    assert sections[1]["excerpt"] == "Copy the validated bundle only when explicitly requested."


def test_read_web_bundle_summary_drops_isolated_punctuation_segments(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "punctuation-rich-web",
        {
            "post.md": (
                "WHY IT EXISTS\n"
                "Capture is not knowledge management.\n"
                "WORKFLOW\n"
                ". Downstream neutral tools validate and export bundles.\n"
                "COMMANDS\n"
                "clipsmith providers --json."
            ),
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "punctuation-rich-web",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/punctuation-rich-web")

    assert ". ." not in post.review_summary
    assert post.review_summary == (
        "Capture is not knowledge management. "
        "Downstream neutral tools validate and export bundles. "
        "clipsmith providers --json."
    )


def test_read_marks_review_content_truncated_separately_from_source_content(tmp_path):
    workspace = Workspace.init(tmp_path)
    body = " ".join(f"segment-{index}" for index in range(900))
    _write_post(
        tmp_path,
        "web",
        "long-review",
        {
            "post.md": body,
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "long-review",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/long-review")

    assert post.content_truncated is False
    assert post.review_content.endswith("…")
    assert post.review_content_truncated is True
    assert post.review_content_omitted_chars > 0


def test_truncated_source_review_excerpt_preserves_head_and_tail(tmp_path):
    workspace = Workspace.init(tmp_path)
    body = " ".join(f"lead-{index} body text." for index in range(700))
    _write_post(
        tmp_path,
        "web",
        "long-truncated-source",
        {
            "post.md": f"{body}[truncated 2048 chars]",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "long-truncated-source",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "status": "complete",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/long-truncated-source")
    excerpt = post.content_files[0]["review_excerpt"]

    assert excerpt.startswith("lead-0 body text.")
    assert "...[omitted " in excerpt
    assert "699 body text." in excerpt
    assert not excerpt.startswith("body text.")
    assert post.content_files[0]["review_excerpt_truncated"] is True
    assert [section["title"] for section in post.review_outline[0]["sections"]] == [
        "Lead",
        "Later context",
        "Full content",
    ]
    assert post.review_outline[0]["sections"][0]["excerpt"].startswith("lead-0 body text.")
    assert "read_command" in post.review_outline[0]["sections"][2]["excerpt"]


def test_read_surfaces_capture_status_and_warnings(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "warning-post",
        {
            "post.md": "# Warning Post\n\nBody.",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "warning-post",
                    "platform": "web",
                    "content_files": [{"path": "post.md", "kind": "post"}],
                    "warnings": ["article extraction incomplete", "embedded media skipped"],
                    "status": "partial",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/warning-post")

    assert post.capture_status == "partial"
    assert post.capture_warnings == [
        "article extraction incomplete",
        "embedded media skipped",
    ]
    assert post.review_summary.startswith(
        "Warnings: article extraction incomplete; embedded media skipped."
    )


def test_read_clipsmith_bundle_ignores_unsafe_declared_content_file(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "web",
        "unsafe-bundle",
        {
            "post.md": "# Safe Post\n\nBody",
            "capture.json": json.dumps(
                {
                    "schema": "clipsmith.capture_bundle.v1",
                    "id": "unsafe-bundle",
                    "platform": "web",
                    "source_url": "https://example.test",
                    "content_files": [
                        {"path": "../secret.md", "kind": "summary"},
                        {"path": "post.md", "kind": "post"},
                    ],
                    "assets": [],
                    "warnings": [],
                    "status": "partial",
                }
            ),
        },
    )

    post = InboxModule(workspace).read("web/unsafe-bundle")

    assert post.title == "Safe Post"
    assert post.content_source == "post.md"


def test_note_moves_post_to_archive_writes_source_concept_and_records_legacy_path(
    tmp_path,
):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260706-old")
    module = InboxModule(workspace)

    result = module.note(
        InboxNoteRequest(
            name="20260706-old",
            topic="agent-engineering/agent-harness",
            summary="代码图谱选型要看索引准确性和 Agent 是否实际使用。",
            tags=["agent-harness", "code-intelligence"],
        )
    )

    assert result.archive_path == tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old"
    assert result.archive_path.is_dir()
    assert not (tmp_path / "inbox" / "xhs" / "20260706-old").exists()
    assert result.source_path.is_file()
    assert result.concept_path is not None
    assert result.concept_path.is_file()

    repo = MarkdownRepository()
    source = repo.read_doc(result.source_path)
    concept = repo.read_doc(result.concept_path)
    assert source.frontmatter["resource"] == "https://example.test/xhs"
    assert source.frontmatter["legacy_path"] == "archive/agent-harness/[xhs] 20260706-old"
    assert "## 原文摘录" in source.body
    assert "摘要" in source.body
    assert concept.frontmatter["legacy_paths"] == ["archive/agent-harness/[xhs] 20260706-old"]


def test_archive_source_only_uses_fallback_content_when_summary_blank(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(
        tmp_path,
        "x",
        "20260705-post",
        {"post.md": "# Source Only\n\nPlain body with https://example.test/fallback"},
    )

    result = InboxModule(workspace).archive(
        "20260705-post",
        "agent-engineering/agent-harness",
        tags=["code-intelligence"],
    )

    assert result.concept_path is None
    source = MarkdownRepository().read_doc(result.source_path)
    assert source.frontmatter["resource"] == "https://example.test/fallback"
    assert "# Source Only\n\nPlain body with https://example.test/fallback" in source.body
    assert "## 来源" in source.body
    assert "archive/agent-harness/[x] 20260705-post" in source.body


def test_archive_uses_archived_path_as_resource_when_source_missing(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(tmp_path, "web", "20260704-nosource", {"article.md": "# No Source\n\nBody"})

    result = InboxModule(workspace).archive(
        "20260704-nosource",
        "agent-engineering/agent-harness",
        summary="Manual summary.",
    )

    source = MarkdownRepository().read_doc(result.source_path)
    assert source.frontmatter["resource"] == "archive/agent-harness/[web] 20260704-nosource"


def test_archive_destination_collision_gets_numeric_suffix(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260706-old")
    collision = tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old"
    collision.mkdir(parents=True)

    result = InboxModule(workspace).archive(
        "20260706-old",
        "agent-engineering/agent-harness",
        summary="Manual summary.",
    )

    assert result.archive_path == tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old-2"
    assert result.archive_path.is_dir()
    assert collision.is_dir()


def test_note_rolls_back_archive_move_when_knowledge_write_fails(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_xhs_post(tmp_path, "20260706-old")
    archive_path = tmp_path / "archive" / "agent-harness" / "[xhs] 20260706-old"

    with pytest.raises(RuntimeError, match="knowledge write failed"):
        InboxModule(workspace, knowledge=RaisingKnowledge()).note(
            InboxNoteRequest(
                name="20260706-old",
                topic="agent-engineering/agent-harness",
                summary="Summary.",
            )
        )

    assert (tmp_path / "inbox" / "xhs" / "20260706-old").is_dir()
    assert not archive_path.exists()


def test_platform_name_identifier_disambiguates_duplicate_folder_names(tmp_path):
    workspace = Workspace.init(tmp_path)
    _write_post(tmp_path, "web", "20260706-same", {"article.md": "# Web Post\n\nBody"})
    _write_post(tmp_path, "x", "20260706-same", {"post.md": "# X Post\n\nBody"})

    with pytest.raises(ValueError, match="Ambiguous inbox item.*platform/name"):
        InboxModule(workspace).archive(
            "20260706-same",
            "agent-engineering/agent-harness",
            summary="Manual summary.",
        )

    result = InboxModule(workspace).archive(
        "x/20260706-same",
        "agent-engineering/agent-harness",
        summary="Manual summary.",
    )

    assert result.archive_path == tmp_path / "archive" / "agent-harness" / "[x] 20260706-same"
    assert result.archive_path.is_dir()
    assert (tmp_path / "inbox" / "web" / "20260706-same").is_dir()
    assert not (tmp_path / "inbox" / "x" / "20260706-same").exists()


def test_rejects_identifier_that_escapes_inbox(tmp_path):
    workspace = Workspace.init(tmp_path)
    outside = tmp_path / "archive" / "old-topic" / "outside"
    outside.mkdir(parents=True)
    (outside / "article.md").write_text("# Outside\n\nBody", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid inbox identifier"):
        InboxModule(workspace).archive(
            "../archive/old-topic/outside",
            "agent-engineering/agent-harness",
            summary="Manual summary.",
        )

    assert outside.is_dir()
    assert not (tmp_path / "archive" / "agent-harness" / "[old-topic] outside").exists()


def test_rejects_platform_identifier_with_nested_item_path(tmp_path):
    workspace = Workspace.init(tmp_path)
    web_post = _write_post(tmp_path, "web", "20260706-post", {"article.md": "# Web\n\nBody"})

    with pytest.raises(ValueError, match="Invalid inbox identifier"):
        InboxModule(workspace).archive(
            "x/../web/20260706-post",
            "agent-engineering/agent-harness",
            summary="Manual summary.",
        )

    assert web_post.is_dir()
    assert not (tmp_path / "archive" / "agent-harness" / "[web] 20260706-post").exists()


@pytest.mark.parametrize(
    "identifier",
    [
        "",
        ".",
        "..",
        "/tmp/outside",
        "x/",
        "/x/name",
        "x/.",
        "x/..",
        "x/name/extra",
    ],
)
def test_rejects_malformed_inbox_identifiers(tmp_path, identifier):
    workspace = Workspace.init(tmp_path)

    with pytest.raises(ValueError, match="Invalid inbox identifier"):
        InboxModule(workspace).read(identifier)


def test_missing_content_file_raises_file_not_found(tmp_path):
    workspace = Workspace.init(tmp_path)
    (tmp_path / "inbox" / "xhs" / "20260706-empty").mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        InboxModule(workspace).read("20260706-empty")
