from news_collect.contract import SourceAdapter, ItemRef, FetchResult
from news_collect.orchestrator import run_ingest


class FakeAdapter(SourceAdapter):
    def __init__(self, name, domains):
        self.name = name
        self.domains = domains
        self.fetched = None
    def discover(self, state, fresh): return []
    def refs_for(self, targets):
        return [ItemRef(key=t, source=self.name, url=t) for t in targets]
    def fetch(self, items):
        self.fetched = items
        return FetchResult(status="ok", written=items)


def _ctx(tmp_path):
    return dict(workspace=tmp_path, vault=tmp_path / "vault",
                now="2026-06-14T09:00:00+02:00",
                notifier=type("N", (), {"notify": lambda self, t, m: None})(),
                runlog_path=tmp_path / "vault" / "News" / "run-log.md")


def test_routes_targets_to_adapters(tmp_path):
    z = FakeAdapter("zhihu", ["zhihu.com"])
    out = run_ingest([z], ["https://zhihu.com/p/1", "https://zhihu.com/p/2"],
                     force=False, dry_run=False, **_ctx(tmp_path))
    assert [r.key for r in z.fetched] == ["https://zhihu.com/p/1", "https://zhihu.com/p/2"]
    assert out[0].status == "ok" and out[0].count == 2


def test_unknown_domain_reported_as_error(tmp_path):
    z = FakeAdapter("zhihu", ["zhihu.com"])
    out = run_ingest([z], ["https://unknown.example/x"], force=False, dry_run=False, **_ctx(tmp_path))
    errs = [o for o in out if o.status == "error"]
    assert errs and "no adapter" in errs[0].message
    assert "unknown.example" in errs[0].message
