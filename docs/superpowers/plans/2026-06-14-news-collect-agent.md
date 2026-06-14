# News Collect Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, locally-scheduled multi-source content collector that pulls new content weekly from Zhihu, RSS feeds, and local markdown into one Obsidian vault, with manual-login-on-failure handled via notify-and-resume.

**Architecture:** A thin Python orchestrator (`collect.py`) drives source adapters that all conform to one `SourceAdapter` contract. Each adapter `discover()`s new items (scheduled mode) or is handed explicit items (ingest mode), then `fetch()`es them through a shared writer into `{Vault}/News/{source}/`. Per-source JSON state makes runs incremental and idempotent; failures are isolated per source and surfaced via a desktop notification plus an appended `run-log.md`. A `launchd` LaunchAgent fires it Friday 09:00 local.

**Tech Stack:** Python 3.14 (built-in `tomllib`), pytest, `feedparser` + `markdownify` (RSS), `PyYAML` (frontmatter). Reuses existing `scripts/fetch_zhihu_*.py` and `scripts/write_to_obsidian.py` for Zhihu. macOS `launchd` for scheduling, `osascript` for notifications.

**Reference spec:** `docs/superpowers/specs/2026-06-14-news-collect-agent-design.md`

---

## File Structure

```
news_collect/
├── __init__.py
├── contract.py         # ItemRef, FetchResult, NormalizedDoc, SourceAdapter ABC
├── keys.py             # url_key(), file_key()  — stable dedup keys
├── state.py            # SourceState, load_state(), save_state()
├── writer.py           # slugify(), write_doc()  — normalized doc -> vault markdown
├── runlog.py           # SourceOutcome, append_runlog()
├── notify.py           # summarize(), MacNotifier
├── routing.py          # is_local_path(), route()
├── orchestrator.py     # run_scheduled(), run_ingest()
├── config.py           # Config, load_config()
├── collect.py          # CLI entry point (scheduled run + ingest subcommand)
├── requirements.txt    # feedparser, markdownify, PyYAML
└── adapters/
    ├── __init__.py
    ├── rss.py          # RssAdapter
    ├── local.py        # LocalAdapter
    └── zhihu.py        # ZhihuAdapter (wraps existing scripts/)

deploy/
└── com.kunwu.news-collect.plist.template

tests/news_collect/
├── conftest.py
├── test_keys.py
├── test_state.py
├── test_writer.py
├── test_runlog.py
├── test_notify.py
├── test_routing.py
├── test_orchestrator_scheduled.py
├── test_orchestrator_ingest.py
├── test_config.py
├── test_rss_adapter.py
├── test_local_adapter.py
├── test_zhihu_adapter.py
└── fixtures/sample_feed.xml
```

Responsibilities: each module has one job. `contract.py` defines the shared vocabulary every
other module imports. Adapters never touch state files or the run-log directly — the
orchestrator owns those. The writer is the only module that knows the vault folder layout
(except the Zhihu adapter, which delegates to the existing `write_to_obsidian.py`).

---

## Task 1: Scaffold the package and dependencies

**Files:**
- Create: `news_collect/__init__.py` (empty)
- Create: `news_collect/adapters/__init__.py` (empty)
- Create: `news_collect/requirements.txt`
- Create: `tests/news_collect/__init__.py` (empty)
- Create: `tests/news_collect/conftest.py`
- Create: `pytest.ini`

- [ ] **Step 1: Create package directories and empty init files**

```bash
mkdir -p news_collect/adapters tests/news_collect/fixtures deploy
touch news_collect/__init__.py news_collect/adapters/__init__.py tests/news_collect/__init__.py
```

- [ ] **Step 2: Write `news_collect/requirements.txt`**

```
feedparser>=6.0.0
markdownify>=0.11.0
PyYAML>=6.0
```

- [ ] **Step 3: Write `pytest.ini` at repo root**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -ra
```

- [ ] **Step 4: Write `tests/news_collect/conftest.py`**

```python
import sys
from pathlib import Path

# Make the repo root importable so `import news_collect...` works under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
```

- [ ] **Step 5: Install dependencies into the existing venv**

Run: `venv/bin/pip install -r news_collect/requirements.txt && venv/bin/pip install pytest`
Expected: installs complete without error.

- [ ] **Step 6: Verify pytest collects (no tests yet)**

Run: `venv/bin/pytest -q`
Expected: `no tests ran` (exit code 5) — confirms collection works.

- [ ] **Step 7: Commit**

```bash
git add news_collect tests pytest.ini deploy
git commit -m "chore: scaffold news_collect package and test harness"
```

---

## Task 2: Define the contract types

**Files:**
- Create: `news_collect/contract.py`
- Test: `tests/news_collect/test_contract.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_contract.py
from news_collect.contract import ItemRef, FetchResult, NormalizedDoc


def test_itemref_defaults():
    ref = ItemRef(key="k1", source="rss")
    assert ref.key == "k1"
    assert ref.source == "rss"
    assert ref.url is None
    assert ref.meta == {}


def test_fetchresult_keys_property():
    r = FetchResult(
        status="ok",
        written=[ItemRef(key="a", source="rss"), ItemRef(key="b", source="rss")],
    )
    assert r.keys == ["a", "b"]
    assert r.message == ""


def test_normalizeddoc_holds_body():
    doc = NormalizedDoc(source="rss", title="Hello", body_md="# Hello")
    assert doc.title == "Hello"
    assert doc.extra_frontmatter == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.contract'`

- [ ] **Step 3: Write `news_collect/contract.py`**

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ItemRef:
    """A reference to one collectable item, with a stable dedup key."""
    key: str
    source: str
    url: str | None = None
    path: str | None = None
    title: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class NormalizedDoc:
    """Source-agnostic document ready to be written to the vault."""
    source: str
    title: str
    body_md: str
    url: str | None = None
    published: str | None = None
    extra_frontmatter: dict = field(default_factory=dict)


