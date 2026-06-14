from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "spm")


def url_key(url: str) -> str:
    """Normalize a URL into a stable dedup key (drops tracking params, fragment, trailing slash)."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    kept = [(k, v) for k, v in parse_qsl(parts.query)
            if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)]
    query = urlencode(sorted(kept))
    return urlunsplit((scheme, netloc, path, query, ""))


def file_key(path) -> str:
    """Stable key for a local file: absolute path + short content hash."""
    p = Path(path).resolve()
    digest = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return f"{p}#{digest}"
