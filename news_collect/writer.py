from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import yaml

from news_collect.contract import NormalizedDoc


def slugify(title: str) -> str:
    """ASCII-friendly slug; falls back to a hash for non-ASCII-only titles."""
    norm = unicodedata.normalize("NFKD", title or "")
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    if slug:
        return slug
    if title.strip():
        return "t-" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:10]
    return "untitled"


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