@dataclass
class FetchResult:
    """Outcome of an adapter.fetch() call."""
    status: str  # "ok" | "needs_login" | "error"
    written: list[ItemRef] = field(default_factory=list)
    message: str = ""

    @property
    def keys(self) -> list[str]:
        return [item.key for item in self.written]


class SourceAdapter(ABC):
    """Interface every source adapter implements."""
    name: str = ""
    domains: list[str] = []

    @abstractmethod
    def discover(self, state, fresh: bool) -> list[ItemRef]:
        """Return refs for items new since last run (scheduled mode)."""

    @abstractmethod
    def fetch(self, items: list[ItemRef]) -> FetchResult:
        """Fetch, normalize, and write the given items. Returns a FetchResult."""

    def refs_for(self, targets: list[str]) -> list[ItemRef]:
        """Build ItemRefs from explicit ingest targets (URLs by default)."""
        return [ItemRef(key=t, source=self.name, url=t) for t in targets]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_contract.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/contract.py tests/news_collect/test_contract.py
git commit -m "feat: add news_collect contract types"
```

---

## Task 3: Stable dedup keys

**Files:**
- Create: `news_collect/keys.py`
- Test: `tests/news_collect/test_keys.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_keys.py
from pathlib import Path

from news_collect.keys import url_key, file_key


def test_url_key_strips_tracking_and_fragment():
    a = url_key("https://example.com/post?utm_source=x&id=5#section")
    b = url_key("https://example.com/post?id=5")
    assert a == b


def test_url_key_normalizes_trailing_slash_and_scheme_case():
    assert url_key("HTTP://Example.com/post/") == url_key("http://example.com/post")


def test_file_key_changes_with_content(tmp_path):
    f = tmp_path / "note.md"
    f.write_text("one", encoding="utf-8")
    k1 = file_key(f)
    f.write_text("two", encoding="utf-8")
    k2 = file_key(f)
    assert k1 != k2
    assert k1.startswith(str(Path(f).resolve()) + "#")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_keys.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.keys'`

- [ ] **Step 3: Write `news_collect/keys.py`**

```python
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "ref", "spm")


def url_key(url: str) -> str:
    """Normalize a URL into a stable dedup key (drops tracking params, fragment, trailing slash)."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    kept = [(k, v) for k, v in parse_qsl(parts.query)
            if not any(k.lower().startswith(p) for p in _TRACKING_PREFIXES)]
    query = urlencode(sorted(kept))
    return urlunsplit((scheme, netloc, path, query, ""))


def file_key(path) -> str:
    """Stable key for a local file: absolute path + short content hash."""
    p = Path(path).resolve()
    digest = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return f"{p}#{digest}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_keys.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/keys.py tests/news_collect/test_keys.py
git commit -m "feat: add stable dedup key helpers"
```

---

## Task 4: Per-source state load/save

**Files:**
- Create: `news_collect/state.py`
- Test: `tests/news_collect/test_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_state.py
from news_collect.state import SourceState, load_state, save_state


def test_load_missing_returns_empty(tmp_path):
    st = load_state(tmp_path, "rss")
    assert st.last_run is None
    assert st.seen == set()


def test_save_then_load_roundtrip(tmp_path):
    st = SourceState(last_run="2026-06-14T09:00:00+02:00", seen={"a", "b"})
    save_state(tmp_path, "rss", st)
    back = load_state(tmp_path, "rss")
    assert back.last_run == "2026-06-14T09:00:00+02:00"
    assert back.seen == {"a", "b"}


def test_state_files_are_per_source(tmp_path):
    save_state(tmp_path, "rss", SourceState(last_run="t", seen={"x"}))
    save_state(tmp_path, "zhihu", SourceState(last_run="t", seen={"y"}))
    assert load_state(tmp_path, "rss").seen == {"x"}
    assert load_state(tmp_path, "zhihu").seen == {"y"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.state'`

- [ ] **Step 3: Write `news_collect/state.py`**

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SourceState:
    last_run: str | None = None
    seen: set[str] = field(default_factory=set)


def _state_dir(workspace) -> Path:
    d = Path(workspace) / "news-collect" / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(workspace, source: str) -> Path:
    return _state_dir(workspace) / f"{source}.json"


def load_state(workspace, source: str) -> SourceState:
    p = state_path(workspace, source)
    if not p.exists():
        return SourceState()
    data = json.loads(p.read_text(encoding="utf-8"))
    return SourceState(last_run=data.get("last_run"), seen=set(data.get("seen", [])))


def save_state(workspace, source: str, state: SourceState) -> None:
    p = state_path(workspace, source)
    payload = {"last_run": state.last_run, "seen": sorted(state.seen)}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/state.py tests/news_collect/test_state.py
git commit -m "feat: add per-source state persistence"
```

---

## Task 5: Shared vault writer

**Files:**
- Create: `news_collect/writer.py`
- Test: `tests/news_collect/test_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_writer.py
import yaml

from news_collect.contract import NormalizedDoc
from news_collect.writer import slugify, write_doc


def test_slugify_basic():
    assert slugify("Hello, World! 2026") == "hello-world-2026"


def test_slugify_handles_unicode_and_empty():
    assert slugify("中文标题") != ""
    assert slugify("") == "untitled"


def test_write_doc_creates_file_with_frontmatter(tmp_path):
    doc = NormalizedDoc(
        source="rss", title="My Post", body_md="# Body\n\ntext",
        url="https://example.com/p", published="2026-06-10T00:00:00+00:00",
        extra_frontmatter={"feed": "Example"},
    )
    path = write_doc(tmp_path, doc, collected_at="2026-06-14T09:00:00+02:00")
    assert path.exists()
    assert path.parent == tmp_path / "News" / "rss"
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["source"] == "rss"
    assert fm["title"] == "My Post"
    assert fm["url"] == "https://example.com/p"
    assert fm["collected_at"] == "2026-06-14T09:00:00+02:00"
    assert fm["feed"] == "Example"
    assert "# Body" in text


