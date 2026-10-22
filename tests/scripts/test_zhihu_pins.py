"""Pins (想法) have no page fetch: discovery keeps the feed's body and the batch
fetcher renders it directly, so they need a title, a /pin/ url and the content."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from scripts.fetch_zhihu_batch import write_item_markdown
from scripts.fetch_zhihu_history import item_from_activity


def pin_activity(action="赞同了想法"):
    return {
        "id": "1792393656313",
        "action_text": action,
        "target": {
            "type": "pin",
            "id": "2094744309690000857",
            "like_count": 3,
            "author": {"name": "someone"},
            "content_html": "<div><p>第一行标题<br/><br/>正文第二段</p></div>",
        },
    }


def test_liked_pin_is_discovered_with_body():
    item = item_from_activity(pin_activity())
    assert item["type"] == "pin"
    assert item["url"] == "https://www.zhihu.com/pin/2094744309690000857"
    assert item["title"] == "第一行标题"
    assert item["voteup"] == 3
    assert "正文第二段" in item["content_html"]


def test_unliked_pin_activity_is_ignored():
    assert item_from_activity(pin_activity(action="发布了想法")) is None


def test_pin_is_written_with_frontmatter(tmp_path):
    item = item_from_activity(pin_activity())
    write_item_markdown(str(tmp_path), 0, item["title"], item, "", "正文", [], {})
    text = (tmp_path / "0001_第一行标题.md").read_text(encoding="utf-8")
    assert 'url: "https://www.zhihu.com/pin/2094744309690000857"' in text
    assert 'interaction_action: "赞同了想法"' in text
    assert "正文" in text
