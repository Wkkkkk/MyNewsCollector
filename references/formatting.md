# 保守格式化（`format_articles.py`）

对已抓取的 Markdown 做**保守**清理 —— 只修复导出瑕疵，不重排正文。可传入目录（递归处理 `*.md`）或单个文件：

```bash
python "${CLAUDE_SKILL_DIR}/scripts/format_articles.py" <文章目录或.md文件...> \
  [--dry-run] [--diff] [--set-times] [--time-field interaction_time] [--no-created-time]
```

## 修复内容

- **多行行内代码 → 围栏代码块**：导出时被压成单个反引号包裹的多行代码恢复为 ``` 围栏，并按内容推断语言标注（cpp/go/python/rust/sql/json/bash/javascript/yaml）
- **链接卡片恢复**：知乎卡片式链接（图片+标题整体包在一个链接里）拆为「图片 + 标题链接」两段
- **塌缩链接列表恢复**：被压成一段的 4+ 链接列表恢复为 `## Links`（或 `## RSS Sources`）下的无序列表
- **重定向解码**：`link.zhihu.com/?target=...` 还原为真实 URL；`zhida.zhihu.com` 实体链接不作为来源链接
- **参考文献区**：`**参考**` / `**References**` 等加粗标题转为 `## ` 标题，区内链接解码重定向
- **空行规范化**：标题/列表/引用/图片/代码块前后补空行，压缩连续空行，代码块内容不动

## 文件时间同步（可选）

`--set-times` 按 frontmatter 字段（默认 `interaction_time`，可用 `--time-field` 改）设置文件的访问/修改时间；macOS 上若有 `SetFile` 还会同步创建时间（`--no-created-time` 跳过）。适合让 Obsidian/Finder 中的文件时间反映实际互动时间。

## 安全性

- **幂等**：重复运行结果不变
- 不动 frontmatter 内容；代码围栏内不处理
- 建议首次先 `--dry-run --diff` 预览
- 结束时输出 `scanned=… changed=…` 摘要