def test_write_doc_is_stable_for_same_doc(tmp_path):
    doc = NormalizedDoc(source="rss", title="Same", body_md="x", url="https://e.com/a")
    p1 = write_doc(tmp_path, doc, collected_at="t")
    p2 = write_doc(tmp_path, doc, collected_at="t")
    assert p1 == p2  # same filename, overwritten not duplicated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.writer'`

- [ ] **Step 3: Write `news_collect/writer.py`**

```python
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import yaml

from news_collect.contract import NormalizedDoc


def slugify(title: str) -> str:
    """ASCII-friendly slug; falls back to a hash for non-ASCII-only titles."""
    norm = unicodedata.normalize("NFKD", title or "")
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    if slug:
        return slug
    if title.strip():
        return "t-" + hashlib.sha256(title.encode("utf-8")).hexdigest()[:10]
    return "untitled"


def _filename(doc: NormalizedDoc) -> str:
    base = slugify(doc.title)
    # disambiguate with a short hash of the identity (url or title)
    ident = doc.url or doc.title
    suffix = hashlib.sha256(ident.encode("utf-8")).hexdigest()[:8]
    return f"{base}-{suffix}.md"


def write_doc(vault, doc: NormalizedDoc, collected_at: str) -> Path:
    """Write a NormalizedDoc to {vault}/News/{source}/<slug>-<hash>.md. Returns the path."""
    folder = Path(vault) / "News" / doc.source
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _filename(doc)

    frontmatter = {"source": doc.source, "title": doc.title}
    if doc.url:
        frontmatter["url"] = doc.url
    if doc.published:
        frontmatter["published"] = doc.published
    frontmatter["collected_at"] = collected_at
    frontmatter.update(doc.extra_frontmatter)

    fm_yaml = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{fm_yaml}\n---\n\n{doc.body_md}\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_writer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/writer.py tests/news_collect/test_writer.py
git commit -m "feat: add shared vault writer"
```

---

## Task 6: Run-log appender

**Files:**
- Create: `news_collect/runlog.py`
- Test: `tests/news_collect/test_runlog.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_runlog.py
from news_collect.runlog import SourceOutcome, append_runlog


def test_append_creates_file_with_entry(tmp_path):
    log = tmp_path / "run-log.md"
    outcomes = [SourceOutcome("rss", "ok", 3, "fetched 3"),
                SourceOutcome("zhihu", "needs_login", 0, "cookie expired")]
    append_runlog(log, outcomes, now="2026-06-14T09:00:00+02:00")
    text = log.read_text(encoding="utf-8")
    assert "2026-06-14T09:00:00+02:00" in text
    assert "rss" in text and "ok" in text
    assert "zhihu" in text and "needs_login" in text


def test_append_prepends_newest_on_top(tmp_path):
    log = tmp_path / "run-log.md"
    append_runlog(log, [SourceOutcome("rss", "ok", 1, "")], now="2026-06-07T09:00:00+02:00")
    append_runlog(log, [SourceOutcome("rss", "ok", 2, "")], now="2026-06-14T09:00:00+02:00")
    text = log.read_text(encoding="utf-8")
    assert text.index("2026-06-14") < text.index("2026-06-07")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_runlog.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.runlog'`

- [ ] **Step 3: Write `news_collect/runlog.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_HEADER = "# News Collect — Run Log\n\n"


@dataclass
class SourceOutcome:
    source: str
    status: str  # "ok" | "needs_login" | "error"
    count: int
    message: str


def _entry(outcomes: list[SourceOutcome], now: str) -> str:
    lines = [f"## {now}\n", "| Source | Status | New | Detail |", "|---|---|---|---|"]
    for o in outcomes:
        detail = o.message.replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {o.source} | {o.status} | {o.count} | {detail} |")
    return "\n".join(lines) + "\n\n"


def append_runlog(path, outcomes: list[SourceOutcome], now: str) -> None:
    """Prepend a dated entry (newest on top) to the run-log markdown file."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text(encoding="utf-8") if p.exists() else _HEADER
    body = existing[len(_HEADER):] if existing.startswith(_HEADER) else existing
    p.write_text(_HEADER + _entry(outcomes, now) + body, encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_runlog.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/runlog.py tests/news_collect/test_runlog.py
git commit -m "feat: add run-log appender"
```

---

## Task 7: Desktop notification

**Files:**
- Create: `news_collect/notify.py`
- Test: `tests/news_collect/test_notify.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_notify.py
from news_collect.notify import summarize, MacNotifier
from news_collect.runlog import SourceOutcome


def test_summarize_clean_run():
    title, msg = summarize([SourceOutcome("rss", "ok", 5, ""),
                            SourceOutcome("local", "ok", 2, "")])
    assert "7 new" in msg
    assert "OK" in msg or "ok" in msg.lower()


def test_summarize_flags_needs_login():
    title, msg = summarize([SourceOutcome("rss", "ok", 5, ""),
                            SourceOutcome("zhihu", "needs_login", 0, "x")])
    assert "zhihu" in msg
    assert "login" in msg.lower()


def test_mac_notifier_invokes_runner():
    calls = []
    notifier = MacNotifier(runner=lambda args, **kw: calls.append(args))
    notifier.notify("Title", "Body")
    assert calls, "runner was not called"
    assert "osascript" in calls[0][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_notify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.notify'`

- [ ] **Step 3: Write `news_collect/notify.py`**

