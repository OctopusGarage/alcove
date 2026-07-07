from alcove.markdown import MarkdownDoc, MarkdownRepository, normalize_slug


def test_normalize_slug_keeps_chinese_and_ascii():
    assert normalize_slug("代码图谱怎么选") == "代码图谱怎么选"
    assert normalize_slug("Apple Notes / Export!") == "apple-notes-export"


def test_write_and_read_markdown_doc(tmp_path):
    repo = MarkdownRepository()
    path = tmp_path / "note.md"
    doc = MarkdownDoc(
        frontmatter={"type": "Pin", "title": "Hello", "tags": ["demo"]},
        body="# Hello\n\nBody",
    )

    repo.write_doc(path, doc)
    loaded = repo.read_doc(path)

    assert loaded.frontmatter["type"] == "Pin"
    assert loaded.frontmatter["title"] == "Hello"
    assert loaded.body == "# Hello\n\nBody\n"


def test_unique_path_adds_numeric_suffix(tmp_path):
    repo = MarkdownRepository()
    first = repo.unique_path(tmp_path, "hello")
    first.write_text("x")

    second = repo.unique_path(tmp_path, "hello")

    assert second.name == "hello-2.md"
