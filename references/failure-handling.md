# 失败处理策略（`fetch_zhihu_batch.py`）

批量抓取脚本采用**两级失败处理**，区分「文章本身问题」和「环境问题」：

| 场景 | 行为 | 说明 |
|------|------|------|
| 散发失败（中间有成功） | 记录到 `_progress.json` 的 `failed` 字段 | 视为文章本身问题（已删除/不可访问），后续跳过 |
| 连续失败 ≥ 5 次 | 中断抓取，**丢弃**缓存的失败记录 | 视为环境问题（Cookie/网络），下次重试仍可跑 |

## 工作原理

- 失败先缓存在内存中，不立即写入进度文件
- 下一条成功时，将缓存的失败记录批量写入进度文件（确认是文章问题）
- 连续失败达到阈值（5 次）时，中断抓取，丢弃缓存（保留重试机会）

失败记录包含 `url` / `reason` / `title` / `timestamp`，方便人工排查。

**相关常量（脚本内）：**

- `CONSECUTIVE_FAIL_THRESHOLD = 5`：连续失败阈值
- `CONSECUTIVE_FAIL_INTERRUPT = True`：是否在连续失败时中断

## 重试模式

```bash
python fetch_zhihu_batch.py <列表文件> [输出目录] [图片目录] --retry-failed
```

此模式会清空 `failed` 列表，只重试之前记录为失败的文章。

## 失败项清单（写入 Obsidian）

```bash
python "${CLAUDE_SKILL_DIR}/scripts/write_zhihu_failures.py" <Vault路径> <标签>:<progress.json> ...
```

生成 `{Vault}/知乎收藏/抓取失败.md`，方便人工逐条重试。
