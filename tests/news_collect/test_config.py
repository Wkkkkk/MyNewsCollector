from news_collect.config import load_config


def test_load_config_parses_sources(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '''
vault = "/Users/me/Vault"

[sources.rss]
enabled = true
feeds = ["https://a.example/feed", "https://b.example/feed"]

[sources.zhihu]
enabled = true
profile = "https://www.zhihu.com/people/someone"
start = "2026-01-01T00:00:00+01:00"

[sources.local]
enabled = false
''',
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.vault == "/Users/me/Vault"
    assert cfg.enabled_sources() == ["rss", "zhihu"]
    assert cfg.source("rss")["feeds"] == ["https://a.example/feed", "https://b.example/feed"]
    assert cfg.source("zhihu")["profile"].endswith("/someone")


def test_enabled_sources_excludes_disabled(tmp_path):
    cfg_file = tmp_path / "c.toml"
    cfg_file.write_text(
        'vault = "/v"\n[sources.rss]\nenabled = false\nfeeds = []\n', encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.enabled_sources() == []
