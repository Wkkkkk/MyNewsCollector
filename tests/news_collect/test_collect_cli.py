import pytest

from news_collect.collect import select_sources, build_adapters
from news_collect.config import Config


def test_select_sources_default_is_all_enabled():
    assert select_sources(["rss", "zhihu", "local"], only=None, skip=None) == ["rss", "zhihu", "local"]


def test_select_sources_only():
    assert select_sources(["rss", "zhihu", "local"], only="rss,local", skip=None) == ["rss", "local"]


def test_select_sources_skip():
    assert select_sources(["rss", "zhihu", "local"], only=None, skip="zhihu") == ["rss", "local"]


def test_select_sources_only_validates_membership():
    with pytest.raises(ValueError):
        select_sources(["rss"], only="nope", skip=None)


def test_build_adapters_constructs_enabled(tmp_path):
    cfg = Config(vault=str(tmp_path / "vault"), sources={
        "rss": {"enabled": True, "feeds": ["https://e/feed"]},
        "local": {"enabled": True, "paths": [str(tmp_path)]},
        "zhihu": {"enabled": False},
    })
    adapters = build_adapters(cfg, workspace=tmp_path, now="t", skill_dir="/skill")
    names = {a.name for a in adapters}
    assert names == {"rss", "local"}  # zhihu disabled


from news_collect.collect import _scheduled_exit_code
from news_collect.runlog import SourceOutcome


def _oc(status="ok", count=0):
    return SourceOutcome(source="s", status=status, count=count, message="")


def test_exit_code_zero_when_all_ok_with_new():
    assert _scheduled_exit_code([_oc("ok", 2), _oc("ok", 1)]) == 0


def test_exit_code_zero_when_partial_ok():
    # fault isolation: one dead source must not fail the whole run
    assert _scheduled_exit_code([_oc("ok"), _oc("error")]) == 0


def test_exit_code_one_when_all_failed():
    assert _scheduled_exit_code([_oc("error"), _oc("needs_login")]) == 1


def test_exit_code_zero_when_no_outcomes():
    assert _scheduled_exit_code([]) == 0


def test_exit_code_44_when_all_ok_and_zero_new():
    assert _scheduled_exit_code([_oc("ok", 0), _oc("ok", 0)]) == 44


def test_exit_code_zero_when_problem_present_even_zero_new():
    assert _scheduled_exit_code([_oc("ok", 0), _oc("error", 0)]) == 0
