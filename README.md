# 🎬 Hermes Podcast Scraper

**自动抓取 YouTube 和 B站品牌运营播客，下载逐字稿，AI 生成总结分析 — 专为内容创作者打造的自动化知识库工具。**

[![Hermes Skill](https://img.shields.io/badge/Hermes-Skill-8A2BE2)](https://hermes-agent.nousresearch.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![YouTube](https://img.shields.io/badge/Platform-YouTube-red)](https://youtube.com)
[![Bilibili](https://img.shields.io/badge/Platform-Bilibili-00A1D6)](https://bilibili.com)

---

## 🎯 这个技能是什么？

一个**全自动化的内容研究系统**，每天自动搜索 YouTube 和 B站上关于**品牌运营、品牌建设、企业成长**的优质播客/访谈视频，下载完整逐字稿，用 AI 生成结构化的总结分析，存入你的 Obsidian 知识库。

专为**访谈节目主持人（如"程前朋友圈"风格）、内容创作者、自媒体运营者、品牌营销从业者**设计。

### 📄 每篇笔记包含

```markdown
# 视频标题
📋 视频信息（平台/频道/播放量/时长）
📝 完整逐字稿（带 [00:00] 时间戳）
🤖 AI 总结分析
   ├── 核心主题
   ├── 关键观点与金句
   ├── 品牌运营启示
   └── 适合引用场景
```

### 🖼️ 效果预览

```
wiki/来源/播客/
├── 2026-05-14 企业家现状：要么不吭声，要么做网红.md
├── 2026-05-14 专访雷军：穿越30年创业周期.md
├── 2026-05-14 How To Build A Brand ft. Chris Do.md
└── ...（每天自动增长 5-10 篇）
```

---

## 🏗️ 实现路径

### 架构图

```
┌─────────────────┐     ┌──────────────────┐
│  YouTube Scraper │     │  B站 Scraper      │
│  (GitHub Actions) │     │  (WSL Cron Job)   │
│  每日 10:00 运行  │     │  每日 22:00 运行   │
└────────┬────────┘     └────────┬──────────┘
         │                       │
         │  搜索 → 字幕下载 → AI总结  │
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────────┐
│              GitHub 仓库 D-                  │
│         (30分钟自动同步)                       │
└──────────────────┬──────────────────────────┘
                   ▼
         ┌─────────────────┐
         │  Obsidian Vault  │
         │  wiki/来源/播客/  │
         └─────────────────┘
```

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 🔍 **搜索** | yt-dlp + Bilibili API | 中英文关键词搜索品牌运营内容 |
| 📝 **字幕提取** | yt-dlp `--write-auto-subs` | YouTube自动字幕 + B站CC字幕 |
| 🍪 **认证** | Browser cookies | B站字幕需要登录态（Chrome导出） |
| 🤖 **AI 总结** | DeepSeek API | 从逐字稿生成结构化总结 |
| 📂 **存储** | Obsidian Wiki | Markdown + YAML frontmatter |
| ⚡ **定时** | GitHub Actions + WSL Cron | 每日自动运行，零手动 |

### 文件结构

```
scripts/
├── shared/
│   └── summarize.py           # DeepSeek AI 总结模块
├── YouTube/
│   └── scraper.py             # YouTube 搜索+字幕+总结
└── Bilibili/
    └── scraper.py             # B站搜索+字幕+总结

.github/workflows/
└── daily-youtube-scraper.yml  # GitHub Actions 定时任务
```

---

## 🚀 快速开始

### 前置条件

- Python 3.12+
- yt-dlp (`pip install yt-dlp`)
- DeepSeek API Key（[免费获取](https://platform.deepseek.com/)）
- Obsidian Vault（用于存储知识库）
- GitHub 账号（用于 Actions 定时运行）

### 1. 安装 Hermes Skill

```bash
# 在 Hermes Agent 中加载此技能
hermes skill install https://github.com/derrickyang1998/hermes-podcast-scraper
```

或直接下载脚本：

```bash
git clone https://github.com/derrickyang1998/hermes-podcast-scraper.git
cp -r hermes-podcast-scraper/scripts/* /path/to/your/repo/scripts/
```

### 2. 配置环境变量

```bash
# .env 或 GitHub Secrets
export DEEPSEEK_API_KEY="sk-..."          # DeepSeek API Key
export YT_COOKIES="..."                   # YouTube cookies (可选)
export BILI_COOKIES="..."                 # B站 cookies (可选)
```

### 3. 设置定时任务

**B站（WSL Cron）：**
```bash
# 编辑 crontab
crontab -e
# 添加：每天 22:00 运行
0 22 * * * cd /path/to/repo && python3 scripts/Bilibili/scraper.py >> ~/logs/bili-scrape.log 2>&1
```

**YouTube（GitHub Actions）：**
复制 `.github/workflows/daily-youtube-scraper.yml` 到你的仓库，在 GitHub Secrets 中设置 `DEEPSEEK_API_KEY`。

### 4. 导出 B站 Cookies

B站字幕下载需要登录态：

```powershell
# Windows PowerShell（需要 Chrome 已登录 B站）
yt-dlp --cookies-from-browser chrome --cookies bili_cookies.txt
```

---

## 🔧 自定义

### 修改搜索关键词

编辑 `scripts/YouTube/scraper.py` 和 `scripts/Bilibili/scraper.py`：

```python
SEARCH_TOPICS = [
    "品牌运营 创业故事 企业家 深度访谈",
    "品牌建设 品牌营销 增长策略",
    # 添加你的关键词...
]
```

### 更换 AI 模型

编辑 `scripts/shared/summarize.py`：

```python
"model": "deepseek-chat",  # 可换成任何兼容 OpenAI API 的模型
```

### 修改输出格式

编辑 `transcript_to_markdown()` 和 `save_markdown()` 函数调整 Markdown 模板。

---

## 📊 实际效果

部署后每天自动产出：

| 平台 | 每日新增 |
|------|----------|
| YouTube | ~6 个视频 |
| Bilibili | ~4 个视频 |
| **合计/月** | **~300 篇逐字稿+AI总结** |

每篇包含：完整对话逐字稿 + AI 提炼的金句 + 品牌运营洞察 + 适合采访引用的场景分析。

---

## 🤝 适用场景

- 🎙️ **播客/访谈主持人** — 研究嘉宾背景，设计采访大纲
- 📝 **内容创作者** — 获取行业最新观点和案例素材
- 📈 **品牌运营** — 跟踪竞品策略和行业动态
- 🎓 **商业学习** — 建立系统化的品牌知识库

---

## ⚠️ 注意事项

- B站 CC 字幕需要用户登录 cookies
- YouTube 云 IP 可能被限流（建议 50+ 条 cookies）
- DeepSeek API 免费额度：500 requests/day
- 脚本默认不下载视频，只提取字幕和元数据

---

## 📄 License

MIT License — 欢迎 Fork、PR、商用！

---

**🚀 让 AI 帮你每天充实知识库，把时间留给真正重要的创作。**
