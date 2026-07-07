import pytest

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


def test_read_doc_treats_malformed_frontmatter_as_body(tmp_path):
    repo = MarkdownRepository()
    path = tmp_path / "bad.md"
    content = "---\ntitle: [unterminated\n---\n# Body\n"
    path.write_text(content, encoding="utf-8")

    loaded = repo.read_doc(path)

    assert loaded.frontmatter == {}
    assert loaded.body == content


def test_read_doc_treats_non_dict_frontmatter_as_body(tmp_path):
    repo = MarkdownRepository()
    path = tmp_path / "list-frontmatter.md"
    content = "---\n- Pin\n---\n# Body\n"
    path.write_text(content, encoding="utf-8")

    loaded = repo.read_doc(path)

    assert loaded.frontmatter == {}
    assert loaded.body == content


@pytest.mark.parametrize("frontmatter_text", ["[]", "false", "0"])
def test_read_doc_treats_falsy_non_dict_frontmatter_as_body(tmp_path, frontmatter_text):
    repo = MarkdownRepository()
    path = tmp_path / "falsy-frontmatter.md"
    content = f"---\n{frontmatter_text}\n---\n# Body\n"
    path.write_text(content, encoding="utf-8")

    loaded = repo.read_doc(path)

    assert loaded.frontmatter == {}
    assert loaded.body == content


def test_unique_path_adds_numeric_suffix(tmp_path):
    repo = MarkdownRepository()
    first = repo.unique_path(tmp_path, "hello")
    first.write_text("x")

    second = repo.unique_path(tmp_path, "hello")

    assert second.name == "hello-2.md"


def test_unique_path_avoids_reserved_filenames(tmp_path):
    repo = MarkdownRepository()

    assert repo.unique_path(tmp_path, "index").name == "index-2.md"
    assert repo.unique_path(tmp_path, "log").name == "log-2.md"
