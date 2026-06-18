from types import SimpleNamespace

from news_collect.adapters.zhihu import ZhihuAdapter
from news_collect.state import SourceState


class FakeRunner:
    """Records commands and returns a pre-programmed return code per call.

    `rcs` is a list of return codes consumed in call order (defaults to 0 once
    exhausted). This decouples the double from script names / arg layout, so any
    pipeline stage can be made to fail without string-matching on its filename.
    """
    def __init__(self, rcs=None):
        self.calls = []
        self._rcs = list(rcs) if rcs else []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        rc = self._rcs.pop(0) if self._rcs else 0
        return SimpleNamespace(returncode=rc)


def _adapter(runner, tmp_path):
    return ZhihuAdapter(profile="https://www.zhihu.com/people/x",
                        start="2026-01-01T00:00:00+01:00",
                        vault="/v", workspace=tmp_path, now="2026-06-14T09:00:00+02:00",
                        skill_dir="/skill", runner=runner)


def test_discover_returns_window_sentinel(tmp_path):
    refs = _adapter(FakeRunner(), tmp_path).discover(SourceState(), fresh=False)
    assert len(refs) == 1
    assert refs[0].source == "zhihu"


def test_fetch_runs_full_pipeline_ok(tmp_path):
    runner = FakeRunner()  # all stages return 0
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "ok"
    stages = [" ".join(c) for c in runner.calls]
    assert any("fetch_zhihu_history" in s for s in stages)
    assert any("fetch_zhihu_batch" in s for s in stages)
    assert any("format_articles" in s for s in stages)
    assert any("write_to_obsidian" in s for s in stages)
    assert any("--root-folder" in s and "News/zhihu" in s for s in stages)


def test_fetch_detects_security_check_as_needs_login(tmp_path):
    runner = FakeRunner(rcs=[2])  # history stage signals security check
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "needs_login"
    # pipeline must stop after the failing history stage
    assert len(runner.calls) == 1
    stages = [" ".join(c) for c in runner.calls]
    assert not any("write_to_obsidian" in s for s in stages)


def test_fetch_history_generic_failure_is_error(tmp_path):
    runner = FakeRunner(rcs=[1])
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "error"
    assert len(runner.calls) == 1  # stops after history


def test_fetch_batch_failure_is_error(tmp_path):
    runner = FakeRunner(rcs=[0, 1])  # history ok, batch fails
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "error"


def test_fetch_batch_security_check_is_needs_login(tmp_path):
    runner = FakeRunner(rcs=[0, 2])  # history ok, batch hits dead session (/signin)
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "needs_login"
    # pipeline must stop at the batch stage, before format/write
    stages = [" ".join(c) for c in runner.calls]
    assert not any("write_to_obsidian" in s for s in stages)


def test_fetch_format_failure_is_error(tmp_path):
    runner = FakeRunner(rcs=[0, 0, 1])  # history+batch ok, format fails
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "error"
    stages = [" ".join(c) for c in runner.calls]
    assert not any("write_to_obsidian" in s for s in stages)  # stops before write


def test_fetch_write_failure_is_error(tmp_path):
    runner = FakeRunner(rcs=[0, 0, 0, 1])  # only write_to_obsidian fails
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "error"
    assert len(runner.calls) == 4  # reached the final stage


def test_fetch_empty_items_is_ok_with_no_calls(tmp_path):
    runner = FakeRunner()
    adapter = _adapter(runner, tmp_path)
    result = adapter.fetch([])
    assert result.status == "ok"
    assert result.written == []
    assert runner.calls == []
