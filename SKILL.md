---
name: podcast-content-scraper
description: Automated daily scraping of brand operations/business podcasts from YouTube and Bilibili. Searches, downloads transcripts, saves to Obsidian wiki with timestamps, auto-syncs to GitHub.
---

# Podcast Content Scraper — YouTube & Bilibili

Automated pipeline that searches, downloads transcripts, and indexes podcast/interview content about brand operations (品牌运营), brand building (品牌建设), and business growth (企业成长) from YouTube and Bilibili.

## Architecture

```
scripts/
├── shared/
│   ├── summarize.py            ← AI 总结 (DeepSeek API, key hardcoded)
│   ├── bilibili_subtitle.py    ← B站 WBI 签名字幕下载模块
│   └── export_bili_cookies.ps1 ← PowerShell 一键导出 B站 cookies
├── YouTube/
│   └── scraper.py              ← YouTube 搜索 + yt-dlp字幕 + 总结
└── Bilibili/
    └── scraper.py              ← B站搜索 + WBI/yt-dlp字幕 + 总结
```

```
YouTube (GitHub Actions) ──┐
                            ├──→ GitHub D- repo ──→ Obsidian Vault (D:\主盘)
Bilibili (WSL Cron Job) ───┘
```

## Quick Reference

| Task | From | How |
|------|------|-----|
| YouTube scrape | Push to main | Auto-triggered |
| B站 scrape | WSL | `cd /mnt/d/主盘 && python3 scripts/Bilibili/scraper.py` |
| Export cookies (YT + B站) | Chrome | Install "Get cookies.txt LOCALLY" extension → visit youtube.com → Export → save as `/mnt/d/主盘/cookies.txt` |
| Check cron jobs | WSL | `hermes cron list` |

## B站 Subtitle System (Detailed)

B站 video subtitles come in two forms:

### A: Manual CC subtitles (WBI-signed API)
Available when uploader added subtitles. Accessed via WBI-signed endpoint:
1. `nav` API → extract `img_key` + `sub_key`
2. Compute mixin key via `MIXIN_KEY_ENC_TAB`
3. `wbi/view?bvid=...&wts=...&w_rid=...` → subtitle list with download URLs
4. Download subtitle JSON from CDN URL

Module: `scripts/shared/bilibili_subtitle.py` — tested working on BV1GJ411x7h7 (12 tracks).
Most brand/business videos DO NOT have manual CC. Returns `None` silently.

### B: AI-generated / user-uploaded subtitles (requires login cookies) ✅ WORKING
Available on many videos when accessing via authenticated session.
Use `yt-dlp --cookies cookies.txt --write-subs --write-auto-subs --sub-langs all`.
Tested working on brand videos: "企业家现状" (837 segments), "运营小红书" (572 segments).