```python
from __future__ import annotations

import subprocess

from news_collect.runlog import SourceOutcome


def summarize(outcomes: list[SourceOutcome]) -> tuple[str, str]:
    """Build (title, message) for the desktop notification."""
    total_new = sum(o.count for o in outcomes if o.status == "ok")
    problems = [o for o in outcomes if o.status != "ok"]
    if not problems:
        return ("News collect ✓", f"{total_new} new, all sources OK")
    needs = ", ".join(f"{o.source} {o.status.replace('_', ' ')}" for o in problems)
    return ("News collect", f"{total_new} new — {needs}")


class MacNotifier:
    """Fires a macOS notification via osascript. `runner` is injectable for tests."""
    def __init__(self, runner=subprocess.run):
        self._runner = runner

    def notify(self, title: str, message: str) -> None:
        # escape double quotes for AppleScript string literals
        t = title.replace('"', '\\"')
        m = message.replace('"', '\\"')
        script = f'display notification "{m}" with title "{t}"'
        try:
            self._runner(["osascript", "-e", script], check=False)
        except FileNotFoundError:
            pass  # not on macOS / osascript unavailable — non-fatal
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_notify.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/notify.py tests/news_collect/test_notify.py
git commit -m "feat: add desktop notification with summary"
```

---

## Task 8: Ingest routing

**Files:**
- Create: `news_collect/routing.py`
- Test: `tests/news_collect/test_routing.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_routing.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_routing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.routing'`

- [ ] **Step 3: Write `news_collect/routing.py`**

```python
from __future__ import annotations

from urllib.parse import urlsplit

from news_collect.contract import SourceAdapter


def is_local_path(target: str) -> bool:
    return not target.lower().startswith(("http://", "https://"))


def route(target: str, adapters: list[SourceAdapter]) -> SourceAdapter | None:
    """Pick the adapter for an ingest target. Local paths -> the 'local' adapter;
    URLs -> the adapter whose domains match. Returns None if no adapter matches."""
    by_name = {a.name: a for a in adapters}
    if is_local_path(target):
        return by_name.get("local")
    host = urlsplit(target).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    for adapter in adapters:
        for d in adapter.domains:
            if host == d or host.endswith("." + d):
                return adapter
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_routing.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/routing.py tests/news_collect/test_routing.py
git commit -m "feat: add ingest routing"
```

---

## Task 9: Orchestrator — scheduled run loop

**Files:**
- Create: `news_collect/orchestrator.py`
- Test: `tests/news_collect/test_orchestrator_scheduled.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_orchestrator_scheduled.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_orchestrator_scheduled.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.orchestrator'`

- [ ] **Step 3: Write `news_collect/orchestrator.py`**

```python
from __future__ import annotations

from news_collect.contract import SourceAdapter
from news_collect.notify import summarize
from news_collect.runlog import SourceOutcome, append_runlog
from news_collect.state import load_state, save_state


def _fetch_and_record(adapter, items, state, workspace, now, force):
    """Filter seen, fetch, persist state on ok. Returns a SourceOutcome."""
    if not force:
        items = [i for i in items if i.key not in state.seen]
    result = adapter.fetch(items)
    if result.status == "ok":
        state.last_run = now
        state.seen.update(result.keys)
        save_state(workspace, adapter.name, state)
        return SourceOutcome(adapter.name, "ok", len(result.written), result.message)
    return SourceOutcome(adapter.name, result.status, 0, result.message)


def _finish(outcomes, runlog_path, now, notifier):
    append_runlog(runlog_path, outcomes, now)
    title, message = summarize(outcomes)
    notifier.notify(title, message)
    return outcomes


def run_scheduled(adapters, *, selected, fresh, force, dry_run,
                  workspace, vault, now, notifier, runlog_path):
    by_name = {a.name: a for a in adapters}
    outcomes: list[SourceOutcome] = []
    for name in selected:
        adapter = by_name[name]
        state = load_state(workspace, name)
        try:
            items = adapter.discover(state, fresh)
            if not force:
                visible = [i for i in items if i.key not in state.seen]
            else:
                visible = items
            if dry_run:
                outcomes.append(SourceOutcome(name, "ok", len(visible), f"would fetch {len(visible)}"))
                continue
            outcomes.append(_fetch_and_record(adapter, items, state, workspace, now, force))
        except Exception as e:  # fault isolation: one bad source never aborts the run
            outcomes.append(SourceOutcome(name, "error", 0, repr(e)))
    return _finish(outcomes, runlog_path, now, notifier)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_orchestrator_scheduled.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/orchestrator.py tests/news_collect/test_orchestrator_scheduled.py
git commit -m "feat: add scheduled run loop with fault isolation"
```

---

## Task 10: Orchestrator — ingest run

**Files:**
- Modify: `news_collect/orchestrator.py` (add `run_ingest`)
- Test: `tests/news_collect/test_orchestrator_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_orchestrator_ingest.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_orchestrator_ingest.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_ingest'`

- [ ] **Step 3: Add `run_ingest` to `news_collect/orchestrator.py`**

Add this import near the top (with the other imports):

```python
from collections import defaultdict

from news_collect.routing import route
```

Append this function to the module:

```python
def run_ingest(adapters, targets, *, force, dry_run,
               workspace, vault, now, notifier, runlog_path):
    by_name = {a.name: a for a in adapters}
    grouped: dict[str, list[str]] = defaultdict(list)
    outcomes: list[SourceOutcome] = []
    for t in targets:
        adapter = route(t, adapters)
        if adapter is None:
            outcomes.append(SourceOutcome("(none)", "error", 0, f"no adapter for {t}"))
        else:
            grouped[adapter.name].append(t)

    for name, ts in grouped.items():
        adapter = by_name[name]
        state = load_state(workspace, name)
        try:
            items = adapter.refs_for(ts)
            if not force:
                items = [i for i in items if i.key not in state.seen]
            if dry_run:
                outcomes.append(SourceOutcome(name, "ok", len(items), f"would fetch {len(items)}"))
                continue
            outcomes.append(_fetch_and_record(adapter, items, state, workspace, now, force=True))
        except Exception as e:
            outcomes.append(SourceOutcome(name, "error", 0, repr(e)))
    return _finish(outcomes, runlog_path, now, notifier)
```

