# News Collect Agent — Design

**Date:** 2026-06-14
**Status:** Approved (brainstorming) → ready for implementation plan

## Summary

A deterministic, locally-scheduled multi-source content collector built on top of the
existing `zhihu-fetcher` skill. It pulls **new** content from several sources once a week,
normalizes everything to Markdown (frontmatter + local images), and writes it into a single
Obsidian vault. It runs unattended via macOS `launchd`; when a source needs a manual login
(cookie expiry / anti-scraping check), it isolates that source, preserves its checkpoint,
and notifies the user with the exact command to fix it — then resumes on the next run.

Beyond the weekly run, the same engine supports **subset runs** (`--only`/`--skip`) and an
**on-demand `ingest`** mode that takes explicit URLs or local files.

## Goals

- Collect new content weekly from multiple, differently-shaped sources behind one engine.
- Reuse the existing Zhihu scripts rather than rewriting them.
- Be incremental and idempotent by default; re-running never re-imports seen content.
- Survive per-source auth failures without aborting the whole run; make manual login a
  notify-and-resume action, not a crash.
- Make adding future sources purely additive (implement an adapter, add a config entry).

## Non-goals

- Browsing/searching sources or posting content.
- Fully unattended login (manual login is inherent to Zhihu/Xiaohongshu and stays manual).
- Cloud execution — this is local because it needs local cookies, browser, and vault.

## Decisions (from brainstorming)

| Topic | Decision |
|-------|----------|
| Sources | Zhihu, RSS feeds, local markdown (v1); public blogs, Xiaohongshu (deferred) |
| Output sink | Single Obsidian vault, one folder per source, frontmatter-tagged |
| Orchestrator | Thin deterministic Python (`collect.py`); Claude builds it, does not run it |
| Manual-login signal | macOS desktop notification + appended entry in vault `run-log.md` |
| Schedule | `launchd` LaunchAgent, Friday 09:00 local; runs at next wake if asleep |
| Incrementality | Per-source state file; incremental by default; `--fresh` re-pulls |
| Dedup | Stable key per item (URL/guid for web, path+content-hash for local); `--force` bypass |
| Run history | Append dated entries to `run-log.md` (no overwrite) |
| Notifications | Desktop ping every run, including clean runs |
| Test framework | pytest |
| v1 scope | Engine + Zhihu + RSS + local-markdown adapters |

## Architecture

```
                  ┌──────────────────────────────┐
   launchd  ─────▶│   collect.py (orchestrator)   │
  (Fri 9am)       │  reads config, loops sources  │
                  └──────────────┬────────────────┘
                                 │  for each selected source
              ┌──────────────────┼───────────────────┐
              ▼                   ▼                    ▼
        ┌───────────┐      ┌───────────┐        ┌───────────┐
        │ zhihu     │      │ rss       │        │ local-md  │
        │ adapter   │      │ adapter   │        │ adapter   │
        └─────┬─────┘      └─────┬─────┘        └─────┬─────┘
              ▼                  ▼                    ▼
        normalized Markdown + frontmatter + images/  (shared writer)
                                 │
                                 ▼
                   {Vault}/News/{source}/   (+ run-log.md)
```

The orchestrator is source-agnostic: it only knows the adapter contract. Sources behind
auth (Zhihu) and sources without (RSS, local) both conform to the same interface.

## Adapter contract

```python
class SourceAdapter:
    name: str                       # "zhihu", "rss", "local"
    domains: list[str]              # used to route ingest URLs (empty for local)

    def discover(self, state, fresh: bool) -> list[ItemRef]:
        """Return refs for items new since last run (incremental). Skipped in ingest mode."""

    def fetch(self, items: list[ItemRef]) -> FetchResult:
        """Fetch, normalize, and write items to the vault."""

# ItemRef: stable `key` (url/guid, or abspath#contenthash) + source-specific locator
# FetchResult:
#   new_items:  list of written records
#   new_state:  {last_run, seen}        # persisted by orchestrator on status=="ok"
#   status:     "ok" | "needs_login" | "error"
#   message:    human-readable detail for the run-log
```

- **Scheduled run:** `items = discover(state, fresh)` → filter seen → `fetch(items)`.
- **Ingest run:** orchestrator routes inputs to adapters (domain → web adapter,
  unknown domain → blogs adapter, local path → local adapter), then calls `fetch()`
  directly; `discover()` is skipped. In v1 the blogs adapter is deferred, so an
  unknown-domain URL has no route: it is reported as an `error` in the run-log
  ("no adapter for <url>") rather than silently dropped.

### Adapters in v1

- **zhihu** — thin wrapper around existing `scripts/fetch_zhihu_history.py` →
  `fetch_zhihu_batch.py` → `format_articles.py` → `write_to_obsidian.py`. Detects cookie
  expiry / 安全验证 and returns `needs_login`. Within-source resume uses the existing
  `_progress.json`.
- **rss** — `feedparser` for discovery + readability extraction for bodies + shared writer.
- **local** — reads markdown files/dirs, dedups by `abspath#contenthash` (edited file
  re-imports; unchanged file skipped), writes through the shared writer.

## Invocation surface

```bash
# Scheduled / full run (launchd fires this) — all enabled sources, incremental
collect.py

# Subset control
collect.py --skip zhihu
collect.py --only rss,local
collect.py --fresh --only zhihu        # ignore state, re-pull

# On-demand ingest — explicit inputs, no discovery
collect.py ingest https://... https://...
collect.py ingest --from urls.txt
collect.py ingest ~/notes/clippings/   # local files/dirs (v1)

# Global flags: --fresh, --force (bypass dedup), --dry-run (preview, write nothing)
```

