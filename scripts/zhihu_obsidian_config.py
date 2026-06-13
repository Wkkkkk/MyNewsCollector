"""Resolve configurable Obsidian output names (CLI flag > env var > English default).

Defaults are English as of skill v1.4.0. Users with an existing Chinese vault can keep the
old names with: ZHIHU_OBSIDIAN_ROOT=知乎收藏 ZHIHU_FAILURES_FILE=抓取失败.md
"""

import os

DEFAULT_ROOT_FOLDER = "Zhihu Collection"
DEFAULT_FAILURES_NAME = "fetch-failures.md"

ENV_ROOT_FOLDER = "ZHIHU_OBSIDIAN_ROOT"
ENV_FAILURES_NAME = "ZHIHU_FAILURES_FILE"


def resolve_root_folder(cli_value=None):
    if cli_value and cli_value.strip():
        return cli_value
    env = os.environ.get(ENV_ROOT_FOLDER, "").strip()
    return env or DEFAULT_ROOT_FOLDER


def resolve_failures_name(cli_value=None):
    if cli_value and cli_value.strip():
        return cli_value
    env = os.environ.get(ENV_FAILURES_NAME, "").strip()
    return env or DEFAULT_FAILURES_NAME