Note: `_fetch_and_record` is called with `force=True` here because the seen-filter has
already been applied above (ingest dedups before building the fetch list, so we must not
filter twice).

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_orchestrator_ingest.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/orchestrator.py tests/news_collect/test_orchestrator_ingest.py
git commit -m "feat: add ingest run with domain routing"
```

---

## Task 11: Config loader

**Files:**
- Create: `news_collect/config.py`
- Create: `news_collect/config.toml` (sample/default config)
- Test: `tests/news_collect/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_config.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.config'`

- [ ] **Step 3: Write `news_collect/config.py`**

```python
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    vault: str
    sources: dict

    def enabled_sources(self) -> list[str]:
        return [name for name, s in self.sources.items() if s.get("enabled")]

    def source(self, name: str) -> dict:
        return self.sources.get(name, {})


def load_config(path) -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    vault = data.get("vault") or os.environ.get("OBSIDIAN_VAULT", "")
    return Config(vault=vault, sources=data.get("sources", {}))
```

- [ ] **Step 4: Write `news_collect/config.toml` (sample defaults)**

```toml
# News Collect configuration.
# vault: absolute path to the Obsidian vault. If omitted, OBSIDIAN_VAULT env var is used.
vault = ""

[sources.rss]
enabled = true
feeds = [
    # "https://example.com/feed.xml",
]

[sources.zhihu]
enabled = true
profile = ""                               # https://www.zhihu.com/people/<slug>
start = "2026-01-01T00:00:00+01:00"        # discovery lower bound on first run

[sources.local]
enabled = false
paths = [
    # "/Users/you/notes/clippings",
]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add news_collect/config.py news_collect/config.toml tests/news_collect/test_config.py
git commit -m "feat: add config loader and sample config"
```

---

## Task 12: RSS adapter

**Files:**
- Create: `news_collect/adapters/rss.py`
- Create: `tests/news_collect/fixtures/sample_feed.xml`
- Test: `tests/news_collect/test_rss_adapter.py`

- [ ] **Step 1: Write the fixture `tests/news_collect/fixtures/sample_feed.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First Post</title>
      <link>https://example.com/first</link>
      <guid>https://example.com/first</guid>
      <pubDate>Mon, 09 Jun 2026 12:00:00 +0000</pubDate>
      <description><![CDATA[<p>Hello <b>world</b></p>]]></description>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.com/second</link>
      <guid>https://example.com/second</guid>
      <pubDate>Tue, 10 Jun 2026 12:00:00 +0000</pubDate>
      <description><![CDATA[<p>Another <i>entry</i></p>]]></description>
    </item>
  </channel>
</rss>
```

- [ ] **Step 2: Write the failing test**

```python
# tests/news_collect/test_rss_adapter.py
from pathlib import Path

import yaml

from news_collect.adapters.rss import RssAdapter
from news_collect.state import SourceState

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


def test_discover_returns_entries_with_url_keys(tmp_path):
    adapter = RssAdapter(feeds=[FIXTURE.as_uri()], vault=tmp_path / "vault",
                         now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    keys = {r.key for r in refs}
    assert "https://example.com/first" in keys
    assert "https://example.com/second" in keys
    assert all(r.source == "rss" for r in refs)


def test_fetch_writes_markdown_with_converted_body(tmp_path):
    vault = tmp_path / "vault"
    adapter = RssAdapter(feeds=[FIXTURE.as_uri()], vault=vault, now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    result = adapter.fetch(refs)
    assert result.status == "ok"
    assert len(result.written) == 2
    files = list((vault / "News" / "rss").glob("*.md"))
    assert len(files) == 2
    text = (files[0]).read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["source"] == "rss"
    # markdownify converts <b>/<i> to markdown emphasis
    assert "**" in text or "*" in text
```

- [ ] **Step 3: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_rss_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.adapters.rss'`

- [ ] **Step 4: Write `news_collect/adapters/rss.py`**

```python
from __future__ import annotations

import feedparser
from markdownify import markdownify as md

from news_collect.contract import SourceAdapter, ItemRef, FetchResult, NormalizedDoc
from news_collect.keys import url_key
from news_collect.writer import write_doc


class RssAdapter(SourceAdapter):
    name = "rss"
    domains: list[str] = []  # ingest routing for arbitrary blogs is handled by the blogs adapter (deferred)

    def __init__(self, feeds, vault, now: str):
        self.feeds = feeds
        self.vault = vault
        self.now = now
        self._entries: dict[str, dict] = {}  # key -> entry detail, populated by discover()

    def discover(self, state, fresh: bool) -> list[ItemRef]:
        refs: list[ItemRef] = []
        for feed_url in self.feeds:
            parsed = feedparser.parse(feed_url)
            feed_title = parsed.feed.get("title", "")
            for e in parsed.entries:
                link = e.get("link") or e.get("id")
                if not link:
                    continue
                key = url_key(link)
                self._entries[key] = {"entry": e, "feed_title": feed_title, "link": link}
                refs.append(ItemRef(key=key, source=self.name, url=link, title=e.get("title")))
        return refs

    def _body_html(self, entry) -> str:
        if entry.get("content"):
            return entry["content"][0].get("value", "")
        return entry.get("summary", "")

    def fetch(self, items: list[ItemRef]) -> FetchResult:
        written: list[ItemRef] = []
        for ref in items:
            detail = self._entries.get(ref.key)
            if detail is None:
                # ingest path: entry not pre-loaded; fetch the single feed item is out of
                # scope, so skip with no write (counts as not-written).
                continue
            e = detail["entry"]
            doc = NormalizedDoc(
                source=self.name,
                title=e.get("title", "(untitled)"),
                body_md=md(self._body_html(e)).strip(),
                url=detail["link"],
                published=e.get("published"),
                extra_frontmatter={"feed": detail["feed_title"]},
            )
            write_doc(self.vault, doc, collected_at=self.now)
            written.append(ref)
        return FetchResult(status="ok", written=written)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_rss_adapter.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add news_collect/adapters/rss.py tests/news_collect/test_rss_adapter.py tests/news_collect/fixtures/sample_feed.xml
git commit -m "feat: add RSS adapter"
```

