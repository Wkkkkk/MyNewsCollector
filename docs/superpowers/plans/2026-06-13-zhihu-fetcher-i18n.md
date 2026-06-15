# zhihu-fetcher English Conversion + Trigger Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the `zhihu-fetcher` skill to English-authored docs, fix its ~0% trigger recall, and make the Obsidian output names configurable (defaulting to English).

**Architecture:** Add one shared config-resolver module that three writer scripts use to pick the Obsidian root-folder and failure-file names (CLI flag > env var > English default). Rewrite the `description:` to lift recall while keeping inline Chinese trigger anchors, then validate with the skill-creator optimization loop against the (already-bilingual) eval set. Translate all explanatory prose to English while preserving every literal string the scripts emit or match against zhihu.com.

**Tech Stack:** Python 3.10+ (stdlib `unittest` for tests, `argparse`), the `skill-creator` `run_loop` harness, AgentSkills SKILL.md conventions.

**Spec:** `docs/superpowers/specs/2026-06-13-zhihu-fetcher-i18n-design.md`

---

## Critical rules for every task

- **Never edit Category-2 strings** — strings the scripts match against zhihu.com's Chinese site:
  `安全验证`, activity labels (`赞同了回答`, `赞同了文章`, `收藏了回答`, `收藏了文章`), and any other
  text compared to fetched page/API content. Translating these silently breaks scraping. In prose
  they may only be **glossed**, e.g. `安全验证 (security-check page)`.
- **Never change** script names, command lines, env-var names, CLI flags, file paths, or frontmatter
  **keys** (`interaction_action`, `interaction_time`, etc.).
- **Category-1 strings** (the Obsidian root folder `知乎收藏`, failure file `抓取失败.md`) are only
  changed via the config resolver in Tasks 1–4 — never hardcode a new literal elsewhere.

---

## Task 1: Shared Obsidian-name config resolver (TDD)

**Files:**
- Create: `scripts/zhihu_obsidian_config.py`
- Test: `scripts/tests/test_zhihu_obsidian_config.py`

- [ ] **Step 1: Write the failing test**

```python
# scripts/tests/test_zhihu_obsidian_config.py
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import zhihu_obsidian_config as cfg


class ResolveRootFolder(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("ZHIHU_OBSIDIAN_ROOT", "ZHIHU_FAILURES_FILE")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_root_is_english(self):
        self.assertEqual(cfg.resolve_root_folder(), "Zhihu Collection")

    def test_default_failures_is_english(self):
        self.assertEqual(cfg.resolve_failures_name(), "fetch-failures.md")

    def test_env_overrides_default(self):
        os.environ["ZHIHU_OBSIDIAN_ROOT"] = "知乎收藏"
        self.assertEqual(cfg.resolve_root_folder(), "知乎收藏")

    def test_cli_overrides_env(self):
        os.environ["ZHIHU_OBSIDIAN_ROOT"] = "知乎收藏"
        self.assertEqual(cfg.resolve_root_folder("Custom"), "Custom")

    def test_blank_env_falls_back_to_default(self):
        os.environ["ZHIHU_OBSIDIAN_ROOT"] = "   "
        self.assertEqual(cfg.resolve_root_folder(), "Zhihu Collection")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd scripts && python -m unittest tests.test_zhihu_obsidian_config -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'zhihu_obsidian_config'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/zhihu_obsidian_config.py
"""Resolve configurable Obsidian output names (CLI flag > env var > English default).

Defaults are English as of skill v1.4.0. Users with an existing Chinese vault can keep the
old names with: ZHIHU_OBSIDIAN_ROOT=知乎收藏 ZHIHU_FAILURES_FILE=抓取失败.md
"""

import os

DEFAULT_ROOT_FOLDER = "Zhihu Collection"
DEFAULT_FAILURES_NAME = "fetch-failures.md"

ENV_ROOT_FOLDER = "ZHIHU_OBSIDIAN_ROOT"
ENV_FAILURES_NAME = "ZHIHU_FAILURES_FILE"


def resolve_root_folder(cli_value=None):
    if cli_value and cli_value.strip():
        return cli_value
    env = os.environ.get(ENV_ROOT_FOLDER, "").strip()
    return env or DEFAULT_ROOT_FOLDER


def resolve_failures_name(cli_value=None):
    if cli_value and cli_value.strip():
        return cli_value
    env = os.environ.get(ENV_FAILURES_NAME, "").strip()
    return env or DEFAULT_FAILURES_NAME
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd scripts && python -m unittest tests.test_zhihu_obsidian_config -v`
Expected: PASS (5 tests OK)

