from news_collect.contract import SourceAdapter, FetchResult
from news_collect.routing import is_local_path, route


class _Fake(SourceAdapter):
    def __init__(self, name, domains):
        self.name = name
        self.domains = domains
    def discover(self, state, fresh): return []
    def fetch(self, items): return FetchResult(status="ok")


def _adapters():
    return [_Fake("zhihu", ["zhihu.com", "zhuanlan.zhihu.com"]),
            _Fake("local", [])]


def test_is_local_path_distinguishes_urls():
    assert is_local_path("/Users/me/note.md") is True
    assert is_local_path("~/notes") is True
    assert is_local_path("https://zhihu.com/x") is False


def test_route_url_by_domain_with_www():
    a = route("https://www.zhihu.com/question/1", _adapters())
    assert a.name == "zhihu"


def test_route_subdomain():
    a = route("https://zhuanlan.zhihu.com/p/123", _adapters())
    assert a.name == "zhihu"


def test_route_local_path_to_local_adapter():
    a = route("/Users/me/note.md", _adapters())
    assert a.name == "local"


def test_route_unknown_domain_returns_none():
    assert route("https://unknown.example/x", _adapters()) is None