---

## Task 13: Local markdown adapter

**Files:**
- Create: `news_collect/adapters/local.py`
- Test: `tests/news_collect/test_local_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_local_adapter.py
import yaml

from news_collect.adapters.local import LocalAdapter
from news_collect.state import SourceState


def _make_notes(tmp_path):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "a.md").write_text("# A\n\nalpha", encoding="utf-8")
    (notes / "b.md").write_text("# B\n\nbeta", encoding="utf-8")
    return notes


def test_discover_finds_markdown_with_path_hash_keys(tmp_path):
    notes = _make_notes(tmp_path)
    adapter = LocalAdapter(paths=[str(notes)], vault=tmp_path / "vault", now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    assert len(refs) == 2
    assert all("#" in r.key for r in refs)
    assert all(r.source == "local" for r in refs)


def test_fetch_writes_files_to_vault(tmp_path):
    notes = _make_notes(tmp_path)
    vault = tmp_path / "vault"
    adapter = LocalAdapter(paths=[str(notes)], vault=vault, now="2026-06-14T09:00:00+02:00")
    refs = adapter.discover(SourceState(), fresh=False)
    result = adapter.fetch(refs)
    assert result.status == "ok"
    out = list((vault / "News" / "local").glob("*.md"))
    assert len(out) == 2
    text = out[0].read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert fm["source"] == "local"
    assert "source_path" in fm


def test_refs_for_expands_dirs_for_ingest(tmp_path):
    notes = _make_notes(tmp_path)
    adapter = LocalAdapter(paths=[], vault=tmp_path / "vault", now="t")
    refs = adapter.refs_for([str(notes)])
    assert len(refs) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_local_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.adapters.local'`

- [ ] **Step 3: Write `news_collect/adapters/local.py`**

```python
from __future__ import annotations

from pathlib import Path

from news_collect.contract import SourceAdapter, ItemRef, FetchResult, NormalizedDoc
from news_collect.keys import file_key
from news_collect.writer import write_doc


class LocalAdapter(SourceAdapter):
    name = "local"
    domains: list[str] = []

    def __init__(self, paths, vault, now: str):
        self.paths = paths
        self.vault = vault
        self.now = now

    def _iter_md(self, roots) -> list[Path]:
        files: list[Path] = []
        for root in roots:
            p = Path(root).expanduser()
            if p.is_dir():
                files.extend(sorted(p.rglob("*.md")))
            elif p.is_file() and p.suffix == ".md":
                files.append(p)
        return files

    def _refs(self, files) -> list[ItemRef]:
        return [ItemRef(key=file_key(f), source=self.name, path=str(Path(f).resolve()),
                        title=f.stem) for f in files]

    def discover(self, state, fresh: bool) -> list[ItemRef]:
        return self._refs(self._iter_md(self.paths))

    def refs_for(self, targets: list[str]) -> list[ItemRef]:
        return self._refs(self._iter_md(targets))

    def fetch(self, items: list[ItemRef]) -> FetchResult:
        written: list[ItemRef] = []
        for ref in items:
            src = Path(ref.path)
            doc = NormalizedDoc(
                source=self.name,
                title=ref.title or src.stem,
                body_md=src.read_text(encoding="utf-8"),
                extra_frontmatter={"source_path": str(src)},
            )
            write_doc(self.vault, doc, collected_at=self.now)
            written.append(ref)
        return FetchResult(status="ok", written=written)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_local_adapter.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/adapters/local.py tests/news_collect/test_local_adapter.py
git commit -m "feat: add local markdown adapter"
```

---

## Task 14: Zhihu adapter (wraps existing scripts)

**Files:**
- Create: `news_collect/adapters/zhihu.py`
- Test: `tests/news_collect/test_zhihu_adapter.py`