- [ ] **Step 5: Commit**

```bash
git add scripts/zhihu_obsidian_config.py scripts/tests/test_zhihu_obsidian_config.py
git commit -m "feat: add configurable Obsidian output-name resolver"
```

---

## Task 2: Wire resolver into write_zhihu_failures.py

**Files:**
- Modify: `scripts/write_zhihu_failures.py` (imports, `main()` lines 40–89)

- [ ] **Step 1: Add the import**

After line 12 (`from pathlib import Path`), add:

```python
from zhihu_obsidian_config import resolve_root_folder, resolve_failures_name
```

- [ ] **Step 2: Replace `main()` arg handling with argparse (supports flags + existing positionals)**

Replace the body from line 41 (`if len(sys.argv) < 3:`) through line 47
(`zhihu_dir.mkdir(parents=True, exist_ok=True)`) with:

```python
    import argparse

    parser = argparse.ArgumentParser(
        description="Write a consolidated Obsidian note for failed Zhihu fetch items."
    )
    parser.add_argument("vault", help="Obsidian vault root path")
    parser.add_argument("specs", nargs="+", help="<label>:<progress-json> pairs")
    parser.add_argument("--root-folder", default=None,
                        help="Obsidian root folder name (default: env ZHIHU_OBSIDIAN_ROOT or 'Zhihu Collection')")
    parser.add_argument("--failures-name", default=None,
                        help="Failure-list filename (default: env ZHIHU_FAILURES_FILE or 'fetch-failures.md')")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    zhihu_dir = vault / resolve_root_folder(args.root_folder)
    zhihu_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: Update the spec-iteration loop to use parsed args**

Replace line 51 (`for spec in sys.argv[2:]:`) with:

```python
    for spec in args.specs:
```

- [ ] **Step 4: Replace the hardcoded output filename**

Replace line 86 (`note = zhihu_dir / "抓取失败.md"`) with:

```python
    note = zhihu_dir / resolve_failures_name(args.failures_name)
```

Leave the note's frontmatter title/tags (`知乎抓取失败项`, `抓取失败`) as-is — they are display
content inside the note, not a path or a Zhihu-matched string, and the user did not ask to alter
note bodies. (If desired later, these are cosmetic.)

- [ ] **Step 5: Verify it runs against existing test output**

Run:
```bash
cd /path/to/MyNewsCollector
mkdir -p /tmp/zh-vault-test
python scripts/write_zhihu_failures.py /tmp/zh-vault-test run:zhihu_test/articles/_progress.json
ls "/tmp/zh-vault-test/Zhihu Collection/"
```
Expected: a `fetch-failures.md` exists under `/tmp/zh-vault-test/Zhihu Collection/`.

Then verify the backward-compat override:
```bash
ZHIHU_OBSIDIAN_ROOT=知乎收藏 ZHIHU_FAILURES_FILE=抓取失败.md \
  python scripts/write_zhihu_failures.py /tmp/zh-vault-test run:zhihu_test/articles/_progress.json
