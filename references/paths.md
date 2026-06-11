# 路径、输出格式与 Obsidian 写入约定

## 工作区目录

脚本默认将 Cookie、浏览器用户数据、默认文章输出等放在 **`OPENCLAW_WORKSPACE`** 环境变量指定的目录；未设置时为 **`~/.openclaw/workspace/`**。下文以 `{workspace}` 指代。

### 持久化文件

| 用途 | 路径 |
|------|------|
| Cookie | `{workspace}/zhihu_cookies.json` |
| Playwright 用户数据 | `{workspace}/chrome_user_data/` |
| 默认文章目录 | `{workspace}/zhihu_articles_{collectionId}/` |
| 默认图片目录 | `{文章输出目录}/images/` |

## 批量抓取命令格式

```bash
python fetch_zhihu_batch.py <列表文件> [输出目录] [图片目录]
```

| 参数 | 说明 |
|------|------|
| **列表文件** | `fetch_zhihu_collection.py` / `fetch_zhihu_history.py` 产出的 JSON |
| **输出目录** | 可选；省略时默认为 `{workspace}/zhihu_articles_{collectionId}/`（`collectionId` 由列表文件名推导） |
| **图片目录** | 可选；省略时默认为 `{输出目录}/images/`；仅在自定义图片目录时才需要传第三个参数 |

## 目录结构示例

```
zhihu_articles_{collectionId}/
├── _progress.json          # 断点续传
├── images/                 # 默认图片目录
│   └── ...
├── 0001_文章标题.md
└── ...
```

## 单篇文章格式要点

- YAML frontmatter：`title`、`author`、`source`、`url`、`voteup`、`images` 等
- 正文为 Markdown；图片引用指向本地 `images/` 下文件名（或脚本生成的相对路径）

```markdown
---
title: "文章标题"
author: "作者"
source: zhihu
url: "https://..."
voteup: 123
images: 5
---

# 文章标题

> 作者: xxx | 原文: [知乎链接](https://...)

正文...
```

个人历史流程抓取的笔记会额外保留互动元数据：

```yaml
interaction_action: "赞同了回答"
interaction_time: 2026-03-20T10:17:57.235000+00:00
interaction_date: 2026-03-20
tags: [zhihu, 编程与开发, 赞同了回答]
```

## Obsidian 写入要点

### Vault 路径解析顺序

1. **命令行参数**（优先让用户直接写出 Vault 根路径）
2. 未传时使用环境变量 **`OBSIDIAN_VAULT`**（单个路径）
3. 仍无时脚本按常见目录扫描，多个命中时再交互选择

### 分类与落盘（`write_to_obsidian.py`）

- **分类**：优先对齐已有 `知乎收藏/` 子目录；否则按内容关键词；无法归类则「未分类」
- **落盘**：`{Vault}/知乎收藏/{分类}/{文章标题}.md`；图片同步规则见脚本（目标侧常有集中 `images` 目录）
- 来源侧会先找 `<文章目录>/images`，否则兼容同级 `zhihu_images`

### 个人历史写入（`write_zhihu_history_to_obsidian.py`）

- 默认写入 `{Vault}/知乎收藏/{分类}/`
- 写入前扫描已有笔记的 `url` 并**按 URL 去重更新**，避免重复导入
- 保留互动时间、动作标签