The Zhihu adapter shells out to the existing pipeline. To keep it testable, all subprocess
calls go through an injectable `runner` and the steps are sequenced in one private method.
`discover` returns a single sentinel ItemRef representing "the whole incremental window"
(Zhihu's own scripts compute the actual new items and resume via `_progress.json`); `fetch`
runs the four-stage pipeline and maps the outcome to a status.

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_zhihu_adapter.py
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
        # Simulate the history script printing a security-check marker on stderr.
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
    # pipeline must stop after the failing history stage
    stages = [" ".join(c) for c in runner.calls]
    assert not any("write_to_obsidian" in s for s in stages)


def test_fetch_batch_failure_is_error(tmp_path):
    runner = FakeRunner(fail=True)
    adapter = ZhihuAdapter(profile="https://www.zhihu.com/people/x", start="2026-01-01T00:00:00+01:00",
                           vault="/v", workspace=tmp_path, now="2026-06-14T09:00:00+02:00",
                           skill_dir="/skill", runner=runner)
    result = adapter.fetch(adapter.discover(SourceState(), fresh=False))
    assert result.status == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_zhihu_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.adapters.zhihu'`

- [ ] **Step 3: Write `news_collect/adapters/zhihu.py`**

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from news_collect.contract import SourceAdapter, ItemRef, FetchResult

# Return code the Zhihu scripts use to signal a security-check / cookie-expiry condition.
NEEDS_LOGIN_RC = 2


class ZhihuAdapter(SourceAdapter):
    name = "zhihu"
    domains = ["zhihu.com", "zhuanlan.zhihu.com"]

    def __init__(self, profile, start, vault, workspace, now, skill_dir, runner=subprocess.run):
        self.profile = profile
        self.start = start
        self.vault = vault
        self.workspace = Path(workspace)
        self.now = now
        self.skill_dir = skill_dir
        self._runner = runner

    def discover(self, state, fresh: bool) -> list[ItemRef]:
        # Zhihu's own scripts compute the incremental window and resume via _progress.json,
        # so we represent the whole window as a single work item keyed by run timestamp.
        since = state.last_run or self.start
        return [ItemRef(key=f"zhihu-window:{since}", source=self.name,
                        url=self.profile, title=f"Zhihu activity since {since}")]

    def _script(self, name: str) -> str:
        return str(Path(self.skill_dir) / "scripts" / name)

    def fetch(self, items: list[ItemRef]) -> FetchResult:
        if not items:
            return FetchResult(status="ok", written=[])
        work = self.workspace / "news-collect" / "zhihu"
        work.mkdir(parents=True, exist_ok=True)
        list_json = str(work / "history.json")
        articles_dir = str(work / "articles")

        history = ["python", self._script("fetch_zhihu_history.py"),
                   self.profile, self.start, list_json]
        r = self._runner(history, cwd=self.skill_dir)
        if r.returncode == NEEDS_LOGIN_RC:
            return FetchResult(status="needs_login",
                               message="Zhihu security check / cookie expired. "
                                       "Run scripts/zhihu_relogin.py, then: collect.py --only zhihu")
        if r.returncode != 0:
            return FetchResult(status="error", message="fetch_zhihu_history failed")

        for cmd in (
            ["python", self._script("fetch_zhihu_batch.py"), list_json, articles_dir],
            ["python", self._script("format_articles.py"), articles_dir, "--set-times"],
            ["python", self._script("write_to_obsidian.py"), articles_dir, self.vault,
             "--root-folder", "News/zhihu"],
        ):
            r = self._runner(cmd, cwd=self.skill_dir)
            if r.returncode != 0:
                return FetchResult(status="error", message=f"{cmd[1]} failed")

        return FetchResult(status="ok", written=items)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_zhihu_adapter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add news_collect/adapters/zhihu.py tests/news_collect/test_zhihu_adapter.py
git commit -m "feat: add Zhihu adapter wrapping existing scripts"
```

---

## Task 15: CLI entry point

**Files:**
- Create: `news_collect/collect.py`
- Test: `tests/news_collect/test_collect_cli.py`

The CLI parses args, builds adapters from config, resolves the selected source list
(`--only`/`--skip`), and dispatches to `run_scheduled` or `run_ingest`. We test the pure
helpers (`select_sources`, `build_adapters`) directly rather than spawning a subprocess.

- [ ] **Step 1: Write the failing test**

```python
# tests/news_collect/test_collect_cli.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/news_collect/test_collect_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'news_collect.collect'`

- [ ] **Step 3: Write `news_collect/collect.py`**

```python
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from news_collect.adapters.local import LocalAdapter
from news_collect.adapters.rss import RssAdapter
from news_collect.adapters.zhihu import ZhihuAdapter
from news_collect.config import load_config, Config
from news_collect.notify import MacNotifier
from news_collect.orchestrator import run_scheduled, run_ingest

DEFAULT_CONFIG = Path(__file__).with_name("config.toml")


def select_sources(enabled: list[str], only: str | None, skip: str | None) -> list[str]:
    if only:
        wanted = [s.strip() for s in only.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in enabled]
        if unknown:
            raise ValueError(f"--only names unknown/disabled sources: {unknown}")
        return wanted
    if skip:
        dropped = {s.strip() for s in skip.split(",")}
        return [s for s in enabled if s not in dropped]
    return list(enabled)


def build_adapters(cfg: Config, *, workspace, now: str, skill_dir: str):
    adapters = []
    for name in cfg.enabled_sources():
        s = cfg.source(name)
        if name == "rss":
            adapters.append(RssAdapter(feeds=s.get("feeds", []), vault=cfg.vault, now=now))
        elif name == "local":
            adapters.append(LocalAdapter(paths=s.get("paths", []), vault=cfg.vault, now=now))
        elif name == "zhihu":
            adapters.append(ZhihuAdapter(profile=s.get("profile", ""), start=s.get("start", ""),
                                         vault=cfg.vault, workspace=workspace, now=now,
                                         skill_dir=skill_dir))
    return adapters


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="collect.py", description="Multi-source news collector")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--only")
    parser.add_argument("--skip")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    sub = parser.add_subparsers(dest="cmd")
    ing = sub.add_parser("ingest", help="ingest explicit URLs or local paths")
    ing.add_argument("targets", nargs="*")
    ing.add_argument("--from", dest="from_file")
    args = parser.parse_args(argv)

    skill_dir = os.environ.get("CLAUDE_SKILL_DIR", str(Path(__file__).resolve().parents[1]))
    workspace = os.environ.get("OPENCLAW_WORKSPACE", str(Path.home() / ".openclaw" / "workspace"))
    now = _now_iso()

    cfg = load_config(args.config)
    if not cfg.vault:
        print("error: no vault configured (set 'vault' in config.toml or OBSIDIAN_VAULT)", file=sys.stderr)
        return 2

    adapters = build_adapters(cfg, workspace=workspace, now=now, skill_dir=skill_dir)
    runlog_path = Path(cfg.vault) / "News" / "run-log.md"
    notifier = MacNotifier()
    ctx = dict(workspace=workspace, vault=cfg.vault, now=now,
               notifier=notifier, runlog_path=runlog_path)

    if args.cmd == "ingest":
        targets = list(args.targets)
        if args.from_file:
            targets += [ln.strip() for ln in Path(args.from_file).read_text().splitlines() if ln.strip()]
        run_ingest(adapters, targets, force=args.force, dry_run=args.dry_run, **ctx)
        return 0

    selected = select_sources([a.name for a in adapters], args.only, args.skip)
    run_scheduled(adapters, selected=selected, fresh=args.fresh, force=args.force,
                  dry_run=args.dry_run, **ctx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/news_collect/test_collect_cli.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full suite**

Run: `venv/bin/pytest -q`
Expected: all tests pass (PASS across every test_*.py).

- [ ] **Step 6: Smoke-check the CLI wiring with `--dry-run`**

Run: `OBSIDIAN_VAULT=/tmp/vault venv/bin/python news_collect/collect.py --dry-run --config news_collect/config.toml`
Expected: exits 0. With the sample config (rss enabled but no feeds, zhihu enabled but no
profile), `--dry-run` discovers nothing to fetch, writes a run-log entry under
`/tmp/vault/News/`, and never calls any adapter's `fetch`. This is a wiring sanity check —
real verification is the pytest suite in Step 5.

- [ ] **Step 7: Commit**

```bash
git add news_collect/collect.py tests/news_collect/test_collect_cli.py
git commit -m "feat: add collect.py CLI entry point"
```

---

## Task 16: launchd plist template and documentation

**Files:**
- Create: `deploy/com.kunwu.news-collect.plist.template`
- Create: `news_collect/README.md`

- [ ] **Step 1: Write `deploy/com.kunwu.news-collect.plist.template`**

Placeholders `__REPO__`, `__WORKSPACE__`, `__VAULT__` are filled in at install time.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.kunwu.news-collect</string>

    <key>ProgramArguments</key>
    <array>
        <string>__REPO__/venv/bin/python</string>
        <string>__REPO__/news_collect/collect.py</string>
    </array>

    <key>EnvironmentVariables</key>
    <dict>
        <key>OPENCLAW_WORKSPACE</key>
        <string>__WORKSPACE__</string>
        <key>OBSIDIAN_VAULT</key>
        <string>__VAULT__</string>
        <key>CLAUDE_SKILL_DIR</key>
        <string>__REPO__</string>
    </dict>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>5</integer>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>__WORKSPACE__/news-collect/logs/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>__WORKSPACE__/news-collect/logs/launchd.err.log</string>
</dict>
</plist>
```

- [ ] **Step 2: Write `news_collect/README.md`**

````markdown
# News Collect

Deterministic multi-source content collector. Pulls new content from configured sources into
`{Vault}/News/{source}/`, incremental and idempotent, with desktop notifications and a
`run-log.md`. See the design spec at `docs/superpowers/specs/2026-06-14-news-collect-agent-design.md`.

## Setup

```bash
venv/bin/pip install -r news_collect/requirements.txt
cp news_collect/config.toml news_collect/config.local.toml   # edit: vault, feeds, zhihu profile
```

Edit `config.toml` (or pass `--config`): set `vault`, RSS `feeds`, the Zhihu `profile`/`start`,
and `local` `paths`. Enable/disable each source with `enabled = true/false`.

## Usage

```bash
# Weekly full run (all enabled sources, incremental)
venv/bin/python news_collect/collect.py

# Subset control
venv/bin/python news_collect/collect.py --skip zhihu
venv/bin/python news_collect/collect.py --only rss,local
venv/bin/python news_collect/collect.py --fresh --only zhihu   # re-pull, ignore state

# Preview without writing
venv/bin/python news_collect/collect.py --dry-run

# On-demand ingest (URLs route by domain; local paths handled by the local adapter)
venv/bin/python news_collect/collect.py ingest https://www.zhihu.com/p/123
venv/bin/python news_collect/collect.py ingest ~/notes/clippings/
venv/bin/python news_collect/collect.py ingest --from urls.txt
# --force re-imports already-seen items
```

When Zhihu reports `needs_login`, the run-log and notification tell you to run
`scripts/zhihu_relogin.py`, then re-run `collect.py --only zhihu` — it resumes from checkpoint.

## Weekly schedule (launchd, Friday 09:00 local)

```bash
REPO="$(pwd)"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
VAULT="/absolute/path/to/your/Obsidian/Vault"
mkdir -p "$WORKSPACE/news-collect/logs"
sed -e "s#__REPO__#$REPO#g" -e "s#__WORKSPACE__#$WORKSPACE#g" -e "s#__VAULT__#$VAULT#g" \
    deploy/com.kunwu.news-collect.plist.template \
    > ~/Library/LaunchAgents/com.kunwu.news-collect.plist
launchctl load ~/Library/LaunchAgents/com.kunwu.news-collect.plist
```

Manage:

```bash
launchctl start com.kunwu.news-collect    # run now (manual smoke test)
launchctl unload ~/Library/LaunchAgents/com.kunwu.news-collect.plist   # disable
```

## Manual smoke test

1. `launchctl start com.kunwu.news-collect`
2. Confirm a new dated entry appears in `{Vault}/News/run-log.md`.
3. Confirm a desktop notification fired.
4. If anything failed, check `{Workspace}/news-collect/logs/launchd.err.log`.

## Adding a source later

Implement a `SourceAdapter` subclass in `news_collect/adapters/`, register it in
`build_adapters()` in `collect.py`, and add a `[sources.<name>]` block to `config.toml`.
Deferred adapters: **blogs** (readability; also the route for unknown-domain ingest URLs) and
**xiaohongshu**.
````

- [ ] **Step 3: Verify the plist template renders with sample substitution**

Run: `sed -e 's#__REPO__#/tmp/repo#g' -e 's#__WORKSPACE__#/tmp/ws#g' -e 's#__VAULT__#/tmp/v#g' deploy/com.kunwu.news-collect.plist.template | plutil -lint -`
Expected: `... OK` (valid plist).

- [ ] **Step 4: Commit**

```bash
git add deploy/com.kunwu.news-collect.plist.template news_collect/README.md
git commit -m "feat: add launchd plist template and README"
```

---

## Final verification

- [ ] **Run the complete test suite**

Run: `venv/bin/pytest -q`
Expected: every test passes.

- [ ] **Confirm no source file has placeholders or unfinished sections**

Run: `grep -rn "TODO\|TBD\|FIXME" news_collect/ deploy/ || echo "clean"`
Expected: `clean`

---

## Deferred (not in this plan — additive follow-ups)

- **blogs adapter** — readability extraction; becomes the default route for unknown-domain
  ingest URLs (today they're reported as errors).
- **xiaohongshu adapter** — aggressive anti-scraping; its own effort, mirrors the Zhihu
  needs-login pattern.
- **Image localization for RSS** — v1 keeps remote image URLs in the body; downloading and
  rewriting to local copies is a follow-up.
