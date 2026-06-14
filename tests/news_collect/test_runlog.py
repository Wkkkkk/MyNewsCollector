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
