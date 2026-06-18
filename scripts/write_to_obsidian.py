#!/usr/bin/env python3
"""
知乎文章写入 Obsidian 知识库
自动检测 Obsidian Vault 路径，根据内容智能分类，结合已有目录结构。

用法:
  python write_to_obsidian.py <文章目录> [Obsidian Vault 路径]

Vault 解析优先级（从高到低）:
  1. 命令行第二个参数
  2. 环境变量 OBSIDIAN_VAULT（单个 Vault 根路径；也可用 ZHIHU_OBSIDIAN_VAULT 作为别名）
  3. 常见目录扫描（多个命中时可交互选择）
"""

import os
import re
import sys
import hashlib
import subprocess
from datetime import datetime
from pathlib import Path

from zhihu_obsidian_config import resolve_root_folder


def env_vault_candidate_paths():
    """
    从环境变量读取 Vault 候选路径。
    OBSIDIAN_VAULT 为主；ZHIHU_OBSIDIAN_VAULT 为别名。多个路径用 os.pathsep 分隔（少见）。
    """
    keys = ("OBSIDIAN_VAULT", "ZHIHU_OBSIDIAN_VAULT")
    ordered = []
    seen = set()
    for key in keys:
        raw = os.environ.get(key, "").strip()
        if not raw:
            continue
        for part in raw.split(os.pathsep):
            part = part.strip().strip('"').strip("'")
            if not part:
                continue
            p = Path(part).expanduser()
            try:
                rp = p.resolve()
            except Exception:
                rp = p
            key_str = str(rp)
            if key_str in seen:
                continue
            seen.add(key_str)
            ordered.append(rp)
    return ordered


def detect_obsidian_vault():
    """
    自动检测本地 Obsidian Vault 路径。
    检测策略：
    1. 环境变量 OBSIDIAN_VAULT（及别名 ZHIHU_OBSIDIAN_VAULT）
    2. 常见路径扫描（用户目录与各盘符常见目录）
    """
    candidates = []

    env_paths = env_vault_candidate_paths()
    env_resolved_existing = set()
    for p in env_paths:
        if p.exists():
            env_resolved_existing.add(str(p.resolve()))

    common_paths = []
    common_paths.extend(env_paths)

    home = Path.home()
    common_paths.extend([
        home / "Documents" / "Obsidian Vault",
        home / "Documents" / "Obsidian",
        home / "Obsidian Vault",
        home / "Obsidian",
        home / "MyVault",
        home / "vault",
    ])

    for drive in ["C:", "D:", "E:"]:
        common_paths.append(Path(f"{drive}/Obsidian Vault"))
        common_paths.append(Path(f"{drive}/vault"))
        common_paths.append(Path(f"{drive}/Documents/Obsidian Vault"))

    seen_paths = set()
    uniq = []
    for p in common_paths:
        try:
            k = str(p.resolve())
        except Exception:
            k = str(p)
        if k not in seen_paths:
            seen_paths.add(k)
            uniq.append(p)

    for p in uniq:
        if not p.exists():
            continue
        rs = str(p.resolve())
        has_obsidian_meta = (p / ".obsidian").exists()
        # 显式配置的路径：即使暂未生成 .obsidian 也纳入（少见）；其余须有 .obsidian
        if has_obsidian_meta or rs in env_resolved_existing:
            candidates.append(rs)

    # 去重并返回
    candidates = list(dict.fromkeys(candidates))
    return candidates


def detect_existing_categories(vault_path, root_folder):
    """
    扫描 Obsidian Vault 中已有的分类目录。
    返回: {分类名: 文章数量}
    """
    categories = {}
    zhihu_dir = os.path.join(vault_path, root_folder)

    # 扫描知乎收藏目录下的分类
    if os.path.exists(zhihu_dir):
        for item in os.listdir(zhihu_dir):
            item_path = os.path.join(zhihu_dir, item)
            if os.path.isdir(item_path) and not item.startswith('.'):
                # 统计该分类下的文章数
                article_count = len([f for f in os.listdir(item_path) if f.endswith('.md')])
                categories[item] = article_count

    # 扫描 Vault 根目录的一级文件夹（作为参考）
    vault_categories = {}
    for item in os.listdir(vault_path):
        item_path = os.path.join(vault_path, item)
        if os.path.isdir(item_path) and not item.startswith('.'):
            article_count = len([f for f in os.listdir(item_path) if f.endswith('.md')])
            vault_categories[item] = article_count

    return {
        'zhihu': categories,
        'vault': vault_categories,
    }


