from news_collect.contract import SourceAdapter, ItemRef, FetchResult
from news_collect.orchestrator import run_scheduled
from news_collect.state import load_state, save_state, SourceState


class FakeAdapter(SourceAdapter):
    def __init__(self, name, discovered=None, result=None, raise_exc=None):
        self.name = name
        self.domains = []
        self._discovered = discovered or []
        self._result = result
        self._raise = raise_exc
        self.fetched = None
    def discover(self, state, fresh):
        return list(self._discovered)
    def fetch(self, items):
        if self._raise:
            raise self._raise
        self.fetched = items
        return self._result


def _ctx(tmp_path):
    return dict(workspace=tmp_path, vault=tmp_path / "vault",
                now="2026-06-14T09:00:00+02:00",
                notifier=type("N", (), {"notify": lambda self, t, m: None})(),
                runlog_path=tmp_path / "vault" / "News" / "run-log.md")


def test_ok_source_advances_state(tmp_path):
    refs = [ItemRef(key="a", source="rss"), ItemRef(key="b", source="rss")]
    a = FakeAdapter("rss", discovered=refs, result=FetchResult(status="ok", written=refs))
    out = run_scheduled([a], selected=["rss"], fresh=False, force=False, dry_run=False, **_ctx(tmp_path))
    assert out[0].status == "ok" and out[0].count == 2
    st = load_state(tmp_path, "rss")
    assert st.seen == {"a", "b"} and st.last_run == "2026-06-14T09:00:00+02:00"


def test_already_seen_items_filtered(tmp_path):
    save_state(tmp_path, "rss", SourceState(last_run="t", seen={"a"}))
    refs = [ItemRef(key="a", source="rss"), ItemRef(key="b", source="rss")]
    a = FakeAdapter("rss", discovered=refs,
                    result=FetchResult(status="ok", written=[ItemRef(key="b", source="rss")]))
    run_scheduled([a], selected=["rss"], fresh=False, force=False, dry_run=False, **_ctx(tmp_path))
    assert [r.key for r in a.fetched] == ["b"]  # "a" filtered out before fetch


def test_needs_login_leaves_state_intact(tmp_path):
    save_state(tmp_path, "zhihu", SourceState(last_run="OLD", seen={"x"}))
    a = FakeAdapter("zhihu", discovered=[ItemRef(key="y", source="zhihu")],
                    result=FetchResult(status="needs_login", message="cookie expired"))
    out = run_scheduled([a], selected=["zhihu"], fresh=False, force=False, dry_run=False, **_ctx(tmp_path))
    assert out[0].status == "needs_login"
    st = load_state(tmp_path, "zhihu")
    assert st.last_run == "OLD" and st.seen == {"x"}  # untouched


def test_exception_is_isolated(tmp_path):
    bad = FakeAdapter("rss", discovered=[ItemRef(key="a", source="rss")], raise_exc=RuntimeError("boom"))
    good = FakeAdapter("local", discovered=[ItemRef(key="b", source="local")],
                       result=FetchResult(status="ok", written=[ItemRef(key="b", source="local")]))
    out = run_scheduled([bad, good], selected=["rss", "local"], fresh=False, force=False, dry_run=False, **_ctx(tmp_path))
    statuses = {o.source: o.status for o in out}
    assert statuses["rss"] == "error" and statuses["local"] == "ok"


def test_dry_run_writes_no_state(tmp_path):
    refs = [ItemRef(key="a", source="rss")]
    a = FakeAdapter("rss", discovered=refs, result=FetchResult(status="ok", written=refs))
    run_scheduled([a], selected=["rss"], fresh=False, force=False, dry_run=True, **_ctx(tmp_path))
    assert a.fetched is None  # fetch never called
    assert load_state(tmp_path, "rss").seen == set()


def test_force_bypasses_seen_filter(tmp_path):
    save_state(tmp_path, "rss", SourceState(last_run="t", seen={"a"}))
    refs = [ItemRef(key="a", source="rss")]
    a = FakeAdapter("rss", discovered=refs, result=FetchResult(status="ok", written=refs))
    run_scheduled([a], selected=["rss"], fresh=False, force=True, dry_run=False, **_ctx(tmp_path))
    assert [r.key for r in a.fetched] == ["a"]
