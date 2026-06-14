from pathlib import Path

from news_collect.keys import url_key, file_key


def test_url_key_strips_tracking_and_fragment():
    a = url_key("https://example.com/post?utm_source=x&id=5#section")
    b = url_key("https://example.com/post?id=5")
    assert a == b


def test_url_key_normalizes_trailing_slash_and_scheme_case():
    assert url_key("HTTP://Example.com/post/") == url_key("http://example.com/post")


def test_file_key_changes_with_content(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("one", encoding="utf-8")
    k1 = file_key(f)
    f.write_text("two", encoding="utf-8")
    k2 = file_key(f)
    assert k1 != k2
    assert k1.startswith(str(Path(f).resolve()) + "#")