def analyze_content_categories(article_files, existing_categories):
    """
    分析文章内容，结合已有分类，生成智能分类规则。
    策略：
    1. 优先匹配已有分类的关键词
    2. 对无法匹配的内容，自动聚类生成新分类
    """
    # 从已有分类中提取关键词
    existing_keywords = {}
    for cat_name in existing_categories.get('zhihu', {}):
        existing_keywords[cat_name] = cat_name.lower()

    # 预定义的通用分类模板（仅作为参考，不强制使用）
    template_rules = {
        'AI与人工智能': ['ai', '人工智能', 'gpt', 'chatgpt', '大模型', 'llm', '深度学习',
                         '机器学习', 'openai', 'claude', 'gemini', 'aigc', 'agent'],
        '编程与开发': ['python', 'java', 'javascript', 'typescript', '编程', '代码',
                       '开发', '框架', 'api', '数据库', 'docker', 'git', '前端', '后端'],
        '创业与商业': ['创业', '商业', '融资', '投资', 'startup', '产品', '运营',
                       '市场', '营销', '一人公司', '独立开发', '副业'],
        '效率与工具': ['效率', '工具', '自动化', '工作流', '笔记', 'obsidian', 'notion'],
        '职场与成长': ['职场', '工作', '面试', '职业', '成长', '学习', '认知'],
        '科技与互联网': ['科技', '互联网', '芯片', '区块链', 'web3', '自动驾驶'],
        '产品与设计': ['产品', '设计', 'ui', 'ux', '交互', '用户体验', 'figma'],
        '生活杂谈': ['生活', '健康', '旅行', '电影', '读书', '随笔', '思考'],
    }

    # 如果已有分类很多，优先使用已有分类
    if len(existing_categories.get('zhihu', {})) >= 3:
        print(f"检测到已有 {len(existing_categories['zhihu'])} 个分类，优先匹配已有分类")
        return existing_keywords, template_rules
    else:
        print(f"已有分类较少（{len(existing_categories.get('zhihu', {}))} 个），使用智能分类")
        return {}, template_rules


def classify_article(title, content_preview, existing_keywords, template_rules):
    """
    智能分类：优先匹配已有分类，其次使用模板规则。
    """
    text = (title + ' ' + content_preview).lower()

    # 优先级1：匹配已有分类关键词
    if existing_keywords:
        for cat_name, keyword in existing_keywords.items():
            if keyword in text:
                return cat_name

    # 优先级2：使用模板规则
    scores = {}
    for category, keywords in template_rules.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[category] = score

    if scores:
        return max(scores, key=scores.get)

    # 优先级3：根据标题特征推断
    if any(w in title for w in ['?', '？', '如何', '怎么', '为什么', '是什么']):
        return '问答与思考'

    return '未分类'


