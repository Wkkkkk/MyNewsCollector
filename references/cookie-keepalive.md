# Cookie Login, Keep-Alive, and Recovery

This document explains how to use the login scripts and describes the built-in cookie keep-alive mechanism in the batch-fetch script. Cookies are persisted by default at `{workspace}/zhihu_cookies.json` (see [paths.md](paths.md)).

## Login Scripts

### `zhihu_login.py` — Initial Login Helper

Opens a browser and waits for the user to log in. The default success condition is detecting the **`z_c0`** cookie — no additional redirect is required.

**Optional post-login verification:** If you want to confirm that a specific login-gated page is accessible after logging in (e.g., a collection page, a column admin page, or a followed-feed page), you can supply a URL. This step is optional and skipped when not configured:

- **`ZHIHU_VERIFY_URL`** environment variable: set to a full `http://` or `https://` URL; or
- Pass the URL as the first command-line argument:

  ```bash
  python "${CLAUDE_SKILL_DIR}/scripts/zhihu_login.py" "https://www.zhihu.com/..."
  ```

The script visits that URL and checks whether the response body contains the generic login-prompt text. If it does, the script warns that login may not be complete; otherwise the session is considered valid for that page. Any Zhihu URL that requires login can be used here.

### `zhihu_relogin.py` — Re-login

Use this when the cookie has expired and needs to be refreshed. Opens a browser window and writes the new cookie back to `zhihu_cookies.json`.

### `zhihu_login_save.py` — Login and Save

Use as part of the cookie workflow when needed.

## Cookie Keep-Alive Mechanism (built into `fetch_zhihu_batch.py`)

The batch-fetch script has a multi-layer keep-alive strategy that requires no manual intervention:

1. **Proactive TTL check** (every article): parses the `expires` field of the `z_c0` cookie; triggers aggressive refresh when fewer than 30 minutes remain
2. **Routine keep-alive** (every 5–8 articles): visits a Zhihu listing page and simulates scrolling
3. **Aggressive keep-alive** (every ~20 articles): visits an actual article page and simulates reading (2–5-second pause + scrolling)
4. **Passive detection**: checks on every article visit whether the browser was redirected to `/account/unhuman` or `/signin`
5. **Automatic recovery**: on detecting an expired session, attempts up to 3 aggressive keep-alive cycles
6. **Cookie backup**: after each keep-alive cycle, extracts the latest cookies from the browser and saves them to file (extended format includes `expires`)
7. **Clean exit**: saves the latest cookies and current progress before the script terminates

## Session Expiry: Detection and Response

- Typical expiry symptoms: page title shows 安全验证 (security-check page), redirect to `/account/unhuman`, empty article body.
- Response sequence: the script first retries automatically up to 3 times (aggressive keep-alive); if that still fails, run `zhihu_relogin.py` to log in manually.
- Do not blindly increase concurrency or retries when the session is expired — restore the login state first.
