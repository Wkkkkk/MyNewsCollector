# Cookie 登录、保活与恢复

本文件说明登录脚本的使用方式与批量抓取脚本内置的 Cookie 保活机制。Cookie 默认持久化在 `{workspace}/zhihu_cookies.json`（见 [paths.md](paths.md)）。

## 登录脚本

### `zhihu_login.py` — 首次登录辅助

打开浏览器等待用户登录，默认以检测到 **`z_c0`** Cookie 为成功条件即可结束（不要求额外跳转）。

**可选二次校验**：若用户希望登录后再确认「某一内需登录页」是否可访问（如某收藏夹页、专栏后台、关注动态等），属可选项，不设则不执行：

- **环境变量 `ZHIHU_VERIFY_URL`**：值为完整 `http://` 或 `https://` URL；
- **或**命令行第一个参数传入同一完整 URL：

  ```bash
  python "${CLAUDE_SKILL_DIR}/scripts/zhihu_login.py" "https://www.zhihu.com/..."
  ```

脚本会访问该 URL，若正文仍出现知乎通用提示「请登录后查看」，则提示可能未登录完成；否则认为当前会话可访问该页。不限定于收藏夹，任意知乎链接均可（只要登录态相关）。

### `zhihu_relogin.py` — 重新登录

Cookie 失效、需重新登录并写回 `zhihu_cookies.json` 时使用（会打开浏览器窗口）。

### `zhihu_login_save.py` — 登录并保存

按需配合 Cookie 流程使用。

## Cookie 保活机制（`fetch_zhihu_batch.py` 内置）

批量抓取脚本内置多层 Cookie 保活策略，无需手工干预：

1. **主动 TTL 检测**（每篇文章）：解析 z_c0 的 `expires` 字段，剩余 < 30 分钟时自动触发激进刷新
2. **常规保活**（每 5-8 篇）：访问知乎列表页 + 模拟滚动
3. **激进保活**（每 ~20 篇）：访问实际文章页 + 模拟阅读（停留 2-5 秒 + 滚动）
4. **被动检测**：每次访问文章时检查是否被重定向到 `/account/unhuman` 或 `/signin`
5. **自动恢复**：检测到失效时，自动尝试 3 次激进保活恢复
6. **Cookie 备份**：每次保活后自动从浏览器提取最新 Cookie 保存到文件（扩展格式含 expires）
7. **安全退出**：脚本结束前保存最新 Cookie + 当前进度

## 失效判断与处置

- 典型失效现象：页面标题「安全验证」、跳转 `/account/unhuman`、正文全空。
- 处置顺序：脚本会先自动重试 3 次（激进保活）；仍失败时运行 `zhihu_relogin.py` 人工重新登录。
- 切勿在 Cookie 失效时盲目加大并发重试 —— 优先恢复登录态。
