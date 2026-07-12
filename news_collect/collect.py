from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from news_collect.adapters.local import LocalAdapter
from news_collect.adapters.rss import RssAdapter
from news_collect.adapters.zhihu import ZhihuAdapter
from news_collect.config import load_config, Config
from news_collect.notify import MacNotifier
from news_collect.orchestrator import run_scheduled, run_ingest
from news_collect.runlog import outcome_stats

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")
EX_NOTHING_NEW = 44  # ran OK but produced nothing new (shared launchd-catchup contract)


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


def _scheduled_exit_code(outcomes) -> int:
    """Tri-state per the launchd-catchup job contract:
      1  — total failure: every selected source failed (nothing produced).
      44 — ran OK but nothing new: all sources ok and 0 new items.
      0  — produced new output (or partial success with a problem present).
    Empty selection -> 0."""
    if not outcomes:
        return 0
    if all(o.status != "ok" for o in outcomes):
        return 1
    total_new, problems = outcome_stats(outcomes)
    if not problems and total_new == 0:
        return EX_NOTHING_NEW
    return 0


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
    # Clicking the notification opens the News run-log note in Obsidian, landing in
    # the News folder alongside the freshly-collected notes.
    news_url = "obsidian://open?path=" + urllib.parse.quote(str(runlog_path))
    notifier = MacNotifier(open_url=news_url)
    ctx = dict(workspace=workspace, vault=cfg.vault, now=now,
               notifier=notifier, runlog_path=runlog_path)

    def _notify_crash(exc):
        # A hard crash (not a handled per-source failure) never reaches the normal
        # notification, so fire one here pointing at the launchd error log.
        err_log = Path(workspace) / "news-collect" / "logs" / "launchd.err.log"
        try:
            subprocess.run(["/usr/local/bin/terminal-notifier",
                            "-title", "📰 News collect — CRASHED",
                            "-message", f"{type(exc).__name__}: {str(exc)[:150]} — click for the error log",
                            "-group", "news-collect",
                            "-execute", f"open {shlex.quote(str(err_log))}"],
                           check=False)
        except FileNotFoundError:
            pass  # terminal-notifier absent — non-fatal

    try:
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
        outcomes = run_scheduled(adapters, selected=selected, fresh=args.fresh,
                                 force=args.force, dry_run=args.dry_run, **ctx)
        return _scheduled_exit_code(outcomes)
    except Exception as exc:  # hard crash: still fire a clickable failure alert
        _notify_crash(exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
