---
name: zhihu-fetcher
description: "Use when the user wants Zhihu (知乎) content pulled onto their machine. Triggers: download or archive a collection (收藏夹) of answers/articles; batch-fetch article bodies as Markdown with local images (批量下载/批量抓取); resume an interrupted scrape (续传/断点续传) or point at an existing zhihu_articles_*/ output dir; recover from cookie expiry, login, or an anti-scraping check (安全验证) during a scrape; export liked/saved history (点赞/收藏历史) or a 专栏 author's articles; fix mangled Markdown exported from Zhihu; or sync any of the above into an Obsidian vault. Works whether the user writes in Chinese or English. Not for: browsing or searching Zhihu, writing Zhihu posts, or general questions about Zhihu features/membership."
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, WebFetch
metadata:
  version: "1.4.0"
---

# Zhihu Content Fetcher

Fetch **collection article lists** or **personal like/save history** from Zhihu, batch-scrape **body Markdown** (with local image copies), and optionally sync into an **Obsidian** vault. For a visual overview see [`README.md`](README.md) at the repo root.

## When this triggers

- Explicit mention of: Zhihu, 知乎, 专栏 (column), 收藏夹 (collection), article scraping, batch download, like/save history, Cookie, CAPTCHA, Obsidian, knowledge-base sync, etc.
- User pastes a **zhihu.com** / **zhuanlan.zhihu.com** URL and wants the body text or a list
- Needs help with **resume/checkpoint**, **local image storage**, or **anti-scraping / Stealth** issues

## Environment & conventions

- **Language**: This skill is authored in English; respond and produce content in the user's language.
- **Skill root**: `${CLAUDE_SKILL_DIR}` refers to the root of this skill repo (some host UIs write it as `{baseDir}` — same meaning). All scripts live under `scripts/`.
- **Workspace directory** `{workspace}`: set by env var **`OPENCLAW_WORKSPACE`**; defaults to `~/.openclaw/workspace/` when unset. Stores cookies, browser data, and default output. See [references/paths.md](references/paths.md).
- **Dependencies**: run `pip install -r requirements.txt` inside `scripts/`, then `playwright install chromium`.

## Main flow: collection → batch → format → Obsidian

```bash
# 1. Collection list (API preferred; falls back to Playwright DOM on failure)
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_collection.py" <collectionURL-or-ID>

# 2. Batch-scrape body text & images → zhihu_articles_{collectionId}/  (contains _progress.json, images/, numbered *.md)
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_batch.py" <list.json> [output-dir] [images-dir]

# 3. Conservative formatting (recommended: run --dry-run --diff first to preview)
python "${CLAUDE_SKILL_DIR}/scripts/format_articles.py" <articles-dir> [--dry-run --diff]

# 4. (Optional) Write to Obsidian → {Vault}/{root}/{category}/  (default root: Zhihu Collection)
python "${CLAUDE_SKILL_DIR}/scripts/write_to_obsidian.py" <articles-dir> [vault-path] [--root-folder NAME]
```

**Resume / checkpoint**: if a batch job is interrupted, re-run the same `fetch_zhihu_batch.py` command to continue — completed URLs are recorded in `_progress.json`.

## Personal history flow (likes / saves)

Applies to activity entries on a personal profile page: **赞同了回答 / 赞同了文章 / 收藏了回答 / 收藏了文章** (liked/saved answer/article). Timestamps use ISO format; if no timezone is supplied the scripts default to **Europe/Stockholm**.

```bash
# 1. Collect activity list (start inclusive, end exclusive); re-run to resume after interruption; --fresh ignores checkpoint and rebuilds
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_history.py" \
  https://www.zhihu.com/people/<slug> \
  2026-01-01T00:00:00+01:00 \
  <output.json> \
  --until 2026-04-05T00:00:00+02:00

# 2. Batch-scrape body text & images (failed items auto-retried 3 times by default)
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_batch.py" <output.json> <articles-dir>

# 3. Conservative formatting (--set-times stamps files with interaction_time)
python "${CLAUDE_SKILL_DIR}/scripts/format_articles.py" <articles-dir> --set-times

# 4. Write to Obsidian (deduplicates by URL, preserves interaction time and action labels)
python "${CLAUDE_SKILL_DIR}/scripts/write_zhihu_history_to_obsidian.py" <articles-dir> <vault-path> .
```

