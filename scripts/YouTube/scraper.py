#!/usr/bin/env python3
"""
YouTube Podcast Scraper — 每日自动搜索优质播客并下载逐字稿

功能：
1. 搜索 YouTube 上关于企业成长、品牌建设、品牌运营的高播放量播客
2. 下载视频的逐字稿（字幕）
3. 按 wiki 来源格式保存到 obsidian

运行方式：
   python3 scripts/youtube_podcast_scraper.py
  
需要在 GitHub Secrets 设置：
  - YOUTUBE_API_KEY（可选，有则用于搜索排序，无则用 yt-dlp 搜索）
"""

import os
import re
import json
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

# Add scripts/shared to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'shared'))

# ── 配置 ──────────────────────────────────────────────
# 搜索关键词（中文 + 英文，提高覆盖率）
SEARCH_TOPICS = [
    # 中文 — 品牌运营/企业成长
    "品牌运营 创业故事 企业家 深度访谈",
    "品牌建设 品牌营销 增长策略",
    "企业成长 管理经验 创始人对话",
    "创业经验 商业思维 赚钱生意",
    "品牌出海 跨境电商 国际化运营",
    # 英文 — Brand & Business
    "brand building business strategy podcast interview",
    "founder story business growth branding tips",
    "how to build a brand marketing entrepreneurship",
    "startup scaling brand strategy CEO interview",
    "business growth mindset leadership brand story",
]

# 每个关键词取前 N 个视频
VIDEOS_PER_QUERY = 3

# 每天最多处理视频数（防止 Action 超时/超量）
MAX_VIDEOS_PER_RUN = 6

# 已处理视频记录文件（避免重复下载）
PROCESSED_DB = "raw/素材/.youtube_processed.json"

# 保存路径
OUTPUT_DIR = "wiki/来源/播客"

# ── 辅助函数 ──────────────────────────────────────────

def slugify(text):
    """生成文件名友好的字符串"""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text[:80]


def get_repo_root():
    """获取仓库根目录（脚本在 scripts/ 下运行）"""
    path = Path(__file__).resolve()
    # 向上找 .git 目录
    for parent in path.parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def load_processed():
    """加载已处理视频记录"""
    repo = get_repo_root()
    db_path = repo / PROCESSED_DB
    if db_path.exists():
        with open(db_path) as f:
            return json.load(f)
    return {"processed_ids": [], "processed_urls": []}


def save_processed(data):
    """保存已处理视频记录"""
    repo = get_repo_root()
    db_path = repo / PROCESSED_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def search_youtube(query, max_results=5):
    """搜索 YouTube 视频，返回 [{id, title, channel, views, url}]"""
    import subprocess, json
    
    results = []
    
    # 方法 1: yt-dlp 搜索（按相关性）
    try:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist", "-J",
        ]
        # 如果有 cookies 文件，自动使用
        if os.path.exists("cookies.txt"):
            cmd += ["--cookies", "cookies.txt"]
        cmd += [f"ytsearch{max_results}:{query}"]
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if output.returncode == 0:
            data = json.loads(output.stdout)
            for entry in data.get('entries', []):
                results.append({
                    'id': entry['id'],
                    'title': entry.get('title', 'Untitled'),
                    'channel': entry.get('channel', entry.get('uploader', 'Unknown')),
                    'views': entry.get('view_count', 0),
                    'url': f"https://youtube.com/watch?v={entry['id']}",
                    'duration': entry.get('duration', 0),
                })
    except Exception as e:
        print(f"  yt-dlp search failed: {e}")
    
    return results


