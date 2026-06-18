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
from scripts.fetch_zhihu_history import classify_api_failure


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


# --- history-stage API-failure classifier ------------------------------------
# The discovery script sees a JSON API response, not a page URL. The redirect
# in that JSON points at /account/unhuman even when the real cause is a dead
# session, so the `need_login` flag (not the URL) is the authoritative signal.

NEED_LOGIN_BODY = ('{"error":{"need_login":true,'
                   '"redirect":"https://www.zhihu.com/account/unhuman?type=S6E3V1&need_login=true",'
                   '"code":40352,"message":"系统监测到您的网络环境存在异常"}}')

ANTISPIDER_BODY = ('{"error":{"message":"请求过于频繁，请稍后再试","code":40362}}')


def test_need_login_body_is_logged_out():
    assert classify_api_failure(403, NEED_LOGIN_BODY) == "LOGGED_OUT"


def test_antispider_body_without_need_login_is_rate_limited():
    assert classify_api_failure(412, ANTISPIDER_BODY) == "RATE_LIMITED"


def test_signin_redirect_body_is_logged_out():
    body = '{"error":{"redirect":"https://www.zhihu.com/signin?next=%2F"}}'
    assert classify_api_failure(403, body) == "LOGGED_OUT"


def test_unparseable_body_defaults_to_rate_limited():
    # Crying "re-login" on an opaque failure is worse than backing off, so the
    # safe default is RATE_LIMITED (backoff, then a generic error if persistent).
    assert classify_api_failure(403, "<html>gateway timeout</html>") == "RATE_LIMITED"