ls /tmp/zh-vault-test/知乎收藏/
```
Expected: `抓取失败.md` exists under `/tmp/zh-vault-test/知乎收藏/`.

- [ ] **Step 6: Commit**

```bash
git add scripts/write_zhihu_failures.py
git commit -m "feat: configurable root folder + failure filename in write_zhihu_failures"
```

---

## Task 3: Wire resolver into write_zhihu_history_to_obsidian.py

**Files:**
- Modify: `scripts/write_zhihu_history_to_obsidian.py` (imports; `main()` lines 197–213)

- [ ] **Step 1: Add the import**

Near the top imports add:

```python
from zhihu_obsidian_config import resolve_root_folder
```

- [ ] **Step 2: Add a `--root-folder` flag while keeping the positional call shape**

Replace lines 198–204 (the `if len(sys.argv) < 3:` block through the `folder_name = ...` line) with:

```python
    import argparse

    parser = argparse.ArgumentParser(
        description="Import Zhihu like/save history articles into an Obsidian vault."
    )
    parser.add_argument("article_dir")
    parser.add_argument("vault_path")
    parser.add_argument("folder_name", nargs="?", default=".",
                        help="Subfolder under the root; '.' means the root itself")
    parser.add_argument("--root-folder", default=None,
                        help="Obsidian root folder name (default: env ZHIHU_OBSIDIAN_ROOT or 'Zhihu Collection')")
    args = parser.parse_args()

    source_dir = Path(args.article_dir).expanduser().resolve()
    vault_path = Path(args.vault_path).expanduser().resolve()
    folder_name = args.folder_name
```

- [ ] **Step 3: Use the resolved root folder**

Replace line 213 (`zhihu_dir = vault_path / "知乎收藏"`) with:

```python
    zhihu_dir = vault_path / resolve_root_folder(args.root_folder)
```

- [ ] **Step 4: Keep the root sentinel backward-compatible**

In `resolve_history_root` (line 192), the sentinel list `("", ".", "root", "知乎收藏")` means
"write into the root, not a subfolder." Add the English default so passing the new root name as a
folder-name also resolves to root. Change line 192 to:

```python
    if folder_name in ("", ".", "root", "知乎收藏", "Zhihu Collection"):
```

- [ ] **Step 5: Smoke-test argument parsing**

Run: `python scripts/write_zhihu_history_to_obsidian.py --help`
Expected: usage text showing `article_dir`, `vault_path`, optional `folder_name`, and `--root-folder`.

- [ ] **Step 6: Commit**

```bash
git add scripts/write_zhihu_history_to_obsidian.py
git commit -m "feat: configurable root folder in write_zhihu_history_to_obsidian"
```

---

## Task 4: Wire resolver into write_to_obsidian.py

**Files:**
- Modify: `scripts/write_to_obsidian.py` — `detect_existing_categories` (111–139), `sync_images`
  (240–272), `write_to_obsidian` (275–358), `main()` (361–436)

- [ ] **Step 1: Add the import**

With the other top imports add:

```python
from zhihu_obsidian_config import resolve_root_folder
```

- [ ] **Step 2: Thread `root_folder` into `detect_existing_categories`**

Change the signature (line 111) and the hardcoded join (line 117):

```python
def detect_existing_categories(vault_path, root_folder):
```
```python
    zhihu_dir = os.path.join(vault_path, root_folder)
```

- [ ] **Step 3: Thread `root_folder` into `sync_images`**

Change the signature (line ~239) and the hardcoded join (line 252):

```python
def sync_images(source_dir, vault_path, root_folder):
```
```python
    obsidian_images_dir = os.path.join(vault_path, root_folder, 'images')
```

- [ ] **Step 4: Thread `root_folder` into `write_to_obsidian`**

Change the signature (line 275), the hardcoded join (line 277), and the internal call (line 281):

```python
def write_to_obsidian(article_files, vault_path, source_dir, root_folder):
```
```python
    zhihu_dir = os.path.join(vault_path, root_folder)
```
```python
    existing = detect_existing_categories(vault_path, root_folder)
```

- [ ] **Step 5: Resolve the flag in `main()` and pass it to the calls**

In `main()`, immediately after `source_dir = sys.argv[1]` is determined, the script still parses
argv manually. Add flag handling at the very top of `main()` (right after the docstring/first line
of the function) by pulling `--root-folder` out of argv before the existing positional logic:

```python
    root_folder_cli = None
    if "--root-folder" in sys.argv:
        i = sys.argv.index("--root-folder")
        root_folder_cli = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    root_folder = resolve_root_folder(root_folder_cli)
