from pathlib import Path

import yaml

from news_collect.adapters.rss import RssAdapter
from news_collect.state import SourceState

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


def test_discover_returns_entries_with_url_keys(tmp_path):
    adapter = RssAdapter(feeds=[FIXTURE.as_uri()], vault=tmp_path / "vault",
                         now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    keys = {r.key for r in refs}
    assert "https://example.com/first" in keys
    assert "https://example.com/second" in keys
    assert all(r.source == "rss" for r in refs)


def test_fetch_writes_markdown_with_converted_body(tmp_path):
    vault = tmp_path / "vault"
    adapter = RssAdapter(feeds=[FIXTURE.as_uri()], vault=vault, now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    result = adapter.fetch(refs)
    assert result.status == "ok"
    assert len(result.written) == 2
    files = list((vault / "News" / "rss").glob("*.md"))
    assert len(files) == 2
    text = (files[0]).read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["source"] == "rss"
    # markdownify converts <b>/<i> to markdown emphasis
    assert "**" in text or "*" in text
