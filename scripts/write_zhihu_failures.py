#!/usr/bin/env python3
"""
Write a consolidated Obsidian note for failed Zhihu fetch items.

Usage:
  python write_zhihu_failures.py <vault-path> <label>:<progress-json> [...]
"""

import datetime
import json
import sys
from pathlib import Path

from zhihu_obsidian_config import resolve_root_folder, resolve_failures_name

sys.stdout.reconfigure(encoding="utf-8")


def load_failed(label, path):
    path = Path(path).expanduser()
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in data.get("failed", []):
        rows.append(
            {
                "range": label,
                "index": item.get("index", ""),
                "title": item.get("title", ""),
                "reason": item.get("reason", ""),
                "url": item.get("url", ""),
            }
        )
    return rows


def escape_cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def main():
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

    rows = []
    seen = set()
    for spec in args.specs:
        if ":" not in spec:
            print(f"[!] skipping invalid spec: {spec}")
            continue
        label, path = spec.split(":", 1)
        for row in load_failed(label, path):
            url = row.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            rows.append(row)

    lines = [
        "---",
        'title: "知乎抓取失败项"',
        'source: "zhihu"',
        f"updated: {datetime.date.today().isoformat()}",
        "tags: [zhihu, 抓取失败]",
        "---",
        "",
        "# 知乎抓取失败项",
        "",
        "These items failed during body fetch and can be retried manually later.",
        "",
    ]
    if rows:
        lines.extend(["| Range | # | Title | Reason | URL |", "|---|---:|---|---|---|"])
        for row in rows:
            lines.append(
                f"| {escape_cell(row['range'])} | {escape_cell(row['index'])} | "
                f"{escape_cell(row['title'])} | {escape_cell(row['reason'])} | {escape_cell(row['url'])} |"
            )
    else:
        lines.append("No failed items currently recorded.")

    note = zhihu_dir / resolve_failures_name(args.failures_name)
    note.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"failed_items: {len(rows)}")
    print(f"wrote: {note}")


if __name__ == "__main__":
    main()
