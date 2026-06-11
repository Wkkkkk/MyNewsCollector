# 已知问题与故障排查

## 已知问题与对策

| # | 现象 / 原因 | 处理 |
|---|-------------|------|
| 1 | **Cookie 失效**：标题「安全验证」、`/account/unhuman` | **自动恢复**：脚本内置 3 次重试（激进保活：访问文章页+模拟阅读）；仍失败则 `zhihu_relogin.py`。详见 [cookie-keepalive.md](cookie-keepalive.md) |
| 2 | **收藏夹 API 分页**：带 `include` 时列表可能被截断 | `fetch_zhihu_collection.py` 已内置 API ↔ DOM 切换；必要时减少 `include` 或走浏览器分页 |
| 3 | **反爬**：Headless 被识别 | Stealth、UA、间隔；必要时 `fetch_zhihu_interactive.py` |
| 4 | **API 正文不完整**：`include` 只给摘要 | 批量与单篇流程中已优先**页面 DOM** 拉全文 |
| 5 | **图片下载失败** | 正文仍保留原 URL；排查网络、Referer、过期链接 |
| 6 | **Windows 控制台 GBK** | 脚本已 `sys.stdout.reconfigure(encoding='utf-8')` |
| 7 | **批量中断** | 直接再次运行 `fetch_zhihu_batch.py`，依赖 `_progress.json` |
| 8 | **失败项累积** | 散发失败自动记录到 `_progress.json`（含 url/reason/title/timestamp）；连续失败 ≥5 次中断并丢弃缓存；用 `--retry-failed` 可重试。详见 [failure-handling.md](failure-handling.md) |

## 故障排查流程

```
正文全空？
  → Cookie（含 z_c0）→ 是否跳转验证页 → zhihu_relogin.py

图片失败？
  → URL/网络/Referer → Markdown 中仍可保留链接

批量中途停止？
  → 确认 _progress.json → 原命令重跑
```

排查 `_progress.json` 或本地已抓取 Markdown 时，直接用 `Read` / `Grep` 工具，无需脚本。
