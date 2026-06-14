from __future__ import annotations

import subprocess
import sys
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
        # `now` is accepted for a uniform adapter constructor signature; the underlying
        # Zhihu scripts stamp their own timestamps (format_articles --set-times), so this
        # adapter does not use it directly.
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

        history = [sys.executable, self._script("fetch_zhihu_history.py"),
                   self.profile, self.start, list_json]
        r = self._runner(history, cwd=self.skill_dir)
        if r.returncode == NEEDS_LOGIN_RC:
            return FetchResult(status="needs_login",
                               message="Zhihu security check / cookie expired. "
                                       "Run scripts/zhihu_relogin.py, then: collect.py --only zhihu")
        if r.returncode != 0:
            return FetchResult(status="error", message="fetch_zhihu_history failed")

        for cmd in (
            [sys.executable, self._script("fetch_zhihu_batch.py"), list_json, articles_dir],
            [sys.executable, self._script("format_articles.py"), articles_dir, "--set-times"],
            [sys.executable, self._script("write_to_obsidian.py"), articles_dir, self.vault,
             "--root-folder", "News/zhihu"],
        ):
            r = self._runner(cmd, cwd=self.skill_dir)
            if r.returncode != 0:
                return FetchResult(status="error", message=f"{cmd[1]} failed")

        return FetchResult(status="ok", written=items)
