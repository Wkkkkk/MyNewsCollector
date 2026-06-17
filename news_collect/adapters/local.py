from __future__ import annotations

import re
from pathlib import Path

import yaml

from news_collect.contract import SourceAdapter, ItemRef, FetchResult, NormalizedDoc
from news_collect.keys import file_key
from news_collect.writer import write_doc

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a leading YAML frontmatter block from a markdown string.

    Returns (frontmatter_dict, body). If the text has no parseable leading
    block, returns ({}, text) so the whole file is treated as body.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, text
    if not isinstance(fm, dict):
        return {}, text
    return fm, m.group(2)


class LocalAdapter(SourceAdapter):
    name = "local"
    domains: list[str] = []

    def __init__(self, paths, vault, now: str):
        self.paths = paths
        self.vault = vault
        self.now = now

    def _iter_md(self, roots) -> list[Path]:
        files: list[Path] = []
        for root in roots:
            p = Path(root).expanduser()
            if p.is_dir():
                files.extend(sorted(p.rglob("*.md")))
            elif p.is_file() and p.suffix == ".md":
                files.append(p)
        return files

    def _refs(self, files) -> list[ItemRef]:
        return [ItemRef(key=file_key(f), source=self.name, path=str(Path(f).resolve()),
                        title=f.stem) for f in files]

    def discover(self, state, fresh: bool) -> list[ItemRef]:
        return self._refs(self._iter_md(self.paths))

    def refs_for(self, targets: list[str]) -> list[ItemRef]:
        return self._refs(self._iter_md(targets))

    def fetch(self, items: list[ItemRef]) -> FetchResult:
        written: list[ItemRef] = []
        for ref in items:
            src = Path(ref.path)
            fm, body = split_frontmatter(src.read_text(encoding="utf-8"))

            extra = {"source_path": str(src)}
            url = None
            for k, v in fm.items():
                if k in ("title", "source"):
                    continue
                extra[k] = v
            origin = fm.get("source")
            if isinstance(origin, str) and origin.startswith(("http://", "https://")):
                url = origin
            elif origin:
                extra["origin"] = origin  # preserve a non-URL source without clobbering source: local

            doc = NormalizedDoc(
                source=self.name,
                title=fm.get("title") or ref.title or src.stem,
                url=url,
                body_md=body,
                extra_frontmatter=extra,
            )
            write_doc(self.vault, doc, collected_at=self.now)
            written.append(ref)
        return FetchResult(status="ok", written=written)
