from __future__ import annotations

import shlex
import subprocess

from news_collect.runlog import SourceOutcome, outcome_stats

TERMINAL_NOTIFIER = "/usr/local/bin/terminal-notifier"


def summarize(outcomes: list[SourceOutcome]) -> tuple[str, str]:
    """Build (title, message) for the desktop notification."""
    total_new = sum(o.count for o in outcomes if o.status == "ok")
    problems = [o for o in outcomes if o.status != "ok"]
    if not problems:
        return ("News collect ✓", f"{total_new} new, all sources OK")
    needs = ", ".join(f"{o.source} {o.status.replace('_', ' ')}" for o in problems)
    return ("News collect", f"{total_new} new — {needs}")


def should_notify(outcomes: list[SourceOutcome]) -> bool:
    """Notify only when there is something to say: new items were produced, or
    at least one source had a problem. A clean run that produced 0 new items is
    silent (the caller exits 44 — see collect._scheduled_exit_code)."""
    total_new, problems = outcome_stats(outcomes)
    return total_new > 0 or problems


class MacNotifier:
    """Fires a clickable macOS notification via terminal-notifier. Clicking opens
    `open_url` (a file path, file:// URL, or obsidian:// URL) — used to jump to the
    freshly-collected notes. `runner` is injectable for tests."""
    def __init__(self, open_url: str | None = None, runner=subprocess.run):
        self._open_url = open_url
        self._runner = runner

    def notify(self, title: str, message: str) -> None:
        # terminal-notifier takes title/message as argv, so no AppleScript string
        # escaping is needed. A click runs `open <url>` when open_url is set.
        cmd = [TERMINAL_NOTIFIER, "-title", title, "-message", message,
               "-group", "news-collect"]
        if self._open_url:
            cmd += ["-execute", f"open {shlex.quote(self._open_url)}"]
        try:
            self._runner(cmd, check=False)
        except FileNotFoundError:
            pass  # terminal-notifier not installed — non-fatal
