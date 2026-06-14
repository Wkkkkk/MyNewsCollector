from news_collect.adapters.zhihu import ZhihuAdapter
from news_collect.contract import ItemRef
from news_collect.state import SourceState


class FakeRunner:
    """Records commands; returns a configurable returncode per stage."""
    def __init__(self, security_check=False, fail=False):
        self.calls = []
        self.security_check = security_check
        self.fail = fail
    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        class R:
            pass
        r = R()
        joined = " ".join(cmd)
        if self.security_check and "fetch_zhihu_history" in joined:
            r.returncode = 2  # adapter treats rc==2 as needs_login
        elif self.fail and "fetch_zhihu_batch" in joined:
            r.returncode = 1
        else:
            r.returncode = 0
        return r


def test_discover_returns_window_sentinel(tmp_path):
    adapter = ZhihuAdapter(profile="https://www.zhihu.com/people/x", start="2026-01-01T00:00:00+01:00",
                           vault="/v", workspace=tmp_path, now="2026-06-14T09:00:00+02:00",
                           skill_dir="/skill", runner=FakeRunner())
    refs = adapter.discover(SourceState(), fresh=False)
    assert len(refs) == 1
    assert refs[0].source == "zhihu"


def test_fetch_runs_full_pipeline_ok(tmp_path):
    runner = FakeRunner()
    adapter = ZhihuAdapter(profile="https://www.zhihu.com/people/x", start="2026-01-01T00:00:00+01:00",
                           vault="/v", workspace=tmp_path, now="2026-06-14T09:00:00+02:00",
                           skill_dir="/skill", runner=runner)
    refs = adapter.discover(SourceState(), fresh=False)
    result = adapter.fetch(refs)
    assert result.status == "ok"
    stages = [" ".join(c) for c in runner.calls]
    assert any("fetch_zhihu_history" in s for s in stages)
    assert any("fetch_zhihu_batch" in s for s in stages)
    assert any("format_articles" in s for s in stages)
    assert any("write_to_obsidian" in s for s in stages)
    assert any("--root-folder" in s and "News/zhihu" in s for s in stages)


def test_fetch_detects_security_check_as_needs_login(tmp_path):
    runner = FakeRunner(security_check=True)
    adapter = ZhihuAdapter(profile="https://www.zhihu.com/people/x", start="2026-01-01T00:00:00+01:00",
                           vault="/v", workspace=tmp_path, now="2026-06-14T09:00:00+02:00",
                           skill_dir="/skill", runner=runner)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "needs_login"
    stages = [" ".join(c) for c in runner.calls]
    assert not any("write_to_obsidian" in s for s in stages)


def test_fetch_batch_failure_is_error(tmp_path):
    runner = FakeRunner(fail=True)
    adapter = ZhihuAdapter(profile="https://www.zhihu.com/people/x", start="2026-01-01T00:00:00+01:00",
                           vault="/v", workspace=tmp_path, now="2026-06-14T09:00:00+02:00",
                           skill_dir="/skill", runner=runner)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "error"
