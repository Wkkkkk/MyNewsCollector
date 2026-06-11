#!/usr/bin/env python3
"""Conservative Markdown formatter for exported Zhihu/Obsidian articles."""

from __future__ import annotations

import argparse
import os
import difflib
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


REFERENCE_HEADING_RE = re.compile(
    r"^\*\*((?:参考|References?|延伸阅读|更多阅读)[^*]{0,30})\*\*$",
    re.IGNORECASE,
)
REFERENCE_MARKER_RE = re.compile(r"(参考|References?|延伸阅读|更多阅读)", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)", re.DOTALL)
URL_TEXT_RE = re.compile(r"^https?://", re.IGNORECASE)
IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
CARD_LINK_RE = re.compile(
    r"^\[\s*(?P<image>!\[[^\]]*\]\([^)]+\))\s*(?P<title>.*?)\]\((?P<url>https?://[^)]+)\)\s*$",
    re.DOTALL,
)
FRONTMATTER_FIELD_RE = re.compile(r"^(?P<key>[A-Za-z_][\w-]*):\s*(?P<value>.*?)\s*$")


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + len("\n---\n")], text[end + len("\n---\n") :]


def parse_frontmatter_fields(frontmatter: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        match = FRONTMATTER_FIELD_RE.match(line)
        if not match:
            continue
        value = match.group("value").strip().strip('"').strip("'")
        fields[match.group("key")] = value
    return fields


def parse_frontmatter_datetime(frontmatter: str, field: str) -> datetime | None:
    value = parse_frontmatter_fields(frontmatter).get(field)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def set_file_times(path: Path, dt: datetime, setfile_path: str | None) -> bool:
    timestamp = dt.timestamp()
    os.utime(path, (timestamp, timestamp))
    if not setfile_path:
        return False
    local_dt = dt.astimezone()
    setfile_date = local_dt.strftime("%m/%d/%Y %H:%M:%S")
    try:
        subprocess.run([setfile_path, "-d", setfile_date, "-m", setfile_date, str(path)], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def infer_code_language(code: str) -> str:
    sample = code[:500]
    stripped = code.strip()
    if re.search(
        r"#include|std::|ssize_t|loff_t|template\s*[\n<]|_LIBCPP|"
        r"\bclass\s+\w+|(^|\n)\s*(public|private|protected):|"
        r"\b(static|virtual|const)\s+\w+|::\w+",
        sample,
    ):
        return "cpp"
    if re.search(r"package\s+\w+|func\s+\w+\(", sample):
        return "go"
    if re.search(r"def\s+\w+\(|import\s+\w+|from\s+\w+\s+import", sample):
        return "python"
    if re.search(r"fn\s+\w+\(|use\s+[\w:]+|impl\s+", sample):
        return "rust"
    if re.search(r"SELECT\s+.+\s+FROM|CREATE\s+TABLE|INSERT\s+INTO", sample, re.IGNORECASE):
        return "sql"
    if re.search(r"^\s*[{[]", stripped) and re.search(r"^\s*[}\]]\s*$", stripped[-5:], re.DOTALL):
        return "json"
    if re.search(r"(^|\n)\s*(npm|pnpm|yarn|git|curl|wget|python3?|pip|cd|mkdir|cp|mv|rm)\s+", sample):
        return "bash"
    if re.search(r"console\.log|function\s+\w+\(|const\s+\w+\s*=|let\s+\w+\s*=|=>", sample):
        return "javascript"
    if re.search(r"(^|\n)\s*[-\w]+:\s+", sample):
        return "yaml"
    return ""


def normalize_heading_hierarchy(body: str) -> str:
    # Keep heading hierarchy untouched; exported code blocks can contain leading '#'
    # lines, and preserving code is more important than demoting stray headings.
    return body
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    seen_h1 = False
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and re.match(r"^# [^#]", stripped):
            if seen_h1:
                leading = line[: len(line) - len(line.lstrip())]
                out.append(f"{leading}## {stripped[2:]}")
                continue
            seen_h1 = True
        out.append(line)
    return "\n".join(out)


def clean_link_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" \t\r\n:-：|*")


def decode_zhihu_redirect(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc != "link.zhihu.com":
        return url
    target = parse_qs(parsed.query).get("target", [""])[0]
    return unquote(target) if target else url


def is_zhihu_entity_link(url: str) -> bool:
    return urlparse(url).netloc == "zhida.zhihu.com"


def is_source_url(url: str) -> bool:
    return bool(URL_TEXT_RE.match(url)) and not is_zhihu_entity_link(url)


def link_display_url(text: str, url: str) -> str:
    text = clean_link_text(text)
    target = decode_zhihu_redirect(url)
    if URL_TEXT_RE.match(text):
        return text
    if is_zhihu_entity_link(target):
        return ""
    return target


def split_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    start = 0
    bracket_depth = 0
    i = 0
    while i < len(text):
        char = text[i]
        if char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth:
            bracket_depth -= 1
        elif char == "\n" and bracket_depth == 0:
            j = i
            while j < len(text) and text[j] == "\n":
                j += 1
            if j - i >= 2:
                paragraphs.append(text[start:i])
                start = j
                i = j
                continue
        i += 1
    paragraphs.append(text[start:])
    return paragraphs


def paragraph_to_link_list(paragraph: str) -> str | None:
    if re.search(r"(?m)^\s*[-*+]\s+", paragraph):
        return None
    if re.search(r"(?m)^\s*\d+\.\s+", paragraph):
        return None
    if "\n" in paragraph and max((len(line) for line in paragraph.splitlines()), default=0) < 200:
        return None

    matches = list(MARKDOWN_LINK_RE.finditer(paragraph))
    if len(matches) < 4:
        return None

    raw_urls = [link_display_url(match.group(1), match.group(2)) for match in matches]
    raw_urls = [url for url in raw_urls if is_source_url(url)]
    if len(raw_urls) < 3:
        return None

    prefix = clean_link_text(paragraph[: matches[0].start()])
    if prefix and len(prefix) > 40:
        return None

    residual = MARKDOWN_LINK_RE.sub(" ", paragraph)
    residual = IMAGE_RE.sub(" ", residual)
    residual = clean_link_text(residual)
    prefix_suggests_source_list = bool(re.search(r"(rss|source|sources|links?|链接|参考|阅读|资源)", prefix, re.IGNORECASE))
    if not prefix_suggests_source_list and (
        len(residual) > 80 or re.search(r"[。！？；.!?;]", residual)
    ):
        return None

    items: list[tuple[str, str]] = []
    pending_label = ""
    cursor = matches[0].end()
    for index, match in enumerate(matches):
        between = paragraph[cursor : match.start()]
        if between:
            pending_label = clean_link_text(f"{pending_label} {between}")

        text = clean_link_text(match.group(1))
        url = decode_zhihu_redirect(match.group(2))
        display_url = link_display_url(text, url)

        if is_source_url(display_url):
            label = pending_label or text or display_url
            label = clean_link_text(label)
            items.append((label, display_url))
            pending_label = ""
        else:
            pending_label = clean_link_text(f"{pending_label} {text}")

        cursor = match.end()
        if index == len(matches) - 1:
            tail = clean_link_text(paragraph[cursor:])
            if tail and pending_label:
                pending_label = clean_link_text(f"{pending_label} {tail}")

    if len(items) < 3:
        return None

    title = "## Links"
    if prefix:
        lowered = prefix.lower().replace(" ", "")
        if "rss" in lowered:
            title = "## RSS Sources"

    lines = [title, ""]
    for label, url in items:
        lines.append(f"- [{label}]({url})")
    return "\n".join(lines)


def recover_collapsed_link_lists(body: str) -> str:
    paragraphs = split_paragraphs(body)
    recovered: list[str] = []
    for paragraph in paragraphs:
        replacement = paragraph_to_link_list(paragraph)
        recovered.append(replacement if replacement else paragraph)
    return "\n\n".join(recovered)


def clean_card_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title)
    title = IMAGE_RE.sub("", title)
    return title.strip(" \t\r\n")


def recover_broken_card_links(body: str) -> str:
    paragraphs = split_paragraphs(body)
    recovered: list[str] = []
    for paragraph in paragraphs:
        match = CARD_LINK_RE.match(paragraph)
        if not match:
            recovered.append(paragraph)
            continue
        image = match.group("image").strip()
        title = clean_card_title(match.group("title"))
        url = decode_zhihu_redirect(match.group("url"))
        if title:
            recovered.append(f"{image}\n\n[{title}]({url})")
        else:
            recovered.append(f"{image}\n\n<{url}>")
    return "\n\n".join(recovered)


def convert_multiline_inline_code(body: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped.startswith("`") or stripped.startswith("```"):
            out.append(line)
            i += 1
            continue
        if stripped.count("`") >= 2:
            out.append(line)
            i += 1
            continue

        code_lines: list[str] = [line[line.index("`") + 1 :]]
        trailing = ""
        j = i + 1
        found_close = False
        while j < len(lines):
            current = lines[j]
            if current.strip().startswith("```"):
                break
            tick = current.find("`")
            if tick != -1:
                code_lines.append(current[:tick])
                trailing = current[tick + 1 :].strip()
                found_close = True
                break
            code_lines.append(current)
            j += 1

        if not found_close or len(code_lines) < 2:
            out.append(line)
            i += 1
            continue

        code = "\n".join(code_lines).strip("\n")
        if not code.strip():
            out.append(line)
            i += 1
            continue
        if "```" in code:
            out.append(line)
            i += 1
            continue

        language = infer_code_language(code)
        out.append("")
        out.append(f"```{language}")
        out.extend(code.rstrip().split("\n"))
        out.append("```")
        if trailing:
            out.append("")
            out.append(trailing)
        i = j + 1

    return "\n".join(out)


def normalize_reference_headings(lines: list[str]) -> list[str]:
    normalized: list[str] = []
    for line in lines:
        match = REFERENCE_HEADING_RE.match(line.strip())
        if match:
            normalized.append(f"## {match.group(1).strip()}")
        else:
            normalized.append(line)
    return normalized


def is_reference_heading(line: str) -> bool:
    stripped = line.strip()
    if REFERENCE_HEADING_RE.match(stripped):
        return True
    if not stripped.startswith("#"):
        return False
    return bool(REFERENCE_MARKER_RE.search(stripped.lstrip("#").strip()))


def unwrap_reference_section_links(body: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    in_reference_section = False
    reference_items_seen = False
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue

        if not in_fence and stripped.startswith("#"):
            in_reference_section = is_reference_heading(line)
            reference_items_seen = False
        elif not in_fence and is_reference_heading(line):
            in_reference_section = True
            reference_items_seen = False

        if in_reference_section and not in_fence:
            is_reference_item = bool(
                re.match(r"^([-*+]\s+|\d+\.\s+)", stripped)
                or (MARKDOWN_LINK_RE.search(line) and not reference_items_seen)
            )
            if stripped and not is_reference_item and reference_items_seen:
                in_reference_section = False
            elif is_reference_item:
                reference_items_seen = True

        if in_reference_section and not in_fence:
            line = MARKDOWN_LINK_RE.sub(
                lambda match: f"[{match.group(1)}]({decode_zhihu_redirect(match.group(2))})",
                line,
            )
        out.append(line)

    return "\n".join(out)


def line_kind(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("```"):
        return "fence"
    if stripped.startswith("#"):
        return "heading"
    if stripped.startswith(">"):
        return "quote"
    if IMAGE_RE.fullmatch(stripped):
        return "image"
    if re.match(r"^[-*+] \S", stripped) or re.match(r"^\d+\. \S", stripped):
        return "list"
    return "text"


def is_structural(line: str) -> bool:
    return line_kind(line) != "text"


def normalize_spacing(body: str) -> str:
    lines = body.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = normalize_reference_headings(lines)

    out: list[str] = []
    in_fence = False
    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_fence and out and out[-1] == "":
                out.pop()
            if not in_fence and out and out[-1] != "":
                out.append("")
            out.append(line)
            in_fence = not in_fence
            continue

        if in_fence:
            out.append(raw_line.rstrip("\n"))
            continue

        if stripped == "":
            if out and out[-1] != "":
                out.append("")
            continue

        kind = line_kind(line)
        prev_kind = line_kind(out[-1]) if out else "text"
        if (
            kind != "text"
            and out
            and out[-1] != ""
            and not (kind == "list" and prev_kind == "list")
            and not (kind == "quote" and prev_kind == "quote")
        ):
            out.append("")

        out.append(line)

    compact: list[str] = []
    for line in out:
        if line == "" and (not compact or compact[-1] == ""):
            continue
        compact.append(line)

    result: list[str] = []
    in_fence = False
    for i, line in enumerate(compact):
        result.append(line)
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if not in_fence and i + 1 < len(compact) and compact[i + 1] != "":
                result.append("")
            continue
        if in_fence:
            continue
        kind = line_kind(line)
        next_kind = line_kind(compact[i + 1]) if i + 1 < len(compact) else "text"
        if (
            kind != "text"
            and i + 1 < len(compact)
            and compact[i + 1] != ""
            and not (kind == "list" and next_kind == "list")
            and not (kind == "quote" and next_kind == "quote")
        ):
            result.append("")

    while result and result[0] == "":
        result.pop(0)
    while result and result[-1] == "":
        result.pop()
    return "\n".join(result) + "\n"


def format_markdown(text: str) -> str:
    frontmatter, body = split_frontmatter(text)
    body = normalize_heading_hierarchy(body)
    body = convert_multiline_inline_code(body)
    body = recover_broken_card_links(body)
    body = recover_collapsed_link_lists(body)
    body = unwrap_reference_section_links(body)
    body = normalize_spacing(body)
    if frontmatter:
        return frontmatter.rstrip() + "\n\n" + body
    return body


def iter_markdown_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
    return sorted(set(files))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--set-times", action="store_true", help="Set file times from a frontmatter field.")
    parser.add_argument("--time-field", default="interaction_time", help="Frontmatter field used with --set-times.")
    parser.add_argument(
        "--no-created-time",
        action="store_true",
        help="Only set access/modified time; skip macOS creation time.",
    )
    args = parser.parse_args()

    files = iter_markdown_files(args.paths)
    changed = 0
    times_available = 0
    times_set = 0
    creation_times_set = 0
    setfile_path = None if args.no_created_time else shutil.which("SetFile")
    for path in files:
        original = path.read_text(encoding="utf-8")
        frontmatter, _ = split_frontmatter(original)
        file_time = parse_frontmatter_datetime(frontmatter, args.time_field) if args.set_times else None
        if file_time:
            times_available += 1
        formatted = format_markdown(original)
        content_changed = original != formatted
        if content_changed:
            changed += 1
            print(path)
            if args.diff:
                diff = difflib.unified_diff(
                    original.splitlines(),
                    formatted.splitlines(),
                    fromfile=str(path),
                    tofile=str(path),
                    lineterm="",
                )
                print("\n".join(diff))
            if not args.dry_run:
                path.write_text(formatted, encoding="utf-8")

        if args.set_times and file_time:
            if args.dry_run:
                times_set += 1
            else:
                creation_set = set_file_times(path, file_time, setfile_path)
                times_set += 1
                if creation_set:
                    creation_times_set += 1

    summary = f"scanned={len(files)} changed={changed} dry_run={args.dry_run}"
    if args.set_times:
        action = "times_would_set" if args.dry_run else "times_set"
        summary += f" {action}={times_set} time_field={args.time_field}"
        summary += f" time_field_found={times_available}"
        if not args.dry_run:
            summary += f" creation_times_set={creation_times_set}"
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
