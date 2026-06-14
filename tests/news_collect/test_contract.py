from news_collect.contract import ItemRef, FetchResult, NormalizedDoc


def test_itemref_defaults():
    ref = ItemRef(key="k1", source="rss")
    assert ref.key == "k1"
    assert ref.source == "rss"
    assert ref.url is None
    assert ref.meta == {}


def test_fetchresult_keys_property():
    r = FetchResult(
        status="ok",
        written=[ItemRef(key="a", source="rss"), ItemRef(key="b", source="rss")],
    )
    assert r.keys == ["a", "b"]
    assert r.message == ""


def test_normalizeddoc_holds_body():
    doc = NormalizedDoc(source="rss", title="Hello", body_md="# Hello")
    assert doc.title == "Hello"
    assert doc.extra_frontmatter == {}