**How to get cookies (the reliable way):**
Do NOT use `yt-dlp --cookies-from-browser` — it fails on Windows with DPAPI/encryption issues.
Instead, install Chrome extension "Get cookies.txt LOCALLY" from Chrome Web Store:
1. Visit https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc
2. Click "Add to Chrome"
3. Go to www.bilibili.com (make sure you're logged in)
4. Click the 🟦 cookie icon in address bar → Export
5. The downloaded file is your full browser cookie jar — save it as `/mnt/d/主盘/cookies.txt`
6. **Store as GitHub Secret `BILI_COOKIES`** for Actions, or keep locally for WSL cron

### C: WBI signing implementation
```python
MIXIN_KEY_ENC_TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,...]
wts = int(time.time())
sign_str = query_params_sorted + mixin_key
w_rid = hashlib.md5(sign_str.encode()).hexdigest()
```
Full implementation at `scripts/shared/bilibili_subtitle.py`.

## YouTube Subtitle Debugging Chain

See "Pitfalls → Cookie lifecycle + Debugging" above for consolidated debugging table.

## YouTube Pipeline

### Files
- **Script**: `scripts/YouTube/scraper.py` in D- repo
- **Workflow**: `.github/workflows/daily-youtube-scraper.yml`
- **Shared module**: `scripts/shared/summarize.py` (DeepSeek summarization)
- **Schedule**: Daily at UTC 2AM (Beijing 10AM)

### How it works
1. GitHub Actions triggers on push to main + daily schedule
2. yt-dlp searches YouTube for brand-related content (10 queries, 中英文)
3. Attempts subtitle download via yt-dlp `--write-auto-subs`
4. If subtitles obtained, passes transcript to DeepSeek for AI summary
5. Saves as `wiki/来源/播客/YYYY-MM-DD Title.md` with YAML frontmatter — includes 「逐字稿」section +「视频总结」section
6. Updates `wiki/index.md` and `wiki/log.md`
7. Auto-pushes back to repo

### Environment
- **YT_COOKIES**: GitHub Secret for authenticated subtitle downloads (optional, cookies expire)
- **DEEPSEEK_API_KEY**: GitHub Secret for AI summary generation
- Runs on `ubuntu-latest`, installs yt-dlp + deno

### Current limitation
- Subtitle download requires valid YouTube cookies which expire on browser restart
- Even without subtitles, video metadata is saved for reference

## Bilibili Pipeline

### Files
- **Script**: `scripts/Bilibili/scraper.py` in D- repo
- **Cron**: `~/.hermes/scripts/bilibili-auto-scrape.sh`
- **Shared module**: `scripts/shared/summarize.py` (same as YouTube)
- **Schedule**: Daily at UTC 14:00 (Beijing 22:00)

### How it works (✅ WORKING — May 2026)
1. Hermes cron job runs the shell script
2. Shell script runs `python3 scripts/Bilibili/scraper.py`
3. Searches Bilibili API for brand/business content (5 中文关键词)
4. Downloads CC subtitles via **yt-dlp + cookies** (`--cookies cookies.txt --write-subs --write-auto-subs`)
5. Parses SRT to segments → saves as timed transcript「逐字稿」
6. Generates **DeepSeek AI summary**「视频总结」(核心主题/金句/品牌启示/引用场景)
7. Saves to `wiki/来源/播客/YYYY-MM-DD Title.md`
8. Updates wiki index and log
9. Git pushes to GitHub (30-min sync cron pulls it into Obsidian)

**Key breakthrough**: B站 subtitles require login cookies. Export via Chrome extension → `--cookies cookies.txt` enables full CC download. Tested on BV1yS411F754 (837 segments) and BV1y14y1v7jo (572 segments).

## Output Format — with AI Summary

When transcript is successfully obtained (>200 chars), the page includes an AI summary generated by DeepSeek.

Format:
```yaml
---
type: source
tags: [YouTube/Bilibili, 品牌运营, 逐字稿, zh/en]
sources: [PlatformName]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# Video Title

> Source: [Title](URL) | Channel Name

## Video Info
- **Title**: ...
- **Channel**: ...
- **Views**: N
- **Subtitle Language**: zh/en

## 逐字稿
[00:00] Transcript line 1
[00:05] Transcript line 2
...

## 视频总结

### 核心主题
(2-3 sentences summarizing core theme)

### 关键观点与金句
(3-5 key points, marked as 金句 where applicable)

### 品牌运营启示
(2-3 actionable brand operations insights)

### 适合引用场景
(How to use this content in "D的会客厅" interviews)
```

The AI summary is generated via `scripts/shared/summarize.py` using the DeepSeek API (key hardcoded: `sk-c9c6193443b5464aa4f08b3b24f105a8`). Model: `deepseek-chat`, temperature 0.3, max 1500 tokens. Transcript truncated to ~8000 chars for API limits.

## Search Keywords

### YouTube (EN + CN)
- 品牌运营 创业故事 企业家 深度访谈
- 品牌建设 品牌营销 增长策略  
- business growth brand building podcast interview
- startup scaling brand strategy CEO interview

### Bilibili (CN)
- 品牌运营 深度访谈 企业家
- 品牌建设 创始人对话 创业故事
- 品牌营销 增长策略 企业成长

## Vault Integration

- **Vault**: D:\主盘 (/mnt/d/主盘)
- **Wiki dir**: wiki/来源/播客/
- **Index**: wiki/index.md (auto-updated)
- **Log**: wiki/log.md (auto-updated)
- **Sync**: 30-min cron pushes/pulls to GitHub

## Pitfalls

### YouTube subtitle download chain
When subtitle download fails, diagnose in this order:

| Error | Root Cause | Fix |
|-------|-----------|-----|
| `No supported JavaScript runtime` | yt-dlp needs Node/Deno | Install Deno |
| `n challenge solving failed` | JS runtime not found | `--js-runtimes deno` |
| `Remote components ... skipped` | NPM solver blocked | `--extractor-args youtube:player_client=android,ios` |
| `Skipping client "android" ... cookies` | Mobile clients incompatible with cookies | Remove `--extractor-args` when cookies present |
| `cookies are no longer valid` | Browser cookies expire on restart | Re-export fresh cookies |
| `No subtitle files downloaded` (no error) | Video has no subtitles or cloud IP blocked | Accept metadata-only; check `--list-subs` |

### Cookie lifecycle + Debugging

Browser-exported cookies expire within hours/days. Even files >2000 bytes can be invalid. The script auto-detects `<100 byte` cookie files and removes them.

**Never use `--cookies-from-browser` on Windows.** It fails with DPAPI/encryption errors or locked databases. Chrome extension "Get cookies.txt LOCALLY" is the only reliable method for exporting cookies on this user's machine.

| Error | Platform | Root Cause | Fix |
|-------|----------|-----------|-----|
| `Subtitles only available when logged in` | B站 | Requires auth | Export cookies via Chrome extension |
| `Failed to decrypt with DPAPI` | Windows | yt-dlp can't decrypt Chrome | Use Chrome extension — never debug DPAPI further |
| `Could not copy cookie database` | Windows | Browser running, DB locked | Close browser or use Edge extension |
| B站 412 Precondition Failed | B站 | Rate limiting | Retry with delay |

### GitHub Actions requirements
1. `permissions: contents: write` — required for `GITHUB_TOKEN` to git push
2. Remove `cache: pip` if no `requirements.txt` exists — `actions/setup-python@v5` fails hard
3. Verify cookies file is non-empty before passing to yt-dlp

### Network split (WSL vs Windows)
On WSL, YouTube/Google are often blocked while Windows host can reach them. Use `powershell.exe -Command` to route yt-dlp through Windows.

## Automation Philosophy

> **Zero manual steps.** The user's stated preference: setups and pipelines must run autonomously without requiring them to click buttons, run commands, or manually trigger anything. If a step requires manual intervention (e.g., re-exporting browser cookies), flag it as a bottleneck and propose an automated alternative.

- Cron jobs (`no_agent=True` script mode) for WSL-accessible tasks
- GitHub Actions (push + schedule triggers) for tasks needing non-WSL network access
- The `obsidian-auto-push.sh` 30-min cron bridges GitHub ↔ Obsidian automatically
- All outputs land in `wiki/来源/播客/` without user action

## Deepgram Audio Fallback (planned)

When neither CC subtitles nor auto-generated captions are available:
1. yt-dlp downloads audio only (`--extract-audio --audio-format mp3`)
2. Deepgram API transcribes the audio (200h/mo free tier: key `85eb8fdf...`)
3. Transcript saved with timestamps
4. DeepSeek generates AI summary from transcript

The `deepgram-audio-transcription` skill provides the transcription pipeline integration.
