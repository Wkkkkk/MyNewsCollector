from __future__ import annotations

from pathlib import Path

from news_collect.contract import SourceAdapter, ItemRef, FetchResult, NormalizedDoc
from news_collect.keys import file_key
from news_collect.writer import write_doc


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
            doc = NormalizedDoc(
                source=self.name,
                title=ref.title or src.stem,
                body_md=src.read_text(encoding="utf-8"),
                extra_frontmatter={"source_path": str(src)},
            )
            write_doc(self.vault, doc, collected_at=self.now)
            written.append(ref)
        return FetchResult(status="ok", written=written)
