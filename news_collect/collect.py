from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from news_collect.adapters.local import LocalAdapter
from news_collect.adapters.rss import RssAdapter
from news_collect.adapters.zhihu import ZhihuAdapter
from news_collect.config import load_config, Config
from news_collect.notify import MacNotifier
from news_collect.orchestrator import run_scheduled, run_ingest

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")


def select_sources(enabled: list[str], only: str | None, skip: str | None) -> list[str]:
    if only:
        wanted = [s.strip() for s in only.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in enabled]
        if unknown:
            raise ValueError(f"--only names unknown/disabled sources: {unknown}")
        return wanted
    if skip:
        dropped = {s.strip() for s in skip.split(",")}
        return [s for s in enabled if s not in dropped]
    return list(enabled)


def build_adapters(cfg: Config, *, workspace, now: str, skill_dir: str):
    adapters = []
    for name in cfg.enabled_sources():
        s = cfg.source(name)
        if name == "rss":
            adapters.append(RssAdapter(feeds=s.get("feeds", []), vault=cfg.vault, now=now))
        elif name == "local":
            adapters.append(LocalAdapter(paths=s.get("paths", []), vault=cfg.vault, now=now))
        elif name == "zhihu":
            adapters.append(ZhihuAdapter(profile=s.get("profile", ""), start=s.get("start", ""),
                                         vault=cfg.vault, workspace=workspace, now=now,
                                         skill_dir=skill_dir))
    return adapters


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="collect.py", description="Multi-source news collector")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--only")
    parser.add_argument("--skip")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="cmd")
    ing = sub.add_parser("ingest", help="ingest explicit URLs or local paths")
    ing.add_argument("targets", nargs="*")
    ing.add_argument("--from", dest="from_file")
    args = parser.parse_args(argv)

    skill_dir = os.environ.get("CLAUDE_SKILL_DIR", str(Path(__file__).resolve().parents[1]))
    workspace = os.environ.get("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw" / "workspace"))
    now = _now_iso()

    cfg = load_config(args.config)
    if not cfg.vault:
        print("error: no vault configured (set 'vault' in config.toml or OBSIDIAN_VAULT)", file=sys.stderr)
        return 2

    adapters = build_adapters(cfg, workspace=workspace, now=now, skill_dir=skill_dir)
    runlog_path = Path(cfg.vault) / "News" / "run-log.md"
    notifier = MacNotifier()
    ctx = dict(workspace=workspace, vault=cfg.vault, now=now,
               notifier=notifier, runlog_path=runlog_path)

    if args.cmd == "ingest":
        targets = list(args.targets)
        if args.from_file:
            targets += [ln.strip() for ln in Path(args.from_file).read_text().splitlines() if ln.strip()]
        run_ingest(adapters, targets, force=args.force, dry_run=args.dry_run, **ctx)
        return 0

    try:
        selected = select_sources([a.name for a in adapters], args.only, args.skip)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    run_scheduled(adapters, selected=selected, fresh=args.fresh, force=args.force,
                  dry_run=args.dry_run, **ctx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
