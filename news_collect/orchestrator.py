from __future__ import annotations

from news_collect.contract import SourceAdapter
from news_collect.notify import summarize
from news_collect.runlog import SourceOutcome, append_runlog
from news_collect.state import load_state, save_state


def _fetch_and_record(adapter, items, state, workspace, now):
    """Fetch the given items and persist state on ok. Returns a SourceOutcome.

    Callers are the single owner of the seen-filter: `items` must already be the
    list to fetch (filtered, or not, by the caller).
    """
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
    # `vault` is reserved for symmetry with run_ingest; adapters own their write path.
    by_name = {a.name: a for a in adapters}
    outcomes: list[SourceOutcome] = []
    for name in selected:
        adapter = by_name[name]
        state = load_state(workspace, name)
        try:
            items = adapter.discover(state, fresh)
            # The loop is the single owner of the seen-filter.
            visible = items if force else [i for i in items if i.key not in state.seen]
            if dry_run:
                outcomes.append(SourceOutcome(name, "ok", len(visible), f"would fetch {len(visible)}"))
                continue
            outcomes.append(_fetch_and_record(adapter, visible, state, workspace, now))
        except Exception as e:  # fault isolation: one bad source never aborts the run
            outcomes.append(SourceOutcome(name, "error", 0, repr(e)))
    return _finish(outcomes, runlog_path, now, notifier)