def parse_article_metadata(filepath):
    """解析文章的 frontmatter"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    meta = {}
    if content.startswith('---'):
        end = content.find('---', 3)
        if end > 0:
            frontmatter = content[3:end].strip()
            for line in frontmatter.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    meta[key.strip()] = value.strip().strip('"')
            meta['body'] = content[end+3:].strip()
    else:
        meta['body'] = content

    return meta


def _fm_scalar(value):
    """Render a value as a safe YAML frontmatter scalar (quote non-integers)."""
    s = str(value)
    if re.fullmatch(r'-?\d+', s):
        return s
    return '"' + s.replace('"', '\\"') + '"'


# 抓取阶段记录、但需要在 Obsidian frontmatter 中保留的互动元数据。
PRESERVED_META_KEYS = (
    'interaction_action',   # 赞同了回答 / 收藏了文章 ...
    'interaction_time',     # 互动时间 (ISO)
    'liked_action',
    'voteup',               # 赞同数
    'activity_id',
    'source_feed',
)


def build_preserved_frontmatter(meta):
    """从抓取出的 meta 里挑出互动相关字段，生成 frontmatter 行（无则返回空串）。"""
    lines = []
    for key in PRESERVED_META_KEYS:
        val = meta.get(key)
        if val not in (None, ''):
            lines.append(f'{key}: {_fm_scalar(val)}')
    return ('\n' + '\n'.join(lines)) if lines else ''


def strip_leading_title_block(body):
    """去掉抓取脚本写入正文开头的标题/作者块，避免与本脚本生成的标题重复。

    fetch_zhihu_batch 会在正文前加 `# 标题` 和 `> 作者: ... 原文: [知乎链接](...)`，
    而本脚本会重新生成更完整的标题（含分类/原文链接），因此先剥掉正文里的旧标题块。
    """
    lines = body.lstrip('\n').split('\n')
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
        if lines and lines[0].lstrip().startswith('>') and '作者' in lines[0]:
            lines = lines[1:]
    return '\n'.join(lines).strip()


def clean_content_for_obsidian(content):
    """清理内容使其适合 Obsidian"""
    # 更新图片路径：![](filename.jpg) -> ![](images/filename.jpg)
    content = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'![\1](images/\2)', content)
    
    content = re.sub(r'<img[^>]*>', '[图片]', content)
    content = re.sub(r'<video[^>]*>', '[视频]', content)
    content = re.sub(r'<iframe[^>]*>', '[嵌入内容]', content)
    return content


def sync_images(source_dir, vault_path, root_folder):
    """同步图片到 Obsidian Vault"""
    # 查找图片目录
    source_images_dir = os.path.join(source_dir, 'images')
    if not os.path.exists(source_images_dir):
        # 尝试其他可能的路径
        source_images_dir = os.path.join(os.path.dirname(source_dir), 'zhihu_images')

    if not os.path.exists(source_images_dir):
        print("  [!] 未找到图片目录，跳过图片同步")
        return 0

    # 目标图片目录
    obsidian_images_dir = os.path.join(vault_path, root_folder, 'images')
    os.makedirs(obsidian_images_dir, exist_ok=True)
    
    # 复制图片
    images = os.listdir(source_images_dir)
    copied = 0
    
    for img in images:
        src = os.path.join(source_images_dir, img)
        dst = os.path.join(obsidian_images_dir, img)
        
        if not os.path.exists(dst):
            try:
                import shutil
                shutil.move(src, dst)
                copied += 1
            except Exception:
                pass
    
    print(f"  [OK] 同步 {copied} 张图片到 Obsidian")
    return copied


def write_to_obsidian(article_files, vault_path, source_dir, root_folder):
    """将文章写入 Obsidian Vault"""
    zhihu_dir = os.path.join(vault_path, root_folder)
    os.makedirs(zhihu_dir, exist_ok=True)

    # 检测已有分类
    existing = detect_existing_categories(vault_path, root_folder)
    print(f"\n已有知乎分类: {list(existing['zhihu'].keys()) or '无'}")
    print(f"Vault 一级目录: {list(existing['vault'].keys())[:10]}")

    # 分析内容生成分类规则
    existing_keywords, template_rules = analyze_content_categories(article_files, existing)

    stats = {'total': 0, 'success': 0, 'skip': 0, 'categories': {}}

    for filepath in article_files:
        stats['total'] += 1

        try:
            meta = parse_article_metadata(filepath)
            title = meta.get('title', os.path.basename(filepath))
            author = meta.get('author', '')
            url = meta.get('url', '')
            body = meta.get('body', '')

            if not body:
                print(f"  [!] 空内容，跳过: {title}")
                stats['skip'] += 1
                continue

            # 智能分类
            category = classify_article(title, body[:500], existing_keywords, template_rules)

            # 分类目录
            cat_dir = os.path.join(zhihu_dir, category)
            os.makedirs(cat_dir, exist_ok=True)

            # 保留抓取阶段记录的互动元数据（点赞/收藏动作、互动时间、赞同数等）
            preserved_fm = build_preserved_frontmatter(meta)

            # 可见标题下的互动摘要段（动作 + 日期），有则展示
            action = meta.get('interaction_action', '')
            when = (meta.get('interaction_time', '') or '')[:10]
            interaction_seg = f"{action} {when} | " if action else ''

            # 生成 Obsidian 兼容的 Markdown
            obsidian_content = f"""---
title: {_fm_scalar(title)}
author: {_fm_scalar(author)}
source: zhihu
url: {_fm_scalar(url)}
category: {_fm_scalar(category)}
imported: {datetime.now().strftime('%Y-%m-%d')}
tags: [zhihu, {category}]{preserved_fm}
---

# {title}

> {interaction_seg}作者: {author} | [原文链接]({url}) | 分类: {category}

