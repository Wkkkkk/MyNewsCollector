# Conservative Formatting (`format_articles.py`)

Applies **conservative** cleanup to already-fetched Markdown — fixes export artifacts only, does not reflow body text. Accepts a directory (processes `*.md` recursively) or individual files:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/format_articles.py" <article-dir-or-.md-file...> \
  [--dry-run] [--diff] [--set-times] [--time-field interaction_time] [--no-created-time]
```

## What Gets Fixed

- **Multi-line inline code → fenced code blocks:** multi-line code that was collapsed into a single backtick span during export is restored to ``` fences, with the language inferred from content (cpp / go / python / rust / sql / json / bash / javascript / yaml)
- **Link-card restoration:** Zhihu card-style links (image + title wrapped in a single anchor) are split into separate image and title-link elements
- **Collapsed link-list restoration:** lists of 4+ links that were collapsed into a single paragraph are restored as an unordered list under `## Links` (or `## RSS Sources`)
- **Redirect decoding:** `link.zhihu.com/?target=...` URLs are resolved to their real destinations; `zhida.zhihu.com` entity links are not treated as source links
- **References section:** bold headings such as `**References**` are converted to `## ` headings; redirect links inside the section are decoded
- **Blank-line normalization:** blank lines are added before and after headings, lists, blockquotes, images, and code fences; consecutive blank lines are collapsed; code-fence contents are left untouched

## File-Time Sync (optional)

`--set-times` sets the file's access and modification times from a frontmatter field (defaults to `interaction_time`; use `--time-field` to choose a different field). On macOS, if `SetFile` is available, the creation time is also synced (`--no-created-time` skips this). Useful for making file timestamps in Obsidian/Finder reflect the actual interaction time.

## Safety

- **Idempotent:** running multiple times produces the same result
- Frontmatter content is never modified; content inside code fences is never processed
- Recommended first run: `--dry-run --diff` to preview changes
- Prints a `scanned=… changed=…` summary on exit
