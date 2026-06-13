---
name: zhihu-fetcher
description: "Use when the user wants Zhihu (知乎) content pulled onto their machine. Triggers: download or archive a collection (收藏夹) of answers/articles; batch-fetch article bodies as Markdown with local images (批量下载/批量抓取); resume an interrupted scrape (续传/断点续传) or point at an existing zhihu_articles_*/ output dir; recover from cookie expiry, login, or an anti-scraping check (安全验证) during a scrape; export liked/saved history (点赞/收藏历史) or a 专栏 author's articles; fix mangled Markdown exported from Zhihu; or sync any of the above into an Obsidian vault. Works whether the user writes in Chinese or English. Not for: browsing or searching Zhihu, writing Zhihu posts, or general questions about Zhihu features/membership."
allowed-tools: Read, Write, Edit, Grep, Glob, Bash, WebFetch
metadata:
  version: "1.4.0"
---

# 知乎数据抓取

从知乎获取**收藏夹文章列表**或**个人点赞/收藏历史**，批量抓取**正文 Markdown**（含图片本地化），支持写入 **Obsidian** 知识库。可视化说明见仓库根目录 [`README.md`](README.md)。

## 触发条件

- 明确提及：知乎、Zhihu、专栏、收藏夹、文章抓取、批量下载、点赞/收藏历史、Cookie、验证码、Obsidian、知识库同步等
- 粘贴 **zhihu.com** / **zhuanlan.zhihu.com** 链接并希望获取正文或列表
- 需要**断点续传**、**图片落盘**、**反爬 / Stealth** 相关协助

## 环境与约定

- **Language**: This skill is authored in English; respond and produce content in the user's language.
- **技能根目录**：下文 `${CLAUDE_SKILL_DIR}` 表示本 skill 仓库根目录（部分宿主 UI 中写作 `{baseDir}`，含义相同）。脚本均在 `scripts/` 下。
- **工作区目录** `{workspace}`：由环境变量 **`OPENCLAW_WORKSPACE`** 指定，未设置时为 `~/.openclaw/workspace/`；存放 Cookie、浏览器数据与默认输出。详见 [references/paths.md](references/paths.md)。
- **依赖**：在 `scripts/` 下执行 `pip install -r requirements.txt`，并 `playwright install chromium`。

## 主流程：收藏夹 → 批量 → 格式化 → Obsidian

```bash
# 1. 收藏夹列表（优先 API，失败降级 Playwright DOM）
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_collection.py" <收藏夹URL或ID>

# 2. 批量抓取正文与图片 → zhihu_articles_{collectionId}/（含 _progress.json、images/、编号 *.md）
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_batch.py" <列表.json> [输出目录] [图片目录]

# 3. 保守格式化（首次建议先 --dry-run --diff 预览）
python "${CLAUDE_SKILL_DIR}/scripts/format_articles.py" <文章目录> [--dry-run --diff]

# 4. （可选）写入 Obsidian → {Vault}/知乎收藏/{分类}/
python "${CLAUDE_SKILL_DIR}/scripts/write_to_obsidian.py" <文章目录> [Vault路径]
```

**断点续传**：批量任务中断时，重新运行同一条 `fetch_zhihu_batch.py` 命令即可续跑（已完成 URL 记录在 `_progress.json`）。

## 个人历史流程（点赞 / 收藏）

适用于个人主页动态中的**赞同了回答 / 赞同了文章 / 收藏了回答 / 收藏了文章**。时间采用 ISO 格式；若无时区，脚本默认按 **Europe/Stockholm** 解释。

```bash
# 1. 收集活动列表（起始时间含，结束时间不含）；中断后重跑同一命令续跑，--fresh 忽略 checkpoint 重建
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_history.py" \
  https://www.zhihu.com/people/<slug> \
  2026-01-01T00:00:00+01:00 \
  <输出.json> \
  --until 2026-04-05T00:00:00+02:00

# 2. 批量抓取正文与图片（失败默认自动重试 3 次）
python "${CLAUDE_SKILL_DIR}/scripts/fetch_zhihu_batch.py" <输出.json> <文章目录>

# 3. 保守格式化（--set-times 用 interaction_time 设置文件时间）
python "${CLAUDE_SKILL_DIR}/scripts/format_articles.py" <文章目录> --set-times

# 4. 写入 Obsidian（按 URL 去重更新，保留互动时间与动作标签）
python "${CLAUDE_SKILL_DIR}/scripts/write_zhihu_history_to_obsidian.py" <文章目录> <Vault路径> .
```

