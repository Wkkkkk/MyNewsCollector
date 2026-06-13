import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import zhihu_obsidian_config as cfg


class ResolveRootFolder(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("ZHIHU_OBSIDIAN_ROOT", "ZHIHU_FAILURES_FILE")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_default_root_is_english(self):
        self.assertEqual(cfg.resolve_root_folder(), "Zhihu Collection")

    def test_default_failures_is_english(self):
        self.assertEqual(cfg.resolve_failures_name(), "fetch-failures.md")

    def test_env_overrides_default(self):
        os.environ["ZHIHU_OBSIDIAN_ROOT"] = "知乎收藏"
        self.assertEqual(cfg.resolve_root_folder(), "知乎收藏")

    def test_cli_overrides_env(self):
        os.environ["ZHIHU_OBSIDIAN_ROOT"] = "知乎收藏"
        self.assertEqual(cfg.resolve_root_folder("Custom"), "Custom")

    def test_blank_env_falls_back_to_default(self):
        os.environ["ZHIHU_OBSIDIAN_ROOT"] = "   "
        self.assertEqual(cfg.resolve_root_folder(), "Zhihu Collection")


if __name__ == "__main__":
    unittest.main()
