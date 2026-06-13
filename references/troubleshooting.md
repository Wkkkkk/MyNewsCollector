# Known Issues and Troubleshooting

## Known Issues and Mitigations

| # | Symptom / Cause | Resolution |
|---|-----------------|------------|
| 1 | **Cookie expiry:** page title shows 安全验证 (security-check page), redirect to `/account/unhuman` | **Auto-recovery:** script retries up to 3 times (aggressive keep-alive: visits article page + simulates reading); if still failing, run `zhihu_relogin.py`. See [cookie-keepalive.md](cookie-keepalive.md) |
| 2 | **Collection API pagination:** list may be truncated when `include` parameter is set | `fetch_zhihu_collection.py` has built-in API ↔ DOM switching; if needed, reduce `include` fields or use browser-based pagination |
| 3 | **Anti-scraping:** headless browser detected | Stealth mode, UA rotation, request intervals; if still blocked, use `fetch_zhihu_interactive.py` |
| 4 | **Incomplete API body:** `include` returns only a summary | Both batch and single-article flows already prefer **page DOM** for full content |
| 5 | **Image download failures** | Body text still retains the original URL; check network, Referer header, and link expiry |
| 6 | **Windows console GBK encoding** | Scripts already call `sys.stdout.reconfigure(encoding='utf-8')` |
| 7 | **Batch fetch interrupted** | Simply re-run `fetch_zhihu_batch.py`; it resumes from `_progress.json` |
| 8 | **Accumulated failures** | Scattered failures are recorded automatically in `_progress.json` (with `url` / `reason` / `title` / `timestamp`); 5+ consecutive failures abort the run and discard the buffer; use `--retry-failed` to retry. See [failure-handling.md](failure-handling.md) |

## Troubleshooting Flowchart

```
Empty article body?
  → Check cookie (including z_c0) → redirected to verification page? → zhihu_relogin.py

Image failures?
  → Check URL / network / Referer → link can still be kept in the Markdown

Batch stopped mid-run?
  → Inspect _progress.json → re-run the original command
```

When inspecting `_progress.json` or locally fetched Markdown files, use the `Read` / `Grep` tools directly — no script needed.
