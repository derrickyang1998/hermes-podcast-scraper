#!/usr/bin/env python3
"""
Bilibili Podcast Scraper — 每日从 B 站抓取品牌运营/企业成长播客

运行方式:
   python3 scripts/bilibili_podcast_scraper.py
"""

import json
import re
import os
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# Add scripts/shared to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'shared'))


# ── 配置 ──────────────────────────────────────────────
SEARCH_TOPICS = [
    "品牌运营 深度访谈 企业家",
    "品牌建设 创始人对话 创业故事",
    "品牌营销 增长策略 企业成长",
    "创业经验 商业思维 管理心得",
    "跨境电商 品牌出海 运营实战",
]

VIDEOS_PER_QUERY = 2
MAX_VIDEOS_PER_RUN = 5
PROCESSED_DB = "raw/素材/.bilibili_processed.json"
OUTPUT_DIR = "wiki/来源/播客"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com",
}


def get_repo_root():
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists():
            return parent
    return Path.cwd()


def load_processed():
    repo = get_repo_root()
    db_path = repo / PROCESSED_DB
    if db_path.exists():
        with open(db_path) as f:
            return json.load(f)
    return {"processed_ids": [], "processed_urls": []}


def save_processed(data):
    repo = get_repo_root()
    db_path = repo / PROCESSED_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def search_bilibili(query, max_results=3):
    """搜索 Bilibili 视频"""
    encoded = urllib.parse.quote(query)
    url = f"https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={encoded}&page=1&order=click"
    req = urllib.request.Request(url, headers=HEADERS)
    
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        if data.get('code') != 0:
            return []
        
        results = []
        for r in data['data'].get('result', []):
            if r.get('type') != 'video':
                continue
            results.append({
                'id': r['bvid'],
                'aid': r.get('aid', 0),
                'title': r['title'].replace('<em class="keyword">', '').replace('</em>', ''),
                'channel': r.get('author', 'Unknown'),
                'views': r.get('play', 0),
                'url': f"https://www.bilibili.com/video/{r['bvid']}",
                'duration': r.get('duration', ''),
                'description': r.get('description', ''),
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"  Search failed: {e}")
        return []


def get_video_subtitles(bvid, aid=0, cid=None):
    """获取 B 站视频字幕"""
    
    # Step 1: If we don't have cid, get it from video info
    if not cid:
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            if data.get('code') != 0:
                return None
            cid = data['data']['cid']
        except Exception as e:
            print(f"    Video info error: {e}")
            return None
    
    # Step 2: Get subtitle list from player API
    url = f"https://api.bilibili.com/x/player/v2?cid={cid}&bvid={bvid}"
    req = urllib.request.Request(url, headers=HEADERS)
    
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        if data.get('code') != 0:
            return None
        
        sub_info = data['data'].get('subtitle', {})
        sub_list = sub_info.get('subtitles', [])
        
        if not sub_list:
            return None
        
        # 优先中文
        chosen = None
        for lang in ['zh-Hans', 'zh-Hant', 'zh-CN', 'zh']:
            for s in sub_list:
                if s.get('lan', '') == lang:
                    chosen = s
                    break
            if chosen:
                break
        
        if not chosen:
            chosen = sub_list[0]
        
        # Step 3: Download subtitle JSON
        sub_url = chosen['subtitle_url']
        if sub_url.startswith('//'):
            sub_url = 'https:' + sub_url
        
        req3 = urllib.request.Request(sub_url, headers=HEADERS)
        resp3 = urllib.request.urlopen(req3, timeout=10)
        sub_data = json.loads(resp3.read())
        
        bodies = sub_data.get('body', [])
        segments = []
        for seg in bodies:
            segments.append({
                'text': seg['content'],
                'start': seg.get('from', 0),
                'duration': seg.get('to', 0) - seg.get('from', 0),
                'language': chosen.get('lan_doc', chosen.get('lan', 'zh')),
            })
        
        return {
            'segments': segments,
            'language': chosen.get('lan_doc', chosen.get('lan', 'zh')),
            'has_zh': True,
            'has_en': False,
        }
    except Exception as e:
        print(f"    Subtitle error: {e}")
        return None


def format_timestamp(seconds):
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def save_markdown(video_info, transcript_meta):
    """保存 markdown 到 wiki/来源/播客/"""
    now = datetime.now(timezone.utc)
    title = video_info['title']
    
    # 清理文件名
    safe_title = re.sub(r'[\\/*?:"<>|]', '', title)[:60]
    filename = f"{now.strftime('%Y-%m-%d')} {safe_title}.md"
    
    lang_tag = transcript_meta['language'] if transcript_meta else 'N/A'
    
    lines = []
    lines.append("---")
    lines.append("type: source")
    lines.append(f"tags: [Bilibili, 品牌运营, 逐字稿, {lang_tag}]")
    lines.append("sources: [Bilibili]")
    lines.append(f"created: {now.strftime('%Y-%m-%d')}")
    lines.append(f"updated: {now.strftime('%Y-%m-%d')}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> 来源：[{title}]({video_info['url']}) | {video_info['channel']}")
    lines.append("")
    lines.append("## 视频信息")
    lines.append("")
    lines.append(f"- **标题**: {title}")
    lines.append(f"- **频道**: {video_info['channel']}")
    lines.append(f"- **链接**: [{video_info['url']}]({video_info['url']})")
    if video_info.get('views'):
        lines.append(f"- **播放量**: {video_info['views']:,}")
    if video_info.get('duration'):
        lines.append(f"- **时长**: {video_info['duration']}")
    lines.append(f"- **字幕语言**: {lang_tag}")
    lines.append(f"- **抓取日期**: {now.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("## 逐字稿")
    lines.append("")
    
    transcript_text = ""
    if transcript_meta and transcript_meta.get('segments'):
        for seg in transcript_meta['segments']:
            ts = format_timestamp(seg['start'])
            lines.append(f"[{ts}] {seg['text']}")
            transcript_text += seg['text'] + " "
    else:
        lines.append("*（该视频无字幕）*")
    
    # 生成 AI 总结
    if transcript_text.strip():
        print(f"   生成 AI 总结...")
        from summarize import summarize_transcript
        summary = summarize_transcript(title, video_info['channel'], transcript_text)
        if summary:
            lines.append("")
            lines.append(summary)
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*自动抓取于 {now.strftime('%Y-%m-%d %H:%M UTC')} | Bilibili*")
    
    repo = get_repo_root()
    filepath = repo / OUTPUT_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"  ✅ 已保存: {OUTPUT_DIR}/{filename}")
    return filename


def update_index(video_info, filename):
    repo = get_repo_root()
    index_path = repo / "wiki" / "index.md"
    if not index_path.exists():
        return
    
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if filename in content:
        return
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    entry = f"| [[{OUTPUT_DIR}/{filename.replace('.md', '')}]] | {video_info['title'][:50]} | {today} |\n"
    
    # 插入到来源表格末尾
    marker = "## 对比页 Comparison"
    if marker in content:
        content = content.replace(marker, entry + "\n" + marker)
    
    # 更新统计
    content = re.sub(
        r'(\*\*来源页\**: )(\d+)',
        lambda m: f"{m.group(1)}{int(m.group(2)) + 1}",
        content
    )
    
    content = re.sub(
        r'\*最后更新：[\d-]+\*',
        f'*最后更新：{today}*',
        content
    )
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  📝 index.md 已更新")


def update_log(video_info, filename):
    repo = get_repo_root()
    log_path = repo / "wiki" / "log.md"
    if not log_path.exists():
        return
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    entry = f"""
---

## [{today}] | ingest | B站: {video_info['title'][:50]}

- Bilibili 自动抓取：{video_info['title']}
- 频道：{video_info['channel']}
- 链接：[{video_info['url']}]({video_info['url']})
- 保存到：{OUTPUT_DIR}/{filename}
"""
    
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)


