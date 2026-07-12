from news_collect.notify import summarize, should_notify, MacNotifier
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
    assert "terminal-notifier" in calls[0][0]
    assert "Title" in calls[0] and "Body" in calls[0]


def test_mac_notifier_click_opens_target():
    calls = []
    notifier = MacNotifier(open_url="obsidian://open?path=/v/News/run-log.md",
                           runner=lambda args, **kw: calls.append(args))
    notifier.notify("T", "B")
    argv = calls[0]
    assert "-execute" in argv
    assert argv[argv.index("-execute") + 1].startswith("open ")
    assert "run-log.md" in argv[argv.index("-execute") + 1]


def test_should_notify_false_on_empty_clean_run():
    assert should_notify([SourceOutcome("rss", "ok", 0, ""),
                          SourceOutcome("local", "ok", 0, "")]) is False


def test_should_notify_true_when_new_items():
    assert should_notify([SourceOutcome("rss", "ok", 3, "")]) is True


def test_should_notify_true_on_problem_even_with_zero_new():
    assert should_notify([SourceOutcome("rss", "ok", 0, ""),
                          SourceOutcome("zhihu", "needs_login", 0, "x")]) is True
