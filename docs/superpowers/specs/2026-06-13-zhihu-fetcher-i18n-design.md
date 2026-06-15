# Design: zhihu-fetcher — English conversion + trigger optimization

**Date:** 2026-06-13
**Skill:** `zhihu-fetcher` (repo root = skill root)
**Target version:** 1.3.0 → 1.4.0

## Problem & goals

The `zhihu-fetcher` skill is authored in mixed Chinese/English. We want it to be
English-authored for a **public, mixed-language audience** (users may phrase requests in
Chinese *or* English), while:

1. Not regressing — ideally improving — trigger accuracy. The current description has
   **~0% recall** in the eval loop (`eval-workspace/run_loop.log`): precision 100% but it
   almost never fires when it should.
2. Keeping the skill functional for Chinese users (queries, and Zhihu's Chinese website).
3. Letting users choose the language of generated output names instead of hardcoding it.

Non-goals: changing the scraping pipeline behavior; touching the untracked `runs/` and
`zhihu_test/` scrape outputs (out of scope; suggest gitignoring separately).

## Key design decisions

### Three languages, handled separately
- **Authoring language → English.** All explanatory prose in `SKILL.md`, `references/*`, `README.md`.
- **Trigger cues → English with inline Chinese anchors (Option A).** Keep the literal Chinese
  terms users type, embedded in an English description.
- **Runtime/output language → mirror the user.** Decoupled from authoring via an explicit rule.

### Two kinds of literal Chinese strings (critical correctness rule)
- **Category 1 — names we choose** (Obsidian root folder `知乎收藏`, failure file
  `抓取失败.md`, classification subfolders): safe to make configurable.
- **Category 2 — strings tied to zhihu.com's actual Chinese site** (activity labels
  `赞同了回答` / `收藏了文章`, block-detection text `安全验证`, etc.): the scripts *match*
  these against what Zhihu returns. They MUST stay hardcoded Chinese — translating them
  silently breaks parsing. In docs they may be *glossed* in English, e.g. `安全验证 (security-check page)`.

## Scope of work

### 1. Description rewrite (the recall fix)
Replace the current `description:` paragraph in `SKILL.md` frontmatter.
- Lead with a concrete **"Use when…"** sentence covering trigger actions, each with an inline
  Chinese anchor: download/archive a collection (收藏夹); batch-fetch article bodies + local
  images (批量下载); resume an interrupted scrape (断点续传); recover from cookie expiry /
  安全验证; sync liked/saved history (点赞/收藏历史) into Obsidian.
- Keep a **short** "Not for:" clause (browsing, searching, writing Zhihu posts, general Zhihu
  questions) to preserve the 100% precision on the tricky negatives.
- **Remove** the "key signal is action intent… not just information about Zhihu" meta-essay —
  this is the main recall suppressor.
- Trim overall length; keep it scannable.
- This hand-written version is a **seed**; the optimization loop (step 6) refines it.

### 2. Runtime language rule
In `SKILL.md` "环境与约定" → English section. Replace `语言：默认与用户语种一致` with:
> *This skill is authored in English; respond and produce content in the user's language.*

### 3. SKILL.md body + references/* → English
Translate all prose in `SKILL.md` and the five `references/*.md` files. Unchanged: script
names, commands, env vars, CLI flags, file paths, and all Category-2 strings (glossed only).

### 4. README.md → English
Translate human-facing prose. Keep badges, project structure, screenshots, and the upstream
MIT attribution (handsomestWei). Same Category-1/2 rules apply.

### 5. Configurable output names (3 writer scripts)
Follow the skill's existing resolution precedence (**CLI flag > env var > default**, mirroring
the current Vault resolution).

| Knob | CLI flag | Env var | Default (NEW) | Previous |
|------|----------|---------|---------------|----------|
| Obsidian root folder | `--root-folder` | `ZHIHU_OBSIDIAN_ROOT` | `Zhihu Collection` | `知乎收藏` |
| Failure-list filename | `--failures-name` | `ZHIHU_FAILURES_FILE` | `fetch-failures.md` | `抓取失败.md` |

- Scripts touched: `write_to_obsidian.py`, `write_zhihu_history_to_obsidian.py`,
  `write_zhihu_failures.py`. No other scripts.
- **Defaults are now English** (`Zhihu Collection/`, `fetch-failures.md`). This is a
  **breaking change** for users with existing `知乎收藏/` vaults: their old notes will not be
  found/updated under the new default. Migration options, to be documented in
  `references/paths.md`: either rename the existing folder, or keep the old name by setting
  `ZHIHU_OBSIDIAN_ROOT=知乎收藏` (and `ZHIHU_FAILURES_FILE=抓取失败.md`).
- Document the knobs in `references/paths.md`.
- Note: this lifts the prior "scripts never modified, docs only" rule for these 3 files only,
  by deliberate user decision (configurability, not hardcoded rename).

### 6. Re-run the optimization loop
After seeding the new description:
```bash
cd /Users/kunwu/.claude/skills/skill-creator && python3 -m scripts.run_loop \
  --eval-set /Users/kunwu/Workspace/playground/MyNewsCollector/eval-workspace/eval_set.json \
  --skill-path /Users/kunwu/Workspace/playground/MyNewsCollector \
  --model "claude-sonnet-4-6" \
  --max-iterations 5 --verbose \
  > /Users/kunwu/Workspace/playground/MyNewsCollector/eval-workspace/run_loop.log 2>&1
```
- Back up the existing `run_loop.log` first.
- Apply `best_description` to `SKILL.md` **only if it beats the seed**; report before/after
  precision/recall.

### 7. Bilingual eval set
Expand `eval-workspace/eval_set.json` from 20 all-Chinese queries to ~40 by mirroring each
into an English equivalent, preserving balanced `should_trigger` true/false labels. This is
what validates that the description triggers in both languages.

### 8. Version bump
`SKILL.md` metadata `version: "1.3.0"` → `"1.4.0"`.

## Validation
- **Triggering:** the eval loop is the test. Target: recall well above the current ~0% while
  holding precision high, in both languages.
- **Configurability:** run a writer against the existing `zhihu_test/` output into a temp vault
  and confirm the default now produces `Zhihu Collection/`; then run with
  `ZHIHU_OBSIDIAN_ROOT=知乎收藏` and confirm the old name still works (backward-compat escape hatch).
- **Doc correctness:** grep that no Category-2 string, path, flag, or command was altered.

## Order of execution
1. Inventory Category-1 vs Category-2 strings across scripts (read-only).
2. Add configurability to the 3 writer scripts (+ validate).
3. Rewrite the description seed + runtime language rule + version bump in `SKILL.md`.
4. Translate `SKILL.md` body, then `references/*`, then `README.md`.
5. Expand `eval_set.json` to bilingual.
6. Run the optimization loop; apply best description if it wins; report.
