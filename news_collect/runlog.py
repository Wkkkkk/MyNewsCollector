from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_HEADER = "# News Collect — Run Log\n\n"


@dataclass
class SourceOutcome:
    source: str
    status: str  # "ok" | "needs_login" | "error"
    count: int
    message: str


def _entry(outcomes: list[SourceOutcome], now: str) -> str:
    lines = [f"## {now}\n", "| Source | Status | New | Detail |", "|---|---|---|---|"]
    for o in outcomes:
        detail = o.message.replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {o.source} | {o.status} | {o.count} | {detail} |")
    return "\n".join(lines) + "\n\n"


def append_runlog(path, outcomes: list[SourceOutcome], now: str) -> None:
    """Prepend a dated entry (newest on top) to the run-log markdown file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text(encoding="utf-8") if p.exists() else _HEADER
    body = existing[len(_HEADER):] if existing.startswith(_HEADER) else existing
    p.write_text(_HEADER + _entry(outcomes, now) + body, encoding="utf-8")
