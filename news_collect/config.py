from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    vault: str
    sources: dict

    def enabled_sources(self) -> list[str]:
        return [name for name, s in self.sources.items() if s.get("enabled")]

    def source(self, name: str) -> dict:
        return self.sources.get(name, {})


def load_config(path) -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    vault = data.get("vault") or os.environ.get("OBSIDIAN_VAULT", "")
    return Config(vault=vault, sources=data.get("sources", {}))
