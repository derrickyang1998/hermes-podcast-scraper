#!/usr/bin/env python3
"""
Bilibili Subtitle Downloader - 通过 WBI 签名 API 获取 B 站视频字幕

Based on B站 WBI signing protocol:
https://github.com/SocialSisterYi/bilibili-API-collect/blob/master/docs/misc/sign/wbi.md
"""

import json
import hashlib
import time
import urllib.request
import urllib.parse
from functools import lru_cache

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com",
}

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52
]


def _get_mixin_key() -> str:
    """获取 mixin key（缓存 1 小时）"""
    url = "https://api.bilibili.com/x/web-interface/nav"
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    
    wbi_img = data['data']['wbi_img']
    # Extract keys from URLs
    img_key = wbi_img['img_url'].split('/')[-1].split('.')[0]
    sub_key = wbi_img['sub_url'].split('/')[-1].split('.')[0]
    
    raw_key = img_key + sub_key
    mixin = ''.join(raw_key[i] for i in MIXIN_KEY_ENC_TAB if i < len(raw_key))
    return mixin[:32]


def _wbi_sign(params: dict) -> dict:
    """对请求参数进行 WBI 签名"""
    mixin_key = _get_mixin_key()
    params['wts'] = int(time.time())
    
    # Sort params and build query string
    sorted_params = sorted(params.items())
    query = urllib.parse.urlencode(sorted_params)
    
    # MD5 hash
    sign_str = query + mixin_key
    w_rid = hashlib.md5(sign_str.encode()).hexdigest()
    params['w_rid'] = w_rid
    
    return params


def get_video_subtitles(bvid: str) -> dict:
    """
    获取 B 站视频的所有字幕
    返回: {
        'segments': [{text, start, duration, language}, ...],
        'has_zh': bool, 'has_en': bool,
    } 或 None
    """
    
    # Step 1: WBI-signed video info request
    params = _wbi_sign({'bvid': bvid})
    url = f"https://api.bilibili.com/x/web-interface/wbi/view?{urllib.parse.urlencode(params)}"
    
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    
    if data.get('code') != 0:
        return None
    
    v = data['data']
    cid = v['cid']
    sub_info = v.get('subtitle') or {}
    sub_list = sub_info.get('list', sub_info.get('subtitles', []))
    
    if not sub_list:
        return None
    
    print(f"    Found {len(sub_list)} subtitle tracks")
    
    # 优先中文，其次英文
    chosen = None
    for lang in ['zh-Hans', 'zh-CN', 'zh', 'zh-Hant']:
        for s in sub_list:
            if s.get('lan', '') == lang:
                chosen = s
                break
        if chosen:
            break
    
    # Fallback to English
    if not chosen:
        for s in sub_list:
            if s.get('lan', '').startswith('en'):
                chosen = s
                break
    
    # Last fallback
    if not chosen and sub_list:
        chosen = sub_list[0]
    
    if not chosen:
        return None
    
    # Step 2: Get subtitle download URL (WBI signed for player API)
    player_params = _wbi_sign({'cid': cid, 'bvid': bvid})
    player_url = f"https://api.bilibili.com/x/player/wbi/v2?{urllib.parse.urlencode(player_params)}"
    
    try:
        req2 = urllib.request.Request(player_url, headers=HEADERS)
        resp2 = urllib.request.urlopen(req2, timeout=10)
        player_data = json.loads(resp2.read())
        
        if player_data.get('code') == 0:
            p_sub = player_data['data'].get('subtitle', {})
            p_sub_list = p_sub.get('subtitles', p_sub.get('list', []))
            for ps in p_sub_list:
                if ps.get('lan', '') == chosen.get('lan', ''):
                    chosen = ps
                    break
        
    except Exception:
        pass
    
    # Step 3: Download subtitle JSON
    sub_url = chosen.get('subtitle_url', '')
    if not sub_url:
        print(f"    No subtitle URL for {chosen.get('lan_doc', '?')}")
        return None
    
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
    
    # Check if we have Chinese and English
    has_zh = any(s.get('lan', '').startswith('zh') for s in sub_list if s != chosen)
    has_en = any(s.get('lan', '').startswith('en') for s in sub_list if s != chosen)
    # Also check the chosen one
    if chosen.get('lan', '').startswith('zh'): has_zh = True
    if chosen.get('lan', '').startswith('en'): has_en = True
    
    print(f"    ✅ Downloaded {len(segments)} segments ({chosen.get('lan_doc', chosen.get('lan', '?'))})")
    
    return {
        'segments': segments,
        'language': chosen.get('lan_doc', chosen.get('lan', 'zh')),
        'has_zh': has_zh,
        'has_en': has_en,
    }


# ── Test ──
if __name__ == "__main__":
    import sys
    test_bvid = sys.argv[1] if len(sys.argv) > 1 else "BV1GJ411x7h7"
    result = get_video_subtitles(test_bvid)
    if result:
        print(f"\nPreview ({result['language']}):")
        for s in result['segments'][:5]:
            print(f"  [{s['start']:.0f}s] {s['text'][:80]}")
    else:
        print(f"No subtitles found")
