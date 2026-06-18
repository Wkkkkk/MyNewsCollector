"""Tests for to_playwright_cookies: converting the saved cookie file into
Playwright add_cookies() entries WITHOUT clobbering a real expiry into a
session cookie.

Background: relogin used to save simple {name: value} and injection dropped
`expires`, so add_cookies() re-created every cookie as session-scoped
(expires=-1). That made z_c0's expiry permanently -1, which neutered the
batch fetcher's proactive TTL refresh. The fix preserves expires/domain/path.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from scripts.fetch_zhihu_batch import to_playwright_cookies


def _by_name(entries):
    return {c["name"]: c for c in entries}


def test_extended_format_preserves_real_expiry():
    raw = {"z_c0": {"value": "abc", "expires": 1893456000, "domain": ".zhihu.com", "path": "/"}}
    c = _by_name(to_playwright_cookies(raw))["z_c0"]
    assert c["value"] == "abc"
    assert c["expires"] == 1893456000
    assert c["domain"] == ".zhihu.com"
    assert c["path"] == "/"


def test_session_expiry_is_omitted_not_negative():
    # expires=-1 means session cookie; Playwright wants the key absent, not -1.
    raw = {"z_c0": {"value": "abc", "expires": -1}}
    c = _by_name(to_playwright_cookies(raw))["z_c0"]
    assert "expires" not in c


def test_simple_format_still_supported():
    raw = {"z_c0": "abc"}
    c = _by_name(to_playwright_cookies(raw))["z_c0"]
    assert c["value"] == "abc"
    assert c["domain"] == ".zhihu.com"
    assert c["path"] == "/"
    assert "expires" not in c


def test_empty_or_none_yields_no_entries():
    assert to_playwright_cookies(None) == []
    assert to_playwright_cookies({}) == []