History notes retain interaction metadata such as `interaction_action` / `interaction_time` / `interaction_date` in their frontmatter; see [references/paths.md](references/paths.md) for the format.

## Script routing

| Task | Script | Notes |
|------|--------|-------|
| Collection JSON list | `fetch_zhihu_collection.py <collectionURL-or-ID>` | Auto-switches API ↔ DOM; outputs `zhihu_collection_{id}.json` |
| Personal like/save history list | `fetch_zhihu_history.py <people-URL-or-slug> <start-ISO> <output.json> [--until <end-ISO>] [--fresh]` | Preserves `interaction_*` metadata; resumable |
| Batch-scrape body & images | `fetch_zhihu_batch.py <list.json> [output-dir] [images-dir] [--retry-failed]` | Recommended entry point; keepalive, retry, and resume built in |
| Format scraped Markdown | `format_articles.py <dir-or-.md...> [--dry-run --diff --set-times]` | Conservative fixes; see [references/formatting.md](references/formatting.md) |
| Write to Obsidian | `write_to_obsidian.py <articles-dir> [vault-path] [--root-folder NAME]` | Vault: CLI arg > `OBSIDIAN_VAULT` > auto-scan. Root folder: `--root-folder` > `ZHIHU_OBSIDIAN_ROOT` > default `Zhihu Collection`. Set `ZHIHU_OBSIDIAN_ROOT=知乎收藏` for the old Chinese layout (backward compat). |
| Write personal history to Obsidian | `write_zhihu_history_to_obsidian.py <articles-dir> <vault-path> [.]` | Deduplicates by URL |
| Write failures list | `write_zhihu_failures.py <vault-path> <tag>:<progress.json> ... [--root-folder NAME] [--failures-name NAME]` | Outputs `{Vault}/{root}/fetch-failures.md`. Env vars: `ZHIHU_OBSIDIAN_ROOT` (default `Zhihu Collection`), `ZHIHU_FAILURES_FILE` (default `fetch-failures.md`). Set `ZHIHU_OBSIDIAN_ROOT=知乎收藏` + `ZHIHU_FAILURES_FILE=抓取失败.md` to keep the old Chinese paths (backward compat). |
| Re-login after cookie expiry | `zhihu_relogin.py` | Opens a browser window |
| First-time login helper | `zhihu_login.py [verify-URL]` | Detects `z_c0`; optional page verification — see [references/cookie-keepalive.md](references/cookie-keepalive.md) |
| Single-article quick test / debug | `fetch_zhihu.py` (auto multi-strategy) / `fetch_zhihu_api.py` (direct API) / `fetch_zhihu_stealth.py` (stealth) / `fetch_zhihu_interactive.py` (interactive, handles login-page 安全验证 (security-check page)) | Use for single articles or debugging; avoid unnecessary batch runs |
| Read local Markdown, inspect `_progress.json` | — | Use `Read` / `Grep` directly |

## Reference docs (read as needed)

| File | When to read |
|------|-------------|
| [references/paths.md](references/paths.md) | To confirm default output paths, article frontmatter format, Obsidian vault resolution, or category rules |
| [references/cookie-keepalive.md](references/cookie-keepalive.md) | Login / cookie expiry / keepalive mechanism questions |
| [references/failure-handling.md](references/failure-handling.md) | Batch-scrape failures, understanding the two-tier failure strategy, or `--retry-failed` |
| [references/formatting.md](references/formatting.md) | Details of `format_articles.py` fix rules and `--set-times` behaviour |
| [references/troubleshooting.md](references/troubleshooting.md) | Empty body, 安全验证 (security-check page), anti-scraping, image failures |

## Workflow checklist

```
□ scripts dependencies and playwright chromium available; prompt user to set OPENCLAW_WORKSPACE if needed
□ Collection task: run fetch_zhihu_collection.py first to get a valid JSON, then fetch_zhihu_batch.py
□ After batch: conservative format_articles.py (--dry-run --diff on first run), then write to Obsidian
□ On security-check page or empty body: fix Cookie / re-login first; don't increase concurrency
□ Single article or debugging: use a single-article script; avoid unnecessary batch runs
```
