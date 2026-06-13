# Failure-Handling Strategy (`fetch_zhihu_batch.py`)

The batch-fetch script uses a **two-tier failure model** that distinguishes between article-level problems and environment-level problems:

| Scenario | Behavior | Rationale |
|----------|----------|-----------|
| Scattered failures (successes in between) | Recorded in the `failed` field of `_progress.json` | Treated as article-level problems (deleted / inaccessible); skipped on subsequent runs |
| 5 or more consecutive failures | Fetch is aborted; cached failure records are **discarded** | Treated as an environment problem (cookie / network); the next run can still retry all articles |

## How It Works

- Failures are buffered in memory first — they are not written to the progress file immediately.
- When the next article succeeds, buffered failures are flushed to the progress file in batch (confirming they are article-level problems).
- When the consecutive-failure threshold (5) is reached, the fetch is aborted and the buffer is discarded (preserving the ability to retry).

Each failure record contains `url` / `reason` / `title` / `timestamp` to aid manual investigation.

**Relevant constants (in the script):**

- `CONSECUTIVE_FAIL_THRESHOLD = 5`: consecutive-failure threshold
- `CONSECUTIVE_FAIL_INTERRUPT = True`: whether to abort on consecutive failure

## Retry Mode

```bash
python fetch_zhihu_batch.py <list-file> [output-dir] [image-dir] --retry-failed
```

This mode clears the `failed` list and retries only the articles previously recorded as failures.

## Failure-List Note in Obsidian

```bash
python "${CLAUDE_SKILL_DIR}/scripts/write_zhihu_failures.py" <vault-path> <tag>:<progress.json> ...
```

Generates `{Vault}/Zhihu Collection/fetch-failures.md` (default name; configurable via `--failures-name` or `ZHIHU_FAILURES_FILE`), making it easy to review and retry failures one by one.
