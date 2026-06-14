import yaml

from news_collect.contract import NormalizedDoc
from news_collect.writer import slugify, write_doc


def test_slugify_basic():
    assert slugify("Hello, World! 2026") == "hello-world-2026"


def test_slugify_handles_unicode_and_empty():
    assert slugify("中文标题") != ""
    assert slugify("") == "untitled"


def test_write_doc_creates_file_with_frontmatter(tmp_path):
    doc = NormalizedDoc(
        source="rss", title="My Post", body_md="# Body\n\ntext",
        url="https://example.com/p", published="2026-06-10T00:00:00+00:00",
        extra_frontmatter={"feed": "Example"},
    )
    path = write_doc(tmp_path, doc, collected_at="2026-06-14T09:00:00+02:00")
    assert path.exists()
    assert path.parent == tmp_path / "News" / "rss"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["source"] == "rss"
    assert fm["title"] == "My Post"
    assert fm["url"] == "https://example.com/p"
    assert fm["collected_at"] == "2026-06-14T09:00:00+02:00"
    assert fm["feed"] == "Example"
    assert "# Body" in text


def test_write_doc_is_stable_for_same_doc(tmp_path):
    doc = NormalizedDoc(source="rss", title="Same", body_md="x", url="https://e.com/a")
    p1 = write_doc(tmp_path, doc, collected_at="t")
    p2 = write_doc(tmp_path, doc, collected_at="t")
    assert p1 == p2  # same filename, overwritten not duplicated
