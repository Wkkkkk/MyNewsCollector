from __future__ import annotations

import feedparser
from markdownify import markdownify as md

from news_collect.contract import SourceAdapter, ItemRef, FetchResult, NormalizedDoc
from news_collect.keys import url_key
from news_collect.writer import write_doc


class RssAdapter(SourceAdapter):
    name = "rss"
    domains: list[str] = []  # ingest routing for arbitrary blogs is handled by the blogs adapter (deferred)

    def __init__(self, feeds, vault, now: str):
        self.feeds = feeds
        self.vault = vault
        self.now = now
        self._entries: dict[str, dict] = {}  # key -> entry detail, populated by discover()

    def discover(self, state, fresh: bool) -> list[ItemRef]:
        refs: list[ItemRef] = []
        for feed_url in self.feeds:
            parsed = feedparser.parse(feed_url)
            feed_title = parsed.feed.get("title", "")
            for e in parsed.entries:
                link = e.get("link") or e.get("id")
                if not link:
                    continue
                key = url_key(link)
                self._entries[key] = {"entry": e, "feed_title": feed_title, "link": link}
                refs.append(ItemRef(key=key, source=self.name, url=link, title=e.get("title")))
        return refs

    def _body_html(self, entry) -> str:
        if entry.get("content"):
            return entry["content"][0].get("value", "")
        return entry.get("summary", "")

    def fetch(self, items: list[ItemRef]) -> FetchResult:
        written: list[ItemRef] = []
        for ref in items:
            detail = self._entries.get(ref.key)
            if detail is None:
                # ingest path: entry not pre-loaded; fetching a single feed item is out of
                # scope, so skip with no write (counts as not-written).
                continue
            e = detail["entry"]
            doc = NormalizedDoc(
                source=self.name,
                title=e.get("title", "(untitled)"),
                body_md=md(self._body_html(e)).strip(),
                url=detail["link"],
                published=e.get("published"),
                extra_frontmatter={"feed": detail["feed_title"]},
            )
            write_doc(self.vault, doc, collected_at=self.now)
            written.append(ref)
        return FetchResult(status="ok", written=written)