def main():
    print(f"Bilibili Podcast Scraper v1.0")
    print(f"运行时间: {datetime.now().isoformat()}")
    print()
    
    processed = load_processed()
    processed_ids = set(processed.get('processed_ids', []))
    processed_urls = set(processed.get('processed_urls', []))
    print(f"已处理视频: {len(processed_ids)} 个\n")
    
    new_videos = []
    for query in SEARCH_TOPICS:
        if len(new_videos) >= MAX_VIDEOS_PER_RUN:
            break
        print(f"🔍 搜索: {query}")
        results = search_bilibili(query, max_results=VIDEOS_PER_QUERY)
        print(f"   找到 {len(results)} 个")
        for v in results:
            if v['url'] not in processed_urls and v['id'] not in processed_ids:
                new_videos.append(v)
    
    print(f"\n📊 新视频: {len(new_videos)} 个\n")
    
    success = 0
    for v in new_videos[:MAX_VIDEOS_PER_RUN]:
        print(f"📹 [{v['id']}] {v['title'][:55]}")
        print(f"   频道: {v['channel']} | 播放: {v.get('views', 'N/A'):,}")
        
        transcript = get_video_subtitles(v['id'], v.get('aid', 0))
        if transcript:
            print(f"   ✅ 字幕: {len(transcript['segments'])} 段 ({transcript['language']})")
        else:
            print(f"   ⚠️ 无字幕")
        
        filename = save_markdown(v, transcript)
        update_index(v, filename)
        update_log(v, filename)
        
        processed_ids.add(v['id'])
        processed_urls.add(v['url'])
        success += 1
        print()
    
    processed['processed_ids'] = list(processed_ids)
    processed['processed_urls'] = list(processed_urls)
    save_processed(processed)
    
    print(f"✅ 完成！成功处理 {success}/{len(new_videos[:MAX_VIDEOS_PER_RUN])}")
    return success


if __name__ == "__main__":
    sys.exit(main())
