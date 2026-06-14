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
