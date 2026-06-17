from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import yaml

from news_collect.contract import NormalizedDoc


def slugify(title: str) -> str:
    """Filesystem-friendly slug that preserves Unicode word characters (incl. CJK).

    ASCII letters are lowercased; runs of non-word characters collapse to a single
    hyphen. Full-width punctuation and forms normalize to their ASCII equivalents
    first, so they drop out cleanly. Returns 'untitled' only when the title has no
    word characters at all.
    """
    norm = unicodedata.normalize("NFKC", title or "")
    slug = re.sub(r"[^\w]+", "-", norm, flags=re.UNICODE).strip("-").lower()
    return slug[:80] if slug else "untitled"


def _filename(doc: NormalizedDoc) -> str:
    base = slugify(doc.title)
    # disambiguate with a short hash of the identity (url or title)
    ident = doc.url or doc.title
    suffix = hashlib.sha256(ident.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{suffix}.md"


def write_doc(vault, doc: NormalizedDoc, collected_at: str) -> Path:
    """Write a NormalizedDoc to {vault}/News/{source}/<slug>-<hash>.md. Returns the path."""
    folder = Path(vault) / "News" / doc.source
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _filename(doc)

    frontmatter = {"source": doc.source, "title": doc.title}
    if doc.url:
        frontmatter["url"] = doc.url
    if doc.published:
        frontmatter["published"] = doc.published
    frontmatter["collected_at"] = collected_at
    frontmatter.update(doc.extra_frontmatter)

    fm_yaml = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{fm_yaml}\n---\n\n{doc.body_md}\n", encoding="utf-8")
    return path
