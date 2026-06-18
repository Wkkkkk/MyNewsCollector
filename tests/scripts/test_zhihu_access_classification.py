"""Tests for classify_access: the tri-state-inspired classifier that distinguishes
Zhihu access outcomes so a rate-limit trip (`unhuman`) is no longer misdiagnosed as
cookie expiry (which wrongly advised re-login + aborted the batch).

Four outcomes:
- OK           normal page reached -> proceed
- LOGGED_OUT   redirected to /signin -> session dead, re-login + abort (the ONLY re-login case)
- RATE_LIMITED redirected to /account/unhuman -> cookie still valid, anti-bot trip -> backoff
- NETWORK      navigation raised (timeout/etc) -> indeterminate -> retry with backoff
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from scripts.fetch_zhihu_batch import classify_access


def test_normal_url_is_ok():
    assert classify_access("https://zhuanlan.zhihu.com/p/123456") == "OK"


def test_signin_redirect_is_logged_out():
    assert classify_access("https://www.zhihu.com/signin?next=%2F") == "LOGGED_OUT"


def test_unhuman_redirect_is_rate_limited():
    assert classify_access("https://www.zhihu.com/account/unhuman?type=...") == "RATE_LIMITED"


def test_exception_is_network_regardless_of_url():
    assert classify_access("https://zhuanlan.zhihu.com/p/123456",
                           exc=TimeoutError("nav timeout")) == "NETWORK"


def test_logged_out_takes_precedence_over_rate_limited():
    # A URL containing both signals is degenerate, but logged-out is the more
    # definitive verdict: re-login is required either way.
    assert classify_access("https://www.zhihu.com/signin/unhuman") == "LOGGED_OUT"
