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
