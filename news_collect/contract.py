from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ItemRef:
    """A reference to one collectable item, with a stable dedup key."""
    key: str
    source: str
    url: str | None = None
    path: str | None = None
    title: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class NormalizedDoc:
    """Source-agnostic document ready to be written to the vault."""
    source: str
    title: str
    body_md: str
    url: str | None = None
    published: str | None = None
    extra_frontmatter: dict = field(default_factory=dict)


@dataclass
class FetchResult:
    """Outcome of an adapter.fetch() call."""
    status: str  # "ok" | "needs_login" | "error"
    written: list[ItemRef] = field(default_factory=list)
    message: str = ""

    @property
    def keys(self) -> list[str]:
        return [item.key for item in self.written]


class SourceAdapter(ABC):
    """Interface every source adapter implements."""
    name: str = ""
    domains: list[str] = []

    @abstractmethod
    def discover(self, state, fresh: bool) -> list[ItemRef]:
        """Return refs for items new since last run (scheduled mode)."""

    @abstractmethod
    def fetch(self, items: list[ItemRef]) -> FetchResult:
        """Fetch, normalize, and write the given items. Returns a FetchResult."""

    def refs_for(self, targets: list[str]) -> list[ItemRef]:
        """Build ItemRefs from explicit ingest targets (URLs by default)."""
        return [ItemRef(key=t, source=self.name, url=t) for t in targets]