```

Then update the two call sites:
- Line 422: `stats = write_to_obsidian(article_files, vault_path, source_dir, root_folder)`
- Line 426: `sync_images(source_dir, vault_path, root_folder)`

- [ ] **Step 6: Verify end-to-end against existing test output**

Run:
```bash
cd /path/to/MyNewsCollector
rm -rf /tmp/zh-vault-w2o && mkdir -p /tmp/zh-vault-w2o/.obsidian
cp -r zhihu_test/articles /tmp/zh-src && \
python scripts/write_to_obsidian.py /tmp/zh-src /tmp/zh-vault-w2o
ls "/tmp/zh-vault-w2o/Zhihu Collection/"
```
Expected: category subfolders created under `Zhihu Collection/` (English default). No traceback.

- [ ] **Step 7: Commit**

```bash
git add scripts/write_to_obsidian.py
git commit -m "feat: configurable root folder in write_to_obsidian"
```

---

## Task 5: Rewrite the description + runtime language rule + version bump

**Files:**
- Modify: `SKILL.md` frontmatter (lines 2–7) and the 环境与约定 language line (line 21)

- [ ] **Step 1: Replace the `description:` value (recall fix, Option A — English + Chinese anchors)**

Replace the entire `description:` line with this exact value (one line in the YAML):

```yaml
description: "Use when the user wants Zhihu (知乎) content pulled onto their machine. Triggers: download or archive a collection (收藏夹) of answers/articles; batch-fetch article bodies as Markdown with local images (批量下载/批量抓取); resume an interrupted scrape (续传/断点续传) or point at an existing zhihu_articles_*/ output dir; recover from cookie expiry, login, or an anti-scraping check (安全验证) during a scrape; export liked/saved history (点赞/收藏历史) or a 专栏 author's articles; fix mangled Markdown exported from Zhihu; or sync any of the above into an Obsidian vault. Works whether the user writes in Chinese or English. Not for: browsing or searching Zhihu, writing Zhihu posts, or general questions about Zhihu features/membership."
```

- [ ] **Step 2: Bump the version**

Change line 6 from `version: "1.3.0"` to:

```yaml
  version: "1.4.0"
```

- [ ] **Step 3: Replace the language convention line with an English runtime rule**

Change line 21 (`- **语言**：默认与用户语种一致。`) to:

```markdown
- **Language**: This skill is authored in English; respond and produce content in the user's language.
```

- [ ] **Step 4: Verify frontmatter still parses**

Run: `python -c "import yaml,io; t=open('SKILL.md').read().split('---')[1]; print(yaml.safe_load(t)['name'], yaml.safe_load(t)['metadata']['version'])"`
Expected: `zhihu-fetcher 1.4.0` (if PyYAML missing, instead `grep -n 'version:' SKILL.md` shows 1.4.0).

- [ ] **Step 5: Commit**

```bash
git add SKILL.md
git commit -m "feat: rewrite description for recall, add English runtime rule, bump to 1.4.0"
```

---

## Task 6: Translate SKILL.md body to English

**Files:**
- Modify: `SKILL.md` (everything below the frontmatter, i.e. line 9 onward)

- [ ] **Step 1: Translate all prose, preserving the protected tokens**

Translate every Chinese heading, sentence, and table cell into English **except**:
- Command lines, script names, paths, env vars, flags — unchanged.
- The Obsidian output path examples: write them as `{Vault}/{root}/{category}/` and note the
  default root is now `Zhihu Collection` (formerly `知乎收藏`).
- Category-2 strings stay Chinese with an English gloss: `安全验证 (security-check page)`,
  activity labels `赞同了回答 / 赞同了文章 / 收藏了回答 / 收藏了文章 (liked/saved answer/article)`.
- Frontmatter keys (`interaction_action`, etc.) unchanged.

Section-by-section: `# 知乎数据抓取` → `# Zhihu Content Fetcher`; `## 触发条件` → `## When this triggers`;
`## 环境与约定` → `## Environment & conventions`; `## 主流程…` → `## Main flow: collection → batch → format → Obsidian`;
`## 个人历史流程…` → `## Personal history flow (likes / saves)`; `## 脚本路由` → `## Script routing`;
`## 参考文档…` → `## Reference docs (read as needed)`; `## 工作流检查清单` → `## Workflow checklist`.
Translate the two tables' cells and the checklist lines likewise.