{clean_content_for_obsidian(strip_leading_title_block(body))}
"""

            # 文件名
            safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:80]
            filename = f"{safe_title}.md"
            dest_path = os.path.join(cat_dir, filename)

            # 避免覆盖
            if os.path.exists(dest_path):
                file_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                filename = f"{safe_title}_{file_hash}.md"
                dest_path = os.path.join(cat_dir, filename)

            with open(dest_path, 'w', encoding='utf-8') as f:
                f.write(obsidian_content)

            # 删除源文件（剪切模式）
            try:
                os.remove(filepath)
            except Exception:
                pass

            stats['success'] += 1
            stats['categories'][category] = stats['categories'].get(category, 0) + 1
            print(f"  [OK] [{category}] {title[:40]}")

        except Exception as e:
            print(f"  [FAIL] 错误: {e}")
            stats['skip'] += 1

    return stats


def main():
    root_folder_cli = None
    if "--root-folder" in sys.argv:
        i = sys.argv.index("--root-folder")
        root_folder_cli = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    root_folder = resolve_root_folder(root_folder_cli)

    if len(sys.argv) < 2:
        print("用法: python write_to_obsidian.py <文章目录> [Obsidian Vault 路径]")
        print("")
        print("参数:")
        print("  文章目录       - fetch_zhihu_batch.py 输出的目录")
        print("  Obsidian Vault - Vault 根目录（可选；亦可设置环境变量见下）")
        print("")
        print("Vault 优先级: 命令行第 2 参数 > 环境变量 OBSIDIAN_VAULT > 常见目录扫描")
        print("")
        print("示例:")
        print("  python write_to_obsidian.py zhihu_articles_314624076")
        print("  python write_to_obsidian.py zhihu_articles_314624076 \"D:\\\\My Vault\"")
        print("  # Windows PowerShell 示例：")
        print('  $env:OBSIDIAN_VAULT="D:\\\\Notes\\\\MyVault"; python write_to_obsidian.py .\\\\zhihu_articles_xxx')
        sys.exit(1)

    source_dir = sys.argv[1]

    if not os.path.exists(source_dir):
        print(f"文章目录不存在: {source_dir}")
        sys.exit(1)

    # Vault 路径：命令行 > 环境变量（在 detect_obsidian_vault 内合并）> 自动扫描
    if len(sys.argv) > 2:
        vault_path = str(Path(sys.argv[2]).expanduser().resolve())
    else:
        print("正在检测本地 Obsidian Vault...")
        candidates = detect_obsidian_vault()
        if not candidates:
            print("未检测到 Obsidian Vault，请手动指定路径")
            sys.exit(1)
        if len(candidates) == 1:
            vault_path = candidates[0]
            print(f"检测到 Vault: {vault_path}")
        else:
            print(f"检测到多个 Vault:")
            for i, c in enumerate(candidates):
                print(f"  [{i+1}] {c}")
            choice = input("请选择编号 (默认 1): ").strip() or '1'
            vault_path = candidates[int(choice) - 1]
            print(f"已选择: {vault_path}")

    if not os.path.exists(vault_path):
        print(f"Vault 路径不存在: {vault_path}")
        sys.exit(1)

    # 收集文章文件
    article_files = []
    for f in sorted(os.listdir(source_dir)):
        if f.endswith('.md') and not f.startswith('_'):
            article_files.append(os.path.join(source_dir, f))

    if not article_files:
        # No new article bodies to write — e.g. every item in the batch was already
        # fetched (resume checkpoint skipped them) and lives in the vault already.
        # This is a clean no-op, not a failure: exit 0 so the orchestrator records
        # "ok" and advances the source window instead of retrying the same stuck range.
        print("没有新文章需要写入（全部已收录）")
        sys.exit(0)

    print(f"\n找到 {len(article_files)} 篇文章")
    print(f"目标 Vault: {vault_path}")
    print("=" * 60)

    stats = write_to_obsidian(article_files, vault_path, source_dir, root_folder)

    # 同步图片
    print("\n同步图片...")
    sync_images(source_dir, vault_path, root_folder)

    print("\n" + "=" * 60)
    print("写入完成！")
    print(f"  总计: {stats['total']}")
    print(f"  成功: {stats['success']}")
    print(f"  跳过: {stats['skip']}")
    print(f"\n分类统计:")
    for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 篇")
    print("=" * 60)


if __name__ == "__main__":
    main()




