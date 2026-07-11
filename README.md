# MyNewsCollector

A personal news pipeline that lands everything in an [Obsidian](https://obsidian.md/) vault:

- **`news_collect/`** — the centerpiece. A deterministic multi-source collector (RSS, Zhihu,
  local clippings) that runs on a launchd schedule, writes Markdown into
  `{Vault}/News/{source}/`, and keeps a `run-log.md` plus desktop notifications.
- **`scripts/`** — a forked **Zhihu Fetcher skill** (see [Upstream attribution](#upstream-attribution))
  that powers the Zhihu source: collection lists, like/save history, batch article scraping with
  local images, checkpoint resume, cookie keep-alive, and Obsidian sync.

[![CI](https://github.com/Wkkkkk/MyNewsCollector/actions/workflows/test.yml/badge.svg)](https://github.com/Wkkkkk/MyNewsCollector/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-45ba4b.svg)](https://playwright.dev/)

---

## The collector (`news_collect/`)

Pulls new content from each enabled source, incrementally and idempotently. Full details in
[`news_collect/README.md`](news_collect/README.md).

### Setup

```bash
python -m venv venv
venv/bin/pip install -r news_collect/requirements.txt -r scripts/requirements.txt
venv/bin/playwright install chromium   # only needed for the Zhihu source
```

Copy `news_collect/config.toml` to `news_collect/config.local.toml` (git-ignored) and set your
vault path, RSS feeds, Zhihu profile, and local clipping paths. If `vault` is empty, the
`OBSIDIAN_VAULT` env var is used.

### Usage

```bash
# Weekly full run (all enabled sources, incremental)
venv/bin/python -m news_collect.collect --config news_collect/config.local.toml

# Subset control
venv/bin/python -m news_collect.collect --only rss,local
venv/bin/python -m news_collect.collect --skip zhihu
venv/bin/python -m news_collect.collect --dry-run

# On-demand ingest (URLs route by domain; local paths go to the local adapter)
venv/bin/python -m news_collect.collect ingest https://www.zhihu.com/p/123
venv/bin/python -m news_collect.collect ingest ~/notes/clippings/
```

When Zhihu reports `needs_login`, run `scripts/zhihu_relogin.py` and re-run
`--only zhihu` — it resumes from checkpoint.

### Scheduled deployment (launchd, macOS)

Two LaunchAgents are generated from the templates in [`deploy/`](deploy/):

| Job | Cadence | What it runs |
|-----|---------|--------------|
| `com.kunwu.news-collect` | Friday 09:00 | `--skip local` (rss + zhihu) |
| `com.kunwu.news-collect-local` | daily 09:00 | `--only local` (clippings) |

See the "Schedule" section of [`news_collect/README.md`](news_collect/README.md) for the
`sed`-and-`launchctl load` install snippet and the manual smoke test.

---

## The Zhihu fetcher skill (`scripts/` + `SKILL.md`)

The repo root doubles as an [AgentSkills](https://agentskills.io)-style skill: the entry point
is [`SKILL.md`](SKILL.md) and all scripts live under `scripts/`. It can also be driven by hand:

```bash
# 1. Collection → JSON list (API preferred; Playwright DOM fallback)
python scripts/fetch_zhihu_collection.py <collection_url_or_id>

# 2. Bulk-fetch article bodies and images (checkpointed via _progress.json)
python scripts/fetch_zhihu_batch.py <list.json>

# 3. Conservative formatting (preview first with --dry-run --diff)
python scripts/format_articles.py <articles_dir>

# 4. Write to Obsidian, auto-categorized under "Zhihu Collection/"
python scripts/write_to_obsidian.py <articles_dir> [vault_path]
```

Personal like/save history is the same pipeline via `fetch_zhihu_history.py` and
`write_zhihu_history_to_obsidian.py` (URL-deduplicated). The Obsidian root folder and the
failures file are configurable via `--root-folder` / `--failures-name` or the
`ZHIHU_OBSIDIAN_ROOT` / `ZHIHU_FAILURES_FILE` env vars (set `ZHIHU_OBSIDIAN_ROOT=知乎收藏`
for the original Chinese layout). When the cookie session breaks: `python scripts/zhihu_relogin.py`.

---

## Project structure

```
MyNewsCollector/
├── news_collect/            # Multi-source collector (the main program)
│   ├── collect.py           #   CLI entry point (python -m news_collect.collect)
│   ├── orchestrator.py      #   Scheduled runs + on-demand ingest
│   ├── adapters/            #   rss.py, zhihu.py, local.py
│   ├── writer.py, state.py, runlog.py, notify.py, ...
│   ├── config.toml          #   Template config (copy to config.local.toml)
│   └── README.md            #   Setup, usage, launchd deployment
├── scripts/                 # Zhihu fetcher skill scripts (forked, see below)
│   ├── fetch_zhihu_collection.py, fetch_zhihu_history.py, fetch_zhihu_batch.py
│   ├── format_articles.py, write_to_obsidian.py, write_zhihu_history_to_obsidian.py
│   ├── zhihu_login.py, zhihu_relogin.py, zhihu_obsidian_config.py, ...
│   └── requirements.txt
├── SKILL.md                 # Skill entry point: triggers, commands, path conventions
├── tests/                   # pytest suite (news_collect/ + scripts/)
├── deploy/                  # launchd plist templates for the two scheduled jobs
├── references/              # Skill reference docs (paths, cookies, failure handling, ...)
├── docs/                    # Screenshots + design specs
└── .github/workflows/       # CI: pytest on Python 3.11 / 3.13
```

## Tests

```bash
venv/bin/pip install pytest
venv/bin/python -m pytest        # pytest.ini points at tests/
```

---

## Upstream attribution

The Zhihu fetcher skill (`SKILL.md`, `scripts/`, `references/`) is a fork of
[**handsomestWei/zhihu-fetch-skill**](https://github.com/handsomestWei/zhihu-fetch-skill),
adapted and extended in this repo (see the git history for details — e.g. access
classification, cookie-expiry preservation, configurable Obsidian layout) and wrapped by
the `news_collect` pipeline.

Licensed under the [MIT License](LICENSE), © [handsomestWei](https://github.com/handsomestWei/).
