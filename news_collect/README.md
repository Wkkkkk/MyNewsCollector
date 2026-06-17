# News Collect

Deterministic multi-source content collector. Pulls new content from configured sources into
`{Vault}/News/{source}/`, incremental and idempotent, with desktop notifications and a
`run-log.md`. See the design spec at `docs/superpowers/specs/2026-06-14-news-collect-agent-design.md`.

## Setup

```bash
venv/bin/pip install -r news_collect/requirements.txt
```

Edit `news_collect/config.toml` (or pass `--config`): set `vault`, RSS `feeds`, the Zhihu
`profile`/`start`, and `local` `paths`. Enable/disable each source with `enabled = true/false`.
If `vault` is empty, the `OBSIDIAN_VAULT` env var is used.

All commands are run from the repo root using the module form (`-m news_collect.collect`).

## Usage

```bash
# Weekly full run (all enabled sources, incremental)
venv/bin/python -m news_collect.collect

# Subset control
venv/bin/python -m news_collect.collect --skip zhihu
venv/bin/python -m news_collect.collect --only rss,local
venv/bin/python -m news_collect.collect --fresh --only zhihu   # re-pull, ignore state

# Preview without writing
venv/bin/python -m news_collect.collect --dry-run

# On-demand ingest (URLs route by domain; local paths handled by the local adapter)
venv/bin/python -m news_collect.collect ingest https://www.zhihu.com/p/123
venv/bin/python -m news_collect.collect ingest ~/notes/clippings/
venv/bin/python -m news_collect.collect ingest --from urls.txt
# --force re-imports already-seen items
```

When Zhihu reports `needs_login`, the run-log and notification tell you to run
`scripts/zhihu_relogin.py`, then re-run `-m news_collect.collect --only zhihu` — it resumes
from checkpoint.

## Schedule (launchd, 09:00 local)

Two jobs run on different cadences:

- `com.kunwu.news-collect` — **Friday 09:00**, `--skip local` (rss + zhihu)
- `com.kunwu.news-collect-local` — **every morning 09:00**, `--only local`

```bash
REPO="$(pwd)"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
VAULT="/absolute/path/to/your/Obsidian/Vault"
CONFIG="$REPO/news_collect/config.local.toml"
mkdir -p "$WORKSPACE/news-collect/logs"
for tmpl in com.kunwu.news-collect com.kunwu.news-collect-local; do
  sed -e "s#__REPO__#$REPO#g" -e "s#__WORKSPACE__#$WORKSPACE#g" \
      -e "s#__VAULT__#$VAULT#g" -e "s#__CONFIG__#$CONFIG#g" \
      "deploy/$tmpl.plist.template" \
      > "$HOME/Library/LaunchAgents/$tmpl.plist"
  launchctl load "$HOME/Library/LaunchAgents/$tmpl.plist"
done
```

Manage:

```bash
launchctl start com.kunwu.news-collect          # run weekly (rss+zhihu) now
launchctl start com.kunwu.news-collect-local     # run daily (local) now
launchctl unload ~/Library/LaunchAgents/com.kunwu.news-collect.plist   # disable
```

## Manual smoke test

1. `launchctl start com.kunwu.news-collect`
2. Confirm a new dated entry appears in `{Vault}/News/run-log.md`.
3. Confirm a desktop notification fired.
4. If anything failed, check `{Workspace}/news-collect/logs/launchd.err.log`.

## Adding a source later

Implement a `SourceAdapter` subclass in `news_collect/adapters/`, register it in
`build_adapters()` in `collect.py`, and add a `[sources.<name>]` block to `config.toml`.
Deferred adapters: **blogs** (readability; also the route for unknown-domain ingest URLs) and
**xiaohongshu**.
