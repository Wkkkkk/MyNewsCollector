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