历史笔记会在 frontmatter 保留 `interaction_action` / `interaction_time` / `interaction_date` 等互动元数据，格式见 [references/paths.md](references/paths.md)。

## 脚本路由

| 任务 | 脚本 | 备注 |
|------|------|------|
| 收藏夹 JSON 列表 | `fetch_zhihu_collection.py <收藏夹URL或ID>` | API ↔ DOM 自动切换，输出 `zhihu_collection_{id}.json` |
| 个人点赞/收藏历史列表 | `fetch_zhihu_history.py <people URL或slug> <起始ISO> <输出.json> [--until <结束ISO>] [--fresh]` | 保留 `interaction_*` 元数据，断点续跑 |
| 批量抓取正文与图片 | `fetch_zhihu_batch.py <列表.json> [输出目录] [图片目录] [--retry-failed]` | 推荐入口；保活、重试、续传内置 |
| 格式化已抓取 Markdown | `format_articles.py <目录或.md...> [--dry-run --diff --set-times]` | 保守修复，详见 [references/formatting.md](references/formatting.md) |
| 写入 Obsidian | `write_to_obsidian.py <文章目录> [Vault路径]` | Vault：命令行 > `OBSIDIAN_VAULT` > 自动扫描 |
| 写入个人历史到 Obsidian | `write_zhihu_history_to_obsidian.py <文章目录> <Vault路径> [.]` | 按 URL 去重更新 |
| 写入失败项清单 | `write_zhihu_failures.py <Vault路径> <标签>:<progress.json> ...` | 生成 `{Vault}/知乎收藏/抓取失败.md` |
| Cookie 失效重新登录 | `zhihu_relogin.py` | 打开浏览器窗口 |
| 首次登录辅助 | `zhihu_login.py [验证URL]` | 检测 `z_c0`；可选页面验证见 [references/cookie-keepalive.md](references/cookie-keepalive.md) |
| 单篇快速验证 / 调试 | `fetch_zhihu.py`（自动多策略）/ `fetch_zhihu_api.py`（API 直连）/ `fetch_zhihu_stealth.py`（隐身）/ `fetch_zhihu_interactive.py`（交互式，登录页验证码） | 单篇或调试时选用，避免不必要批量 |
| 读本地 Markdown、排查 `_progress.json` | — | 直接用 `Read` / `Grep` |

## 参考文档（按需阅读）

| 文件 | 何时阅读 |
|------|----------|
| [references/paths.md](references/paths.md) | 需要确认默认输出路径、文章 frontmatter 格式、Obsidian Vault 解析与分类规则时 |
| [references/cookie-keepalive.md](references/cookie-keepalive.md) | 登录 / Cookie 失效 / 保活机制相关问题 |
| [references/failure-handling.md](references/failure-handling.md) | 批量抓取出现失败项、需要理解两级失败策略或 `--retry-failed` 时 |
| [references/formatting.md](references/formatting.md) | 需要了解 `format_articles.py` 的具体修复规则与 `--set-times` 细节时 |
| [references/troubleshooting.md](references/troubleshooting.md) | 正文全空、验证页、反爬、图片失败等故障排查 |

## 工作流检查清单

```
□ scripts 依赖与 playwright chromium 可用；必要时提示用户设置 OPENCLAW_WORKSPACE
□ 收藏夹任务：先 fetch_zhihu_collection.py 得到合法 JSON，再 fetch_zhihu_batch.py
□ 批量后：format_articles.py 保守格式化（首次 --dry-run --diff），再写入 Obsidian
□ 遇验证页或全文为空：优先 Cookie/重登录，而非加大并发重试
□ 仅单篇或调试：选用单篇脚本，避免不必要批量
```
