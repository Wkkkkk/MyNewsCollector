from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SourceState:
    last_run: str | None = None
    seen: set[str] = field(default_factory=set)


def _state_dir(workspace) -> Path:
    d = Path(workspace) / "news-collect" / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(workspace, source: str) -> Path:
    return _state_dir(workspace) / f"{source}.json"


def load_state(workspace, source: str) -> SourceState:
    p = state_path(workspace, source)
    if not p.exists():
        return SourceState()
    data = json.loads(p.read_text(encoding="utf-8"))
    return SourceState(last_run=data.get("last_run"), seen=set(data.get("seen", [])))


def save_state(workspace, source: str, state: SourceState) -> None:
    p = state_path(workspace, source)
    payload = {"last_run": state.last_run, "seen": sorted(state.seen)}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
