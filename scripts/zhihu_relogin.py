#!/usr/bin/env python3
"""
知乎重新登录脚本
会打开浏览器窗口，请手动登录后按回车保存 cookie
"""
import asyncio
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

from playwright.async_api import async_playwright


def get_default_paths():
    """与 fetch_zhihu_batch 等脚本一致：OPENCLAW_WORKSPACE 优先，否则 ~/.openclaw/workspace"""
    workspace = os.environ.get(
        "OPENCLAW_WORKSPACE",
        os.path.join(os.path.expanduser("~"), ".openclaw", "workspace"),
    )
    return {
        "workspace": workspace,
        "cookie_file": os.path.join(workspace, "zhihu_cookies.json"),
        "user_data_dir": os.path.join(workspace, "chrome_user_data"),
    }


async def main():
    print("=" * 60)
    print("知乎重新登录")
    print("=" * 60)
    print()
    print("步骤：")
    print("1. 浏览器会打开知乎登录页面")
    print("2. 请手动完成登录（扫码或账号密码）")
    print("3. 登录成功后，按回车键保存 cookie")
    print()

    paths = get_default_paths()
    cookie_file = paths["cookie_file"]
    user_data_dir = paths["user_data_dir"]
    os.makedirs(paths["workspace"], exist_ok=True)

    async with async_playwright() as p:
        # 使用持久化上下文
        context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=['--disable-blink-features=AutomationControlled'],
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            viewport={'width': 1440, 'height': 900},
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # 访问知乎
        print("正在打开知乎...")
        await page.goto('https://www.zhihu.com', wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)
        
        title = await page.title()
        print(f"当前页面: {title}")
        
        # 等待用户登录。
        # 交互式终端：按回车继续。否则（如通过 Claude Code 的 ! 前缀运行，stdin 非 TTY）
        # 改为轮询检测 z_c0 cookie，登录成功后自动保存。
        if sys.stdin.isatty():
            input("\n请在浏览器中完成登录，然后按回车键继续...")
        else:
            print("\n[非交互模式] 请在浏览器中完成登录，正在等待 z_c0 cookie（最多 5 分钟）...")
            for _ in range(150):  # 150 * 2s = 5 分钟
                names = {c['name'] for c in await context.cookies()}
                if 'z_c0' in names:
                    print("[OK] 已检测到登录，正在保存...")
                    break
                await page.wait_for_timeout(2000)
            else:
                print("[!] 超时未检测到 z_c0 cookie，仍尝试保存当前 cookie")

        # 获取所有 cookie
        cookies = await context.cookies()
        
        # 保存 cookie
        cookie_dict = {}
        for cookie in cookies:
            cookie_dict[cookie['name']] = cookie['value']
        
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(cookie_dict, f, ensure_ascii=False, indent=2)
        
        print(f"\n已保存 {len(cookies)} 个 cookie 到 {cookie_file}")
        
        # 检查是否有 z_c0
        if 'z_c0' in cookie_dict:
            print("[OK] 检测到 z_c0 cookie，登录成功！")
        else:
            print("[!] 未检测到 z_c0 cookie，可能登录未完成")
        
        await context.close()
    
    print("\n完成！现在可以运行批量抓取脚本了。")

if __name__ == "__main__":
    asyncio.run(main())
