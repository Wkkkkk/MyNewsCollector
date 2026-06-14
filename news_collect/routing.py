from __future__ import annotations

from urllib.parse import urlsplit

from news_collect.contract import SourceAdapter


def is_local_path(target: str) -> bool:
    return not target.lower().startswith(("http://", "https://"))


def route(target: str, adapters: list[SourceAdapter]) -> SourceAdapter | None:
    """Pick the adapter for an ingest target. Local paths -> the 'local' adapter;
    URLs -> the adapter whose domains match. Returns None if no adapter matches."""
    by_name = {a.name: a for a in adapters}
    if is_local_path(target):
        return by_name.get("local")
    host = urlsplit(target).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for adapter in adapters:
        for d in adapter.domains:
            if host == d or host.endswith("." + d):
                return adapter
    return None