- [ ] **Step 2: Add the new config flags to the script-routing notes**

In the Obsidian rows of the script-routing table, document the new options:
`write_to_obsidian.py … [--root-folder NAME]`, `write_zhihu_failures.py … [--root-folder NAME] [--failures-name NAME]`,
and note env vars `ZHIHU_OBSIDIAN_ROOT` / `ZHIHU_FAILURES_FILE` with the English defaults and the
`知乎收藏`/`抓取失败.md` backward-compat override.

- [ ] **Step 3: Verify no protected token was altered**

Run:
```bash
grep -nE "fetch_zhihu|format_articles|write_to_obsidian|OPENCLAW_WORKSPACE|安全验证|赞同了|收藏了" SKILL.md
```
Expected: all script names, `OPENCLAW_WORKSPACE`, and the glossed Category-2 strings still present.

- [ ] **Step 4: Commit**

```bash
git add SKILL.md
git commit -m "docs: translate SKILL.md body to English; document config flags"
```

---

## Task 7: Translate references/*.md to English

**Files:**
- Modify: `references/paths.md`, `references/cookie-keepalive.md`, `references/failure-handling.md`,
  `references/formatting.md`, `references/troubleshooting.md`

- [ ] **Step 1: Translate each file under the same protected-token rules as Task 6**

For each of the five files, translate prose to English; keep commands/paths/flags/Category-2 strings.

- [ ] **Step 2: Update `references/paths.md` for the configurable + English-default names**

Document, in `references/paths.md`:
- Default Obsidian root folder is now `Zhihu Collection` (was `知乎收藏`); failure file is
  `fetch-failures.md` (was `抓取失败.md`).
- The resolution order: `--root-folder` / `--failures-name` flags > `ZHIHU_OBSIDIAN_ROOT` /
  `ZHIHU_FAILURES_FILE` env > English default.
- **Migration note** for existing Chinese vaults: rename the folder, or set
  `ZHIHU_OBSIDIAN_ROOT=知乎收藏` and `ZHIHU_FAILURES_FILE=抓取失败.md` to keep the old layout.

- [ ] **Step 3: Verify Category-2 strings survived in failure/troubleshooting docs**

Run: `grep -nE "安全验证|赞同了|收藏了" references/*.md`
Expected: still present (glossed in English) where these were originally referenced.

- [ ] **Step 4: Commit**

```bash
git add references/
git commit -m "docs: translate references/* to English; document configurable output names"
```

---

## Task 8: Translate README.md to English

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Translate prose, keep structure and attribution**

Translate headings, the feature table, install/usage prose, and "运行效果"/"项目结构"/"参考文档"
sections to English. Keep unchanged: badges, image links (`docs/openclaw-run.jpg`, `docs/obs.jpg`),
all command blocks/paths, the project-structure tree, the MIT license line and `handsomestWei`
attribution. Update the example Obsidian paths to reflect the `Zhihu Collection` default and mention
the env-var override.

- [ ] **Step 2: Verify images and attribution intact**

Run: `grep -nE "openclaw-run.jpg|obs.jpg|handsomestWei|MIT" README.md`
Expected: all four still present.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: translate README.md to English"
```

---

## Task 9: Confirm the eval set is balanced & bilingual

**Files:**
- Modify (only if needed): `eval-workspace/eval_set.json`

- [ ] **Step 1: Inspect current balance**

The set already contains **20 queries, 10 should-trigger / 10 should-not, mixed Chinese and
English** (e.g. items 2, 7, 13, 17, 19 are English). Confirm with:

```bash
python -c "import json;d=json.load(open('eval-workspace/eval_set.json'));import collections;print(len(d), collections.Counter(x['should_trigger'] for x in d))"
```
Expected: `20 Counter({True: 10, False: 10})`.

- [ ] **Step 2: Add 4 balanced bilingual edge cases (2 trigger, 2 not)**

Append these four objects to the JSON array (keep valid JSON — comma after the previous last item):

```json
  {
    "query": "resume the interrupted zhihu scrape in ~/.openclaw/workspace/zhihu_articles_36662593, it stopped after a security check",
    "should_trigger": true
  },
  {
    "query": "把我关注的某个知乎专栏作者的全部文章批量存成 markdown 并同步到 obsidian",
    "should_trigger": true
  },
  {
    "query": "summarize the top answers on this zhihu question for me, don't download anything",
    "should_trigger": false
  },
  {
    "query": "知乎和微博哪个平台的内容质量更高？说说你的看法",
    "should_trigger": false
  }