## State, dedup, and the run loop

Per-source state file (separate files so sources can't corrupt each other):

```
{workspace}/news-collect/state/{source}.json
  { "last_run": "<ISO8601>", "seen": ["<key>", ...] }
```

Run loop (after `--only`/`--skip` filtering):

```
for source in selected_sources:
    try:
        items = adapter.discover(state, fresh)          # skipped in ingest mode
        items = [i for i in items if i.key not in state.seen]   # unless --force
        if dry_run: record "would fetch N"; continue
        result = adapter.fetch(items)
        if result.status == "ok":
            state.update(last_run=now, seen += result.keys); save(state)
        else:
            record(result.status, result.message)        # state left intact
    except Exception as e:
        record("error", e)                                # one bad source never aborts run
    finally:
        append outcome to run summary
```

Properties:

- **Fault isolation** — a throwing or `needs_login` source is caught; healthy sources still complete.
- **Idempotent + resumable** — state advances only on `ok`, so re-running resumes the
  unfinished window. Combined with Zhihu's `_progress.json` for within-source resume.
- **`needs_login` is a status, not a crash** — adapters signal it explicitly.

## Notification & run-log

At the end of every run:

- Append a dated entry (newest on top) to **`{Vault}/News/run-log.md`**: timestamp,
  per-source status table (`ok`/`needs_login`/`error` + counts), and the exact remediation
  command per problem, e.g.:
  > **zhihu — needs login.** Run `python scripts/zhihu_relogin.py`, then `python news_collect/collect.py --only zhihu`.
- Fire one macOS desktop notification (`osascript`, or `terminal-notifier` if present) every
  run, including clean runs — e.g. *"News collect ✓ — 12 new, all sources OK"* or
  *"News collect — 12 new, Zhihu needs login."*

## Scheduling (launchd)

User LaunchAgent at `~/Library/LaunchAgents/com.kunwu.news-collect.plist`, generated from a
template in `deploy/`:

- `StartCalendarInterval`: Weekday 5 (Friday), Hour 9, Minute 0 (local time).
- Runs at next wake if the Mac was asleep at fire time (launchd default).
- Command: repo `venv/bin/python` running `news_collect/collect.py` (absolute paths).
- Explicitly sets `OPENCLAW_WORKSPACE` and `OBSIDIAN_VAULT` (launchd does not inherit the
  shell profile).
- `StandardOutPath`/`StandardErrorPath` → `{workspace}/news-collect/logs/launchd.{out,err}.log`.

Operated via `launchctl load|unload|start`; documented in the README.

## Repo layout

```
zhihu/
├── scripts/                    # EXISTING Zhihu scripts — untouched
├── news_collect/               # NEW
│   ├── collect.py              # CLI: scheduled run + ingest subcommand
│   ├── orchestrator.py         # run loop, state, run-log, notify
│   ├── contract.py             # SourceAdapter base, ItemRef, FetchResult
│   ├── routing.py              # domain/path → adapter (ingest)
│   ├── writer.py               # shared normalize → vault markdown+frontmatter+images
│   ├── notify.py               # macOS desktop notification
│   ├── config.toml             # sources, vault path, feeds, zhihu target
│   └── adapters/
│       ├── zhihu.py
│       ├── rss.py
│       └── local.py
├── deploy/
│   └── com.kunwu.news-collect.plist.template
└── docs/superpowers/specs/2026-06-14-news-collect-agent-design.md
```

`config.toml` drives enabled sources, RSS feed URLs, the Zhihu profile/collection target, and
the vault path. Adding a source = new file in `adapters/` + a config entry.

## Testing (pytest)

- **Unit (no network) — core of the suite:**
  - Run loop with fake adapters per status: fault isolation, state advances only on `ok`,
    `needs_login` leaves state intact.
  - Dedup: URL keys and path+hash keys; `--force` bypass; edited-file re-import.
  - Routing: URL→adapter by domain, unknown→blogs (deferred placeholder), local path→local.
  - Selection: `--only`/`--skip`/`--dry-run`.
  - run-log append format; notify message construction (injected fake notifier).
- **Adapter-level:**
  - RSS against a saved sample-feed fixture (no live network) → normalized output + frontmatter.
  - local adapter against a temp dir of markdown files → dedup/hash behavior.
  - Zhihu adapter: test the translation layer (args in, status out, `_progress.json` parsing)
    with underlying scripts mocked; do not re-test the existing scripts.
- **Manual smoke test (documented):** `launchctl start` once; confirm run-log entry +
  desktop ping appear.

Approach: TDD for orchestrator/dedup/routing (pure logic); fixture tests for adapters; manual
smoke for launchd wiring.

## v1 scope vs deferred

**v1 (this build):** engine + CLI (`--only`/`--skip`/`--fresh`/`--force`/`--dry-run` +
`ingest`) + state/dedup/routing + run-log + desktop notify + launchd plist +
**zhihu, rss, local** adapters + pytest suite + manual smoke test.

**Deferred (framework supports; additive later):**

- **blogs** adapter (readability) — also the default route for unknown-domain `ingest` URLs.
- **xiaohongshu** adapter — hardest, aggressive anti-scraping; dedicated effort.

## Open risks

- Xiaohongshu anti-scraping is materially harder than Zhihu; scoped out of v1 deliberately.
- launchd env/path footguns (no shell profile) — mitigated by explicit env in the plist and
  the pre-run launchd log files.
- RSS body extraction quality varies by site; readability is best-effort, acceptable for v1.
