#!/usr/bin/env python3
"""
Shared module: AI-powered transcript summarization via DeepSeek API.
Used by both YouTube and Bilibili scrapers.
"""

import json
import urllib.request
import os

DEEPSEEK_API_KEY = os.environ.get(
    "DEEPSEEK_API_KEY", 
    "sk-c9c6193443b5464aa4f08b3b24f105a8"
)

def summarize_transcript(title, channel, transcript_text):
    """
    Summarize a transcript using DeepSeek API.
    Returns a structured markdown summary section.
    """
    if not transcript_text or len(transcript_text) < 200:
        return None
    
    # Truncate to ~8000 chars for API limits
    text = transcript_text[:8000]
    
    prompt = f"""你是一个专业的内容分析助手。请根据以下播客/访谈视频的逐字稿，生成一份结构化的中文总结分析。

视频标题：{title}
频道：{channel}

请按以下格式输出：

## 视频总结

### 核心主题
（2-3句话概括这期视频围绕的核心主题是什么）

### 关键观点与金句
（列出3-5个嘉宾的核心观点，每个用一句话概括，标注是否是金句）

### 品牌运营启示
（这期内容对品牌运营、品牌建设有什么实用的启发？列出2-3条）

### 适合引用场景
（这期内容适合用在我访谈节目"D的会客厅"的什么场景？例如：开场破冰、品牌建设话题、创业故事等）

---
逐字稿内容：
{text}

请直接输出上述格式的内容，不要额外解释。"""

    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps({
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个专业的内容分析助手，擅长从访谈和播客内容中提炼核心观点和实用洞察。输出简洁、结构化、有洞察力的中文总结。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1500,
        }).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
        method="POST"
    )
    
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        data = json.loads(resp.read())
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"    Summary API error: {e}")
        return None