```

- [ ] **Step 3: Verify the JSON is valid and now 24/balanced**

Run: `python -c "import json,collections;d=json.load(open('eval-workspace/eval_set.json'));print(len(d), collections.Counter(x['should_trigger'] for x in d))"`
Expected: `24 Counter({True: 12, False: 12})`

- [ ] **Step 4: Commit**

```bash
git add eval-workspace/eval_set.json
git commit -m "test: add bilingual edge-case queries to trigger eval set"
```

---

## Task 10: Run the optimization loop and apply the best description

**Files:**
- Possibly modify: `SKILL.md` (`description:`), `eval-workspace/run_loop.log`

- [ ] **Step 1: Back up the prior run log**

```bash
cd /path/to/MyNewsCollector
cp eval-workspace/run_loop.log eval-workspace/run_loop.prev.log 2>/dev/null || true
```

- [ ] **Step 2: Run the loop in the background (seed = the new description from Task 5)**

```bash
cd ~/.claude/skills/skill-creator && python3 -m scripts.run_loop \
  --eval-set /path/to/MyNewsCollector/eval-workspace/eval_set.json \
  --skill-path /path/to/MyNewsCollector \
  --model "claude-sonnet-4-6" \
  --max-iterations 5 --verbose \
  > /path/to/MyNewsCollector/eval-workspace/run_loop.log 2>&1
```

- [ ] **Step 3: Read the result**

Inspect the tail of `eval-workspace/run_loop.log` for `Best score`, `best_train_score`,
`best_test_score`, and `best_description`. Compare recall against the prior run (~0%).

- [ ] **Step 4: Apply `best_description` only if it beats the Task-5 seed**

If the loop's `best_description` scores higher than the seed, copy it into `SKILL.md`'s
`description:`. If the seed already wins (loop found no improvement), leave the seed in place.

- [ ] **Step 5: Report before/after to the user**

Present: seed score vs best score, precision/recall in both languages, and whether the
description changed. Do NOT claim success without quoting the actual log numbers.

- [ ] **Step 6: Commit (only if the description changed)**

```bash
git add SKILL.md eval-workspace/run_loop.log
git commit -m "feat: apply optimized description from run_loop (sonnet-4-6)"
```

---

## Task 11: Update project memory

**Files:**
- Modify: `~/.claude/projects/-Users-kunwu-Workspace-playground-zhihu/memory/MEMORY.md`
- Modify: `~/.claude/projects/-Users-kunwu-Workspace-playground-zhihu/memory/zhihu-fetcher-description-optimization.md`

- [ ] **Step 1: Mark the optimization task resolved**

Update the memory file to record: the loop was re-run on the bilingual eval set with
claude-sonnet-4-6, the final description scores, and whether a new description was applied. Note
that defaults are now English with env-var backward-compat. Update the `MEMORY.md` index hook line.
(Memory edits are not git-committed.)

---

## Self-review notes (verified during planning)

- **Spec coverage:** description rewrite (T5/T10), runtime rule (T5), SKILL.md+references+README
  English (T6–T8), configurable names across the 3 writer scripts (T1–T4), bilingual eval (T9),
  loop run + apply (T10), version bump (T5). All spec sections mapped.
- **Eval-set correction vs spec:** the set is already bilingual & balanced (not "20 all-Chinese");
  T9 reflects reality — confirm + add 4, rather than mirror all 20.
- **Type/name consistency:** resolver API `resolve_root_folder(cli_value=None)` /
  `resolve_failures_name(cli_value=None)` and env names `ZHIHU_OBSIDIAN_ROOT` /
  `ZHIHU_FAILURES_FILE` are used identically across T1–T4 and documented identically in T6–T8.
- **Protected strings:** every translation task carries the same Category-2 / path / flag rule and a
  grep verification step.
```
