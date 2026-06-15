"""Regression tests for two Zhihu formatting bugs:

1. HTML tables were flattened into a single run-on line (no `<table>` handling
   in html_to_markdown).
2. The Obsidian write duplicated the title/author header because it re-wrapped a
   body that already carried fetch_zhihu_batch's own `# title` + `> 作者` block.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# write_to_obsidian.py imports a sibling module (zhihu_obsidian_config), so the
# scripts/ dir itself must be importable too.
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import yaml

from scripts.fetch_zhihu_batch import html_to_markdown
from scripts.write_to_obsidian import (
    strip_leading_title_block,
    build_preserved_frontmatter,
    _fm_scalar,
)


TABLE_HTML = """
<table>
<thead><tr><th>A</th><th>B</th><th>C</th></tr></thead>
<tbody>
<tr><td>Prompt engineering</td><td>语句 / 表达式</td><td>单条指令</td></tr>
<tr><td>Loop engineering</td><td>控制流</td><td>迭代/重试</td></tr>
</tbody>
</table>
"""


def test_table_becomes_pipe_table_not_runon():
    md, *_ = html_to_markdown(TABLE_HTML, images_dir=None)
    assert "| A | B | C |" in md
    assert "| --- | --- | --- |" in md
    assert "| Prompt engineering | 语句 / 表达式 | 单条指令 |" in md
    # the bug signature: adjacent cells concatenated with no separator
    assert "Prompt engineering语句" not in md


def test_table_preserves_inline_links_in_cells():
    html = ('<table><tr><td>x</td>'
            '<td><a href="https://e.com/p">Verifier</a></td></tr></table>')
    md, *_ = html_to_markdown(html, images_dir=None)
    assert "[Verifier](https://e.com/p)" in md


def test_strip_leading_title_block_removes_dup_header():
    body = "# T\n\n> 作者: A | 原文: [知乎链接](https://x/y)\n\nreal body"
    out = strip_leading_title_block(body)
    assert out == "real body"
    assert "# T" not in out
    assert "作者" not in out


def test_strip_leading_title_block_leaves_clean_body_untouched():
    body = "real body\n\nmore text"
    assert strip_leading_title_block(body) == body


def test_preserved_frontmatter_keeps_interaction_metadata():
    meta = {
        "interaction_action": "赞同了回答",
        "interaction_time": "2026-06-11T04:09:54+00:00",
        "voteup": "128",
        "activity_id": "abc123",
        "title": "ignored",  # non-preserved key must not leak in
    }
    fm = build_preserved_frontmatter(meta)
    assert 'interaction_action: "赞同了回答"' in fm
    assert 'interaction_time: "2026-06-11T04:09:54+00:00"' in fm
    assert "voteup: 128" in fm  # integer stays unquoted
    assert 'activity_id: "abc123"' in fm
    assert "title:" not in fm


def test_preserved_frontmatter_empty_when_no_interaction():
    assert build_preserved_frontmatter({"title": "x", "author": "y"}) == ""


def test_fm_scalar_title_with_embedded_quotes_is_valid_yaml():
    title = '如何看待由 OpenClaw 作者引发的 "Loop 工程" 讨论？'
    fm = f"title: {_fm_scalar(title)}\n"
    parsed = yaml.safe_load(fm)  # must not raise
    assert parsed["title"] == title


def test_fm_scalar_keeps_integers_unquoted():
    assert _fm_scalar("524") == "524"
    assert _fm_scalar(524) == "524"