def get_transcript(video_id):
    """获取视频逐字稿（带时间戳），使用 yt-dlp 下载字幕文件"""
    import subprocess, tempfile, os, re
    
    cookie_status = "with cookies" if os.path.exists("cookies.txt") else "no cookies"
    if os.path.exists("cookies.txt"):
        cookie_size = os.path.getsize("cookies.txt")
        cookie_status = f"cookies.txt ({cookie_size} bytes)"
    
    print(f"    Downloading subtitles ({cookie_status})...")
    
    try:
        # 使用 yt-dlp 下载字幕文件到临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "yt-dlp", "--skip-download",
            ]
            # If we have cookies, use them; otherwise use mobile client to avoid JS challenge
            if os.path.exists("cookies.txt"):
                cmd += ["--cookies", "cookies.txt"]
            else:
                cmd += ["--extractor-args", "youtube:player_client=android,ios"]
            cmd += [
                "--write-auto-subs", "--write-subs",
                "--sub-langs", "zh-Hans,zh-Hant,zh,en",
                "--sub-format", "vtt",
                "-o", f"{tmpdir}/%(id)s",
            ]
            cmd += [f"https://www.youtube.com/watch?v={video_id}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            # Log any errors from yt-dlp
            if result.returncode != 0:
                print(f"  yt-dlp exit code: {result.returncode}")
            
            # Check stderr for clues
            if result.stderr and 'ERROR' in result.stderr:
                print(f"  yt-dlp ERROR: {result.stderr.splitlines()[0][:200]}" if result.stderr else "")
            
            # 查找下载的字幕文件
            sub_files = [f for f in os.listdir(tmpdir) if f.endswith('.vtt')]
            if not sub_files:
                # 尝试不同的语言标签
                cmd = [
                    "yt-dlp", "--skip-download",
                ]
                if os.path.exists("cookies.txt"):
                    cmd += ["--cookies", "cookies.txt"]
                else:
                    cmd += ["--extractor-args", "youtube:player_client=android,ios"]
                cmd += [
                    "--write-auto-subs",
                    "--sub-langs", "all",
                    "--sub-format", "vtt",
                    "-o", f"{tmpdir}/%(id)s",
                ]
                cmd += [f"https://www.youtube.com/watch?v={video_id}"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                sub_files = [f for f in os.listdir(tmpdir) if f.endswith('.vtt')]
            
            if not sub_files:
                print(f"  No subtitle files downloaded")
                return None
            
            # 选择最佳字幕（优先中文，其次英文）
            chosen_file = None
            lang_code = 'unknown'
            for lang in ['zh-Hans', 'zh-Hant', 'zh', 'en']:
                for f in sub_files:
                    if lang in f:
                        chosen_file = os.path.join(tmpdir, f)
                        lang_code = lang
                        break
                if chosen_file:
                    break
            
            if not chosen_file:
                chosen_file = os.path.join(tmpdir, sub_files[0])
                lang_code = sub_files[0].split('.')[1] if '.' in sub_files[0] else 'unknown'
            
            # 解析 VTT 文件
            with open(chosen_file, 'r', encoding='utf-8') as f:
                vtt_content = f.read()
            
            # 解析 VTT 时间戳和文本
            segments = []
            # VTT 格式: HH:MM:SS.mmm --> HH:MM:SS.mmm
            pattern = re.compile(r'(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}\s*\n(.*?)(?=\n\n|\Z)', re.DOTALL)
            
            for match in pattern.finditer(vtt_content):
                ts = match.group(1)
                text = match.group(2).strip()
                # 移除 VTT 标签（如 <c>、</c> 等）
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if text and not text.startswith('WEBVTT'):
                    # 转换时间戳为秒
                    h, m, s = ts.replace(',', '.').split(':')
                    start_sec = float(h) * 3600 + float(m) * 60 + float(s)
                    segments.append({
                        'text': text,
                        'start': start_sec,
                        'duration': 0,
                        'language': lang_code,
                    })
            
            if not segments:
                print(f"  Could not parse subtitle file")
                return None
            
            print(f"  ✅ 下载了 {len(segments)} 条字幕 ({lang_code})")
            return {
                'segments': segments,
                'language': lang_code,
                'has_zh': 'zh' in lang_code,
                'has_en': 'en' in lang_code,
            }
            
    except subprocess.TimeoutExpired:
        print(f"  yt-dlp timed out for {video_id}")
        return None
    except Exception as e:
        print(f"  Transcript error for {video_id}: {e}")
        return None


def format_timestamp(seconds):
    """秒 → HH:MM:SS"""
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def transcript_to_markdown(video_info, transcript_meta):
    """将逐字稿转换为 markdown wiki 来源页"""
    now = datetime.now(timezone.utc)
    
    # 构建 frontmatter
    lang_tag = transcript_meta['language'] if transcript_meta else 'N/A'
    tags = ["YouTube", "播客", "逐字稿", lang_tag]
    title = video_info['title']
    slug = slugify(title)
    filename = f"{now.strftime('%Y-%m-%d')} {title[:60]}.md"
    
    # 生成内容
    lines = []
    lines.append("---")
    lines.append("type: source")
    lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("sources: [YouTube]")
    lines.append(f"created: {now.strftime('%Y-%m-%d')}")
    lines.append(f"updated: {now.strftime('%Y-%m-%d')}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> 来源：[{video_info['title']}]({video_info['url']}) | {video_info['channel']}")
    lines.append("")
    lines.append("## 视频信息")
    lines.append("")
    lines.append(f"- **标题**: {video_info['title']}")
    lines.append(f"- **频道**: {video_info['channel']}")
    lines.append(f"- **链接**: [{video_info['url']}]({video_info['url']})")
    if video_info.get('views'):
        lines.append(f"- **播放量**: {video_info['views']:,}")
    lines.append(f"- **字幕语言**: {transcript_meta['language'] if transcript_meta else 'N/A'}")
    lines.append(f"- **抓取日期**: {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("## 逐字稿")
    lines.append("")
    
    if transcript_meta and transcript_meta.get('segments'):
        lang = transcript_meta['language']
        transcript_text = ""
        for seg in transcript_meta['segments']:
            ts = format_timestamp(seg['start'])
            text = seg['text']
            transcript_text += text + " "
            # 判断是否需要翻译标注
            if lang.startswith('zh'):
                lines.append(f"[{ts}] {text}")
            else:
                # 英文或其他语言：输出原文，标注语言
                lines.append(f"[{ts}] **[{lang.upper()}]** {text}")
        
        # 生成 AI 总结
        if transcript_text.strip():
            print(f"   生成 AI 总结...")
            from summarize import summarize_transcript
            summary = summarize_transcript(title, video_info['channel'], transcript_text)
            if summary:
                lines.append("")
                lines.append(summary)
    else:
        lines.append("*（逐字稿获取失败）*")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    topics = "、".join(SEARCH_TOPICS[:3])
    lines.append(f"*自动抓取于 {now.strftime('%Y-%m-%d %H:%M UTC')} | 搜索主题：{topics}*")
    
    return filename, "\n".join(lines)


def save_note(filename, content):
    """保存到 wiki/来源/播客/"""
    repo = get_repo_root()
    filepath = repo / OUTPUT_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  ✅ 已保存: {OUTPUT_DIR}/{filename}")
    return filepath


def update_index(video_info, filename):
    """更新 wiki/index.md"""
    repo = get_repo_root()
    index_path = repo / "wiki" / "index.md"
    
    if not index_path.exists():
        return
    
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已存在
    if filename in content:
        return  # 已记录
    
    # 更新来源页计数
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    entry = f"| [[{OUTPUT_DIR}/{filename.replace('.md', '')}]] | {video_info['title'][:50]} | {today} |\n"
    
    # 在来源表格末尾插入
    insert_pos = content.rfind("|---")
    if insert_pos > 0:
        next_newline = content.find('\n', insert_pos)
        if next_newline > 0:
            content = content[:next_newline+1] + entry + content[next_newline+1:]
    
    # 更新统计
    stats_match = re.search(r'\*\*来源页\**: (\d+)', content)
    if stats_match:
        old_count = int(stats_match.group(1))
        new_count = old_count + 1
        content = content.replace(
            f"**来源页**: {old_count}",
            f"**来源页**: {new_count}"
        )
    
    # 更新最后更新日期
    content = re.sub(
        r'\*最后更新：[\d-]+\*',
        f'*最后更新：{today}*',
        content
    )
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  📝 index.md 已更新")


def update_log(video_info, filename):
    """更新 wiki/log.md"""
    repo = get_repo_root()
    log_path = repo / "wiki" / "log.md"
    
    if not log_path.exists():
        return
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    entry = f"""
---

## [{today}] | ingest | {video_info['title'][:50]}

- 自动抓取 YouTube 播客：{video_info['title']}
- 频道：{video_info['channel']}
- 链接：[{video_info['url']}]({video_info['url']})
- 保存到：{OUTPUT_DIR}/{filename}
"""
    
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)


# ── 主流程 ────────────────────────────────────────────

def main():
    print(f"YouTube Podcast Scraper v1.0")
    print(f"运行时间: {datetime.now().isoformat()}")
    print(f"仓库根目录: {get_repo_root()}")
    print()
    
    # 加载已处理记录
    processed = load_processed()
    processed_ids = set(processed.get('processed_ids', []))
    processed_urls = set(processed.get('processed_urls', []))
    print(f"已处理视频: {len(processed_ids)} 个")
    print()
    
    new_videos = []
    
    # 遍历搜索关键词
    for query in SEARCH_TOPICS:
        print(f"🔍 搜索: {query}")
        results = search_youtube(query, max_results=VIDEOS_PER_QUERY)
        print(f"   找到 {len(results)} 个视频")
        
        for v in results:
            if v['url'] not in processed_urls and v['id'] not in processed_ids:
                if v not in new_videos:
                    new_videos.append(v)
        
        if len(new_videos) >= MAX_VIDEOS_PER_RUN:
            break
    
    # 按播放量排序
    new_videos.sort(key=lambda x: x.get('views', 0), reverse=True)
    new_videos = new_videos[:MAX_VIDEOS_PER_RUN]
    
    print(f"\n📊 本次待处理新视频: {len(new_videos)} 个")
    print()
    
    success_count = 0
    for v in new_videos:
        print(f"📹 [{v['id']}] {v['title']}")
        print(f"   频道: {v['channel']} | 播放: {v.get('views', 'N/A')}")
        
        # 获取逐字稿
        transcript = get_transcript(v['id'])
        if transcript:
            print(f"   逐字稿: {len(transcript)} 段")
        else:
            print(f"   ⚠️ 无逐字稿（可能没有字幕）")
        
        # 生成 markdown
        filename, content = transcript_to_markdown(v, transcript)
        save_note(filename, content)
        
        # 更新 index 和 log
        update_index(v, filename)
        update_log(v, filename)
        
        # 记录为已处理
        processed_ids.add(v['id'])
        processed_urls.add(v['url'])
        success_count += 1
        print()
    
    # 保存处理记录
    processed['processed_ids'] = list(processed_ids)
    processed['processed_urls'] = list(processed_urls)
    save_processed(processed)
    
    print(f"✅ 完成！成功处理 {success_count}/{len(new_videos)} 个视频")
    print(f"   累计已处理: {len(processed_ids)} 个")
    
    # 返回成功数用于 GitHub Actions 输出
    return success_count


if __name__ == "__main__":
    sys.exit(main())
# Trigger run Thu May 14 19:44:30 CST 2026
