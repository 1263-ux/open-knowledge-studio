# 平台反爬、轻量化部署与用户交互研究

日期：2026-08-02
状态：`active`
版本：v3 — 实验验证版（实测数据已同步）

目的：围绕 OKS 的三个核心目标——**部署轻量化、知识提取能力提升、用户交互体验优化**——给出可落地的方案和建议。反爬边界定义约束条件，不投入研发资源对抗。

---

## 一、OKS 当前状态（代码层面）

### 1.1 已具备的能力

经过代码审查，OKS 实际已经比文档描述的更完善：

**提取器层（5 个 + 路由）：**

| 提取器 | 命令 | 能力 | 依赖 |
|--------|------|------|------|
| `watch` | `oks-connector watch` | 视频/音频 → 平台字幕采集 → 本地 ASR (faster-whisper) → 场景检测 → 关键帧 → RapidOCR | yt-dlp, ffmpeg, faster-whisper, PySceneDetect, Pillow, av |
| `markitdown` | `oks-connector markitdown` | 办公文档 (docx/pptx/xlsx/html/csv/md) → Markdown | markitdown |
| `mineru` | `oks-connector mineru` | PDF → 文本+版面+公式+OCR | MinerU v3.4 |
| `web` | `oks-connector` (web.py) | 公开网页 → Trafilatura 提取 + Markdown + HTML 快照 | trafilatura, requests |
| `image` | `oks-connector image` | 图片 → RapidOCR | rapidocr |

**能力按需安装系统（`capability_check.py`）：**
```
oks capability install watch     # 视频/音频提取
oks capability install document  # 办公文档
oks capability install pdf       # PDF 提取
oks capability install formula   # 公式 OCR
oks capability install feishu    # 飞书集成
```

**路由系统（`route.py`）：** 自动检测来源类型（URL vs 本地文件，平台识别，扩展名检测），分派对应提取器。当前支持 YouTube、Bilibili、抖音的 URL 路由。

**两条用户路径已跑通：**
- **Agent 路径**：`/ingest` skill → `oks ingest` → `oks-connector` → Raw Bundle → `/promote` → Wiki
- **飞书路径**：飞书 Base 表单 → `feishu_base_worker.py` → CI worker → review → Raw Bundle

### 1.2 当前依赖的实际重量

从 `raw-tools.json` 可以看到当前部署：

```json
{
  "watch_python": "D:/.../watch-venv/Scripts/python.exe",    // faster-whisper + RapidOCR + yt-dlp
  "document_python": "D:/.../.venv/Scripts/python.exe",       // markitdown
  "mineru_python": "D:/.../mineru-venv/Scripts/python.exe",   // MinerU (最重)
  "formula_python": "D:/.../paddle-formula-venv/Scripts/python.exe", // PaddleOCR
  "ffmpeg": "C:/.../ffmpeg.exe",
  "ffprobe": "C:/.../ffprobe.exe"
}
```

**5 个独立 Python venv + ffmpeg**，这是当前"重"的来源。但架构已经做到 isolation——每个提取器独立 venv，互不污染。

---

## 二、竞品能力边界：什么不该重复造

### 2.1 AI 记忆系统竞争格局

2026 年各主流工具的知识管理现状（深度调查修正版）：

| 能力 | Claude Code | Codex | WorkBuddy | Qwen Code/Qoder | Amazon Q | Perplexity |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| 自动跨会话记忆 | ✅ Auto Dream | ✅ 即时保存 | ✅ 三层记忆 | ✅ Dream+Recall | ❌ 静态分析 | ✅ Brain |
| 团队共享 | ✅ 项目级 | ❌ | ✅ IMA KB | ✅ git | ✅ 审查共享 | ❌ |
| LLM Wiki | ✅ 第三方生态活跃 | ✅ 第三方 | ✅ 内置 | ❌ | ❌ | ❌ |
| raw→draft→wiki 闭环 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 人工审核门控 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 知识衰减 | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 证据溯源 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ 有溯源 |

**关键修正：**
- Claude Code Auto Dream 是 **24h + 5会话触发**，不是实时。Managed Agents Memory API (2026-07-22 beta) 已接近 wiki 模式
- Claude Code 第三方 wiki 生态比预期的丰富得多：claude-mem (83.9K stars)、llm-wiki-plugin、KIOKU、Swarmvault、llm-wiki-memory（有审核门！）、Link（审计日志 + hash chain）
- Perplexity Brain (2026-06-18) 已实现 overnight synthesis + 溯源——需要密切关注
- ChatGPT Dreaming V3 (2026-06-04) 自动后台合成 + 时间感知
- 报告原列的 "Vir" 和 "CAMP" **不存在**
- Amazon Q Memory Bank 是**静态代码库分析摘要**，不是学习型记忆
- Qwen Code 没有 Repo Wiki（Repo Wiki 属于 **Qoder IDE**，不同产品）
- WorkBuddy 的记忆系统比报告描述的更成熟：5 类长期记忆 + 每日日志 + 30 天提炼机制

### 2.2 成熟工具生态：OKS 的下游

这些工具已经解决了采集问题，OKS 不需要重复造轮子：

| 工具 | 覆盖 | 状态 | OKS 集成方式 |
|------|------|------|------------|
| yt-dlp | 1800+ 站点 | 活跃（v2026.07.21） | `oks-connector watch` 已集成 |
| Firecrawl | 网页抓取+JS渲染 | 活跃，500页/月免费 | API Key → 本地 Raw Bundle |
| **MediaCrawler** | **小红书/抖音/快手/B站/微博/贴吧/知乎** | **59.4K stars, 活跃** | **子进程→API包装→库复用** |
| Playwright | 浏览器自动化 | 活跃 | Agent 直接调用 |
| Deepgram/Groq/腾讯云 | ASR | 商用 API | 远程替代本地 Whisper |
| LlamaParse/Firecrawl Fire-PDF | PDF 解析 | 商用 API | 远程替代 MinerU |

---

## 三、MediaCrawler：中文社交平台采集的突破口

### 3.1 基本信息

| 维度 | 详情 |
|------|------|
| 仓库 | NanmiCoder/MediaCrawler (59.4K stars, 11.7K forks) |
| 许可证 | **Apache-2.0**（允许商业使用和子许可） |
| 技术栈 | Python + Playwright + Node.js（知乎/抖音签名用） |
| 维护状态 | 活跃，最后推送 2026-07 |
| 平台覆盖 | 小红书、抖音、快手、B站、微博、贴吧、知乎（7 平台） |
| 采集模式 | 关键词搜索 / 帖子详情 / 创作者主页 / 评论（含二级回复） |
| 导出格式 | CSV, JSON, JSONL, Excel, SQLite, MySQL |
| 反爬策略 | CDP 模式连接真实 Chrome（复用 Cookie+指纹）+ 备用 Playwright + IP 代理池 + 登录态缓存 |
| GPU 依赖 | **无**（纯 CPU） |
| Docker | 无官方镜像（Chrome CDP 模式难以容器化） |

### 3.2 关键反爬洞察

MediaCrawler 的反爬策略是 **"不要逆向，要复用"**：
- 通过 Chrome DevTools Protocol (CDP) 连接用户的**真实 Chrome**，复现完整的浏览器环境（Cookie、扩展、TLS 指纹）
- 签名参数通过 `pyexecjs` 在浏览器 JS 上下文中动态提取，不硬编码逆向算法
- 这意味着**不需要维护单独的指纹伪装栈**，但需要用户有 Chrome 且扫码登录

### 3.3 法律风险

- Apache-2.0 许可，但 README 有免责声明（"仅供学习参考，禁止商用"——与许可条款有矛盾）
- 2025-05 小红书 vs 蝉妈妈案：法院裁定抓取小红书数据构成不正当竞争（赔偿 490 万元）
- 2025-03 常州案：3 人因爬取小红书用户数据获刑（缓刑 3-5 年，罚金+没收 653 万元）
- **OKS 如果集成 MediaCrawler，需要：** 仅采集公开内容、控制频率、明确非商业研究用途、咨询法律顾问

### 3.4 集成路径

```
阶段一（原型验证）: Fork MediaCrawler → 子进程调用 → 选 1-2 个平台
阶段二（正式集成）: 扩展 api/main.py → REST 微服务 → HTTP 接入 OKS
阶段三（生产加固）: 跟踪上游更新 → 速率控制 → 失败重试 → 监控
```

---

## 四、平台反爬边界与绕过策略

### 4.1 分平台速查（更新版）

| 平台 | 技术可行性 | 法律安全性 | 推荐方案 | 硬边界 |
|------|:---:|:---:|---|---|
| YouTube | 中-高 | **低** | yt-dlp --skip-download（只取元数据+字幕） | DRM 视频、Premium 专享 |
| Bilibili | 中 | **低** | yt-dlp（⚠️ bilibili-api-python 已于 2026-07-06 永久关停） | 付费课程 DRM |
| 小红书 | 低-中 | **极低** | MediaCrawler CDP 模式 / 用户浏览器扩展采集 | 个人数据、大规模抓取 |
| 抖音 | 低 | **极低** | MediaCrawler / 用户手动分享链接 | 签名对抗、账号封禁 |
| 微信公众号 | 中 | **极低** | RSS 桥接 / 浏览器扩展导出 Markdown | 版权+个人信息 |
| 知乎 | 中 | 低 | MediaCrawler（需 Node.js 签名） | 用户内容版权 |
| 微博 | 中 | 低 | MediaCrawler / 公开 API | 用户隐私 |
| 学术论文 | **高** | **高** | **OpenAlex (CC0, 2.5 亿论文)** → arXiv → Semantic Scholar | 付费出版商 |
| 普通网页（英文） | 高 | 高 | Firecrawl API（实测 50KB+ Markdown 提取） | 硬付费墙 |
| 普通网页（中文） | 中-高 | 高 | Trafilatura 本地（⚠️ Firecrawl 对知乎/CSDN/掘金实测全挂） | 硬付费墙 |

**实测数据（2026-08-02）：**
- Firecrawl 英文博客：✅ 50,838 chars，内容完整
- Firecrawl arXiv PDF：✅ 37,727 chars，Attention Is All You Need 全文正确
- Firecrawl 知乎：❌ 151 chars（反爬页面，乱码）
- Firecrawl CSDN：❌ 超时
- Firecrawl 掘金：❌ 26 chars（几乎空返回）
- **结论：Firecrawl 中文平台不可用。中文网页走本地 Trafilatura + 用户手动 Markdown 兜底。**

### 4.2 绕过策略总则

```
核心原则：不在反爬对抗上投入研发资源。
如果一条路径太难，设计替代路径，而不是硬刚。
```

| 原始目标 | 障碍 | 绕过路径 | 质量损失 |
|----------|------|----------|----------|
| YouTube 视频下载 | PO Token + IP 封锁 | **只取元数据+字幕**（`--skip-download`） | 无视频文件 |
| YouTube 字幕 | IP 封锁 | TranscriptAPI SaaS 中转 | 需付费 |
| Bilibili 字幕 | API 库关停 | BibiGPT API / 直接写 yt-dlp Cookie | 需付费/需登录 |
| 小红书内容 | 极强反爬 | **用户浏览器扩展采集** → 导出 → OKS 摄入 | 依赖用户操作 |
| 抖音视频 | 签名+反爬 | 用户手动分享链接 → 仅摄入可公开访问信息 | 内容不完整 |
| DRM 内容 | 硬边界 | **不下载，仅采集元数据+公开描述+评论** | 无音视频 |
| 需登录平台 | Cookie 风险 | **用户在自己浏览器中操作 → 扩展导出 → OKS** | 依赖用户 |

### 4.3 法律环境关键更新

- **Google v. SerpApi**：2026-07-20 DMCA 索赔被驳回（积极），但允许 8/10 前修改重诉
- **中国 GB/T 45652-2025**：AI 训练数据必须标注来源 URL/数据集/组织
- **EU AI Act**：2026-08-02 全面执行。robots.txt 在 EU 下有法律效力
- **EDPB GenAI 网络抓取指南**：2026-07-07 发布草案
- 社交媒体商业 API 几乎不可用：X API $0.005/条 + $42K+/月 Enterprise；Reddit ~$12K/月起；YouTube 100 次搜索/天硬上限

---

## 五、提取器依赖精简

### 5.1 ASR 选型修正

原报告推荐 Deepgram 为最便宜——**错误**。

| 方案 | 批量价格 | 中文能力 | 推荐场景 |
|------|---------|----------|----------|
| **Groq whisper-large-v3-turbo** | **$0.04/h** | 一般 | 英文批量最便宜，2000 次/天免费 |
| Groq whisper-large-v3 | $0.111/h | 一般 | 英文高精度 |
| OpenAI GPT-4o-mini-transcribe | $0.18/h | 多语言 | 综合性价比 |
| Deepgram Nova-3 | $0.26/h | 一般 | 低延迟流式 |
| **腾讯云 TRTC 语音转文本 2.0** | ~$0.11/h | **最佳** | 中文场景首选 |
| 自托管 faster-whisper | $0 + GPU | 取决于模型 | 月均>15h 音频才划算 |

**实测数据（2026-08-02，12 秒中文音频片段）：**

| 后端 | 延迟 | 12s 成本 | 转录结果 |
|------|:--:|------|------|
| **OpenAI whisper-1** | 2.3s | $0.0012 | "请不吝点赞 订阅 转发 打赏支持明镜与点点栏目" ✅ 正确 |
| OpenAI gpt-4o-mini-transcribe | 1.0s | $0.0006 | "AI技术在其中的应用,如自动司机,比如自动洗车。" ⚠️ 疑似幻觉（与 whisper-1 内容不同） |
| 本地 faster-whisper base | ~5s | $0 | 需要 2GB 模型下载 |

**结论：推荐 OpenAI whisper-1（$0.006/min），质量可靠。** mini-transcribe 更快更便宜但疑似对同一音频产生了不相关内容。本地模型性价比仅在月处理 >15h 音频时才有优势。

### 5.2 PDF 解析方案修正（⭐ 实测更新）

**实测数据（arXiv 1706.03762 "Attention Is All You Need"，2.2MB PDF）：**

| 指标 | MinerU (2.4GB) | pymupdf4llm (~20MB) | 判定 |
|------|:---:|:---:|------|
| 处理时间 | ~30s | **9.23s** | pymupdf4llm 快 3x |
| 输出字符 | 42,779 | 41,803 | 等价 (差距 < 3%) |
| 章节识别 | 完整 | 完整 (27 标题) | 等价 |
| 表格 | 25 个 ✅ | 25 个 ✅ | 等价 |
| 图片 | PNG assets ✅ | 丢失 ❌ | MinerU 胜 |
| LaTeX | 保留 ✅ | 文本可读但格式丢失 ⚠️ | MinerU 胜 |
| **体积** | 2.4GB | **~20MB** | **pymupdf4llm 小 120x** |

**推荐分层（← 实测修正）：**
```
文本型学术 PDF → pymupdf4llm (9s, 20MB, 等价质量, 零成本) ← P0 首选
扫描/图片重 PDF → Firecrawl Fire-PDF (远程, 智能分页, 免费额度内)
中文复杂 PDF → MinerU v3.4 (本地, 需 2.4GB, 仅必要时安装)
```

### 5.3 n8n 编排层——镜像大小修正

原报告称 n8n "150MB Docker 镜像"——**错误**。

| 指标 | 实际值 |
|------|--------|
| 压缩后 | 360MB (n8nio/n8n:next) |
| 解压后 | 1.2GB+ |
| 运行时内存 | 推荐 4GB+ |
| 生产数据库 | 需要 PostgreSQL |

### 5.4 最小 POC 依赖（修正后）

```
# 本地（Docker 镜像约 200-300MB 压缩）
Python 3.12-slim
yt-dlp (元数据+字幕，不下载视频)
pymupdf4llm (文本型 PDF)
requests + beautifulsoup4 (简单网页)

# 远程 API
Groq Whisper ($0.04/h) 或 腾讯云 TRTC ($0.11/h) → ASR
Firecrawl ($16/月) → JS 渲染网页
OpenAI/Anthropic/Kimi API → LLM 蒸馏
OpenAlex API → 学术论文（完全免费、CC0）
```

### 5.5 实测 Level C 依赖清单

基于实验 1.1 的逐层拆除结果，**Level C（拆 ASR + 拆 PDF 重型解析 + 拆浏览器 + 拆公式 OCR）已可达**：

```
✅ 保留（本地 ~73MB）:
  Python 3.12+          ← 运行环境
  yt-dlp (~3MB)         ← 1800+ 站点元数据+字幕，无远程替代
  markitdown (~50MB)    ← 办公文档 (docx/pptx/xlsx/html)
  pymupdf4llm (~20MB)   ← 文本型 PDF，实测等价 MinerU 质量

❌ 已拆（远程化）:
  faster-whisper (~2GB)     → OpenAI whisper-1 $0.006/min ✅ 已验证
  MinerU (~2.4GB)            → pymupdf4llm 覆盖文本 PDF + Firecrawl 覆盖扫描 PDF ✅ 已验证
  PaddleOCR formula (~865MB) → P0 不需要
  Playwright (~300MB)        → Firecrawl API（⚠️ 中文网站不行，需 Trafilatura 本地兜底）

⏳ 待确认:
  ffmpeg (~80MB)             → yt-dlp --skip-download 是否强制依赖？大概率可拆
```

**最终结论：Level C 本地 50-100MB 是已验证可达的目标。**

### 5.6 E2E 闭环验证（⭐ 2026-08-02 实测）

完整链路已跑通——Source → Raw → Draft → Human Promote → Wiki → Recall 首条命中：

```
1. Source     Markdown 文章："AI Agent Memory Systems in 2026"
2. Raw        oks ingest --mode quick → ✅ Raw Bundle (ok 状态)
3. Draft      Agent 蒸馏 → drafts/agent-memory-gap-2026.md
4. Promote    oks drafts promote → ✅ Wiki page (score=0.70, tier=hot)
5. Recall     oks recall "human review gate agent memory" → 🥇 首条命中！

召回评分分解 (--explain):
  token-overlap: 3     ← 关键词匹配
  type:concept x0.6    ← 概念类型加权
  memory-score         ← 记忆曲线评分
  goal-area:computing  ← 目标领域提升
  最终 relevance: 2.05 ← 显著高于其他页面 (1.82, 1.51)
```

### 5.7 当前工具链状态

| 工具 | 用途 | 状态 |
|------|------|:--:|
| Firecrawl API (fc-...) | 英文网页+PDF抓取 | ✅ 已验证 |
| OpenAI API (sk-...) | ASR + Vision + LLM蒸馏 | ✅ 已验证 |
| pymupdf4llm v1.28 | 轻量PDF解析 | ✅ 已验证 |
| vision skill (xiincs) | 截图分析 (gpt-4o) | ✅ 已验证 |
| 千问 API (sk-...) | 中文视觉（更便宜） | ⚠️ DashScope 端点超时，待排查 |
| yt-dlp v2026.07.04 | 视频站点提取 | ✅ 已安装（YouTube 被网络阻断待测） |
| oks 0.3.0 (pipx) | 核心 CLI | ✅ 已安装 |
| 飞书 Base | 采集表单+审批流 | ⚠️ Bot ready, User token 已刷新，表单分享链接待生成 |

---

## 六、部署轻量化方案

### 6.1 推荐的多层安装策略

对标 OpenClaw skill metadata、pip extras、yt-dlp 单二进制分发、Bun 零依赖安装的业界最佳实践：

```
第 0 层：核心 CLI (~5MB, 永远必装)
  pipx install open-knowledge-studio
  → 包含 CLI 框架、配置管理、远程 API 客户端、依赖解析器

第 1 层：纯 Python 可选依赖 (pip extras)
  pip install oks[video,audio,browser]
  → yt-dlp (3MB), openai-whisper, faster-whisper, playwright

第 2 层：系统级依赖 (oks capability install)
  oks capability install watch     → 自动检测平台，安装 ffmpeg
  oks capability install pdf       → 安装 MinerU + PaddleOCR
  → 封装为 Docker sidecar 或 Nix devShell

第 3 层：模型数据 (首次使用时自动下载)
  ~/.cache/oks/models/
  ├── whisper-base.ggml    (~140MB)
  ├── whisper-large.ggml   (~3GB, 显式请求)
  └── tessdata/            (按语言按需)
  → 参考 whisper.cpp / llamafile 的模型缓存模式

第 4 层：远程 API (零本地安装)
  export OKS_REMOTE_MODE=1
  oks transcribe audio.mp3  → 自动使用 Groq/腾讯云 API
```

### 6.2 远程 Fallback 链 (核心降级引擎)

对标 AgentOS `FallbackSTTProxy` 和 Factory CLI 的多 provider 自动切换：

```python
# 降级链配置 (~/.oks/config.yaml)
backends:
  transcription:
    chain:
      - name: platform-captions       # 0. 平台字幕（最快最轻）
        method: yt-dlp --skip-download --write-subs
      - name: local-whisper-cpp       # 1. 本地轻量 (~2MB binary + 140MB model)
        package: whisper-cpp
        model: base
      - name: local-faster-whisper    # 2. 本地 GPU 高精度
        package: faster-whisper
        model: large-v3
        min_vram_mb: 4096
      - name: groq-whisper            # 3. 远程最快 ($0.04/h)
        env_key: GROQ_API_KEY
        free_tier_daily: 2000
      - name: openai-whisper          # 4. 远程备选 ($0.18-0.36/h)
        env_key: OPENAI_API_KEY

  ocr:
    chain:
      - name: pymupdf4llm-native     # 0. 文本型PDF直接提取
      - name: firecrawl-fire-pdf      # 1. 远程智能分页OCR
        env_key: FIRECRAWL_API_KEY
      - name: mineru                  # 2. 本地完整PDF解析
        package: mineru

  browser:
    chain:
      - name: firecrawl-api          # 0. 远程JS渲染（500页/月免费）
      - name: playwright-local        # 1. 本地Chromium (~300MB)
```

**核心退化逻辑：**
1. 优先尝试零依赖方案（平台字幕 / 远程 API / 纯文本提取）
2. 失败后逐级降级到本地重依赖
3. 本地也失败 → 标记为 `restricted`，记录证据链
4. 用户始终可以用 `--local` 或 `--remote` 显式选择

### 6.3 对当前 OKS 架构的具体优化建议

**当前状态（已在 work）：**
- `oks capability install` 已实现按需安装
- 5 个独立 venv 已做到隔离
- `route.py` 已做来源类型检测

**短期可改进（参考 OpenClaw metadata 规范）：**

```yaml
# 每个提取器的 SKILL.md frontmatter 中声明依赖
---
name: watch
description: Video/audio extraction with ASR, scene detection, OCR
version: 1.0.0

metadata:
  oks:
    requires:
      bins: [ffmpeg, ffprobe]
      anyBins: [whisper-cpp, whisper, faster-whisper]

    install:
      - kind: uv
        package: yt-dlp
      - kind: uv
        package: faster-whisper
      - kind: system
        formula: ffmpeg
        linux_pkg: ffmpeg

    fallback:
      local_first: true
      remote:
        - provider: groq
          model: whisper-large-v3
          env_key: GROQ_API_KEY
          cost_per_hour: 0.04
        - provider: tencent-trtc
          env_key: TENCENT_TRTC_KEY
          cost_per_hour: 0.11
---
```

**中期可改进：**
- 单二进制分发（PyInstaller/Nuitka → 约 10-30MB）+ 模型按需下载
- Docker 分层镜像：核心 200MB + video sidecar 500MB + full 2GB
- n8n webhook 替代部分飞书 CI 编排
- Devbox/Nix 声明式环境用于可复现的完整安装

### 6.4 各方案对比

| 方案 | 适合用户 | 本地大小 | 上手难度 |
|------|---------|---------|---------|
| `pipx install oks` (核心) | Python 开发者 | ~20MB | 低 |
| `pipx inject oks yt-dlp` (逐步扩展) | 需要额外能力 | + 按需 | 低 |
| `nix develop github:org/oks` (声明式) | 追求可复现 | 首次 ~2GB | 高 |
| Docker 分层镜像 | CI/CD 和生产 | 核心 200MB | 中 |
| GitHub Codespaces 一键 | 零安装体验 | 云端 | 极低 |
| `export OKS_REMOTE_MODE=1` | 零本地依赖 | 0 | 极低 |

---

## 七、用户交互体验优化

### 7.1 核心洞察

**CLI 本身不适合非技术用户，但 OKS 不需要让非技术用户用 CLI。**

正确的架构：
- **CLI** = 管理员/技术用户的配置入口（`oks init`, `oks watch`, `oks capability install`）
- **浏览器扩展/Watch Folder/Bot** = 普通用户的日常使用入口
- 技术用户配置好 Workspace 后，普通用户不需要打开终端

### 7.2 推荐的多入口架构

```
用户在哪里遇到内容，就在哪里完成采集：

浏览器里看文章     → 浏览器扩展一键保存
手机 APP 里看到    → Share Sheet 分享到 OKS
微信里看到文章     → 转发到 OKS 小程序/bot
本地有文件想入库   → 扔进 Inbox 文件夹
群里有人分享链接   → @bot 转发
脑子里有想法       → 给 Bot 发消息
其他地方           → 复制链接发给 Bot（最低摩擦兜底）
```

### 7.3 分阶段实施建议

**第一步（已实现）：Agent 和飞书路径**

两条路径已跑通，当前即可用。

**第二步（立即可做）：Watch Folder**

```bash
# 用户只需这一条命令，零认知负担
oks watch ~/Knowledge/Inbox

# 把任何文件扔进去 → 自动 ingest → Agent 处理 → Drafts → 人工审核 → Wiki
```

这是最低摩擦的新入口。对标 Hazel ($42 Mac 独占) 的理念，但 AI 驱动。

**第三步（短期，最高 ROI）：浏览器扩展**

对标 Obsidian Web Clipper 的模板系统 + Cubox 的网页标注体验：
- 看到任何网页 → 点击图标 → 自动解析为 Markdown
- 在网页上直接高亮/标注 → 随内容一起保存
- 一键写入 OKS workspace 的 `raw/` 目录
- 可配置：(a) 本地 HTTP 服务模式（localhost:PORT），(b) 直接写文件系统，(c) 通过 n8n webhook

这应该是 OKS 采集端的**旗舰功能**。

**第四步（中期）：飞书/Telegram Bot**

对标 SaveDay Bot 和 OpenClaw 的聊天交互：
```
@oks_bot https://bilibili.com/video/BV1xxx  → 自动采集 → AI 摘要 → 入库
@oks_bot "我上周存的关于 RAG 的文章在哪？" → 检索 → 返回结果
```

OKS CONSTITUTION 已经提到 OpenClaw Skill Hub 集成——可以直接复用 OpenClaw 的飞书/Telegram 连接器。

**第五步（长期）：微信小程序 + Email Drop**

---

## 八、飞书 CI 决策框架

飞书 CI 由 `scripts/feishu_base_worker.py`（2,384 行）驱动，架构上被设计为完全可选扩展。

| 场景 | 建议 |
|------|------|
| 闭环跑不通/效率极低 | 砍掉飞书 CI 代码，用 cron + n8n 替代 |
| 闭环跑通但飞书 CI 是瓶颈 | 保留飞书仅做通知，用 n8n 编排 |
| 闭环跑通且飞书 CI 良好 | 保留并深化 |

当前状态：两条路径都已跑通。在闭环验证完成前，不投入更多精力在飞书 CI 上。

---

## 九、实验设计：回答三个核心问题

> 不追求全覆盖。聚焦三个决定性问题的验证。
> 每个实验都有明确的 go/no-go 阈值。到阈值就决策，不为完美数据拖延。

---

### 问题一：核心部署依赖到底能降到多少？

**要验证的不是估计值，而是实测值。**

#### 实验 1.1：依赖逐层拆除测试

从当前"全装"状态出发，逐步拆除依赖，每拆一层验证还能不能跑通核心闭环。

```
拆除顺序（从最重到最轻）:

Level 全装:    Python + pipx + oks + yt-dlp + ffmpeg + faster-whisper + MinerU + Playwright + PaddleOCR
               → 当前状态 (~3-5GB)

Level A:       拆 PaddleOCR（formula 能力离线，不影响核心链路）
               → 预计减 ~500MB

Level B:       拆 MinerU（PDF 走 pymupdf4llm 本地 + Firecrawl Fire-PDF 远程兜底）
               → 预计再减 ~3GB

Level C:       拆 faster-whisper（ASR 全部走 Groq/腾讯云远程）
               → 预计再减 ~2GB

Level D:       拆 Playwright+Chromium（浏览器渲染全部走 Firecrawl API）
               → 预计再减 ~300MB

Level E:       拆 ffmpeg（不做本地音视频转码，转码走远程 API 或者只采字幕不采音频）
               → 预计再减 ~80MB

Level 最小:    Python + pipx + oks + yt-dlp + pymupdf4llm
               → 只剩 ~50-100MB
```

**实验方法：**

对每个 Level，运行同一条测试链路：

```bash
# 测试内容：3 种典型来源
#   (a) Bilibili 视频 URL: https://www.bilibili.com/video/BV1GJ411x7h7
#   (b) arXiv 论文 PDF: https://arxiv.org/pdf/1706.03762
#   (c) 公开技术文章 URL: https://lilianweng.github.io/posts/2023-06-23-agent/

# 1. 安装该 Level 的依赖
# 2. 对每个来源执行 oks ingest
# 3. 记录: 是否成功生成 Raw Bundle？缺失了什么？
# 4. 记录: 失败是因为缺少哪个被拆除的依赖？
```

**Go/No-Go 阈值：**

| Level | 判定 | 条件 |
|-------|------|------|
| Level C (拆 ASR) | **Go** | 3 个来源中 ≥ 2 个成功生成 Raw Bundle；Groq 或腾讯云 API 可接受 |
| Level D (拆浏览器) | **Go** | Firecrawl API 能覆盖 JS 渲染页面（含 Bilibili 页面信息提取） |
| Level E (拆 ffmpeg) | **需判断** | 如果 yt-dlp --skip-download 不需要 ffmpeg（仅提取元数据和字幕），就拆；否则保留 |
| Level 最小 | **最终目标** | 仅剩 Python + yt-dlp + pymupdf4llm，所有重活走远程 |

**输出物：** `experiments/dependency-strip-{date}.md` —— 每个 Level 的实测依赖大小 + 测试结果矩阵

**预估时长：** 2 小时（大部分时间在安装/卸载和等待 API 响应）

---

### 问题二：通过 API 部署调用的方式是否可行？

**不是"能调用"，而是"调用之后链路还能不能跑通"。**

#### 实验 2.1：API 端到端替换验证

对当前的 5 种提取能力，逐一验证远程 API 能否替代本地重依赖。

```bash
# === 准备好 API Key ===
export GROQ_API_KEY="gsk_..."
export FIRECRAWL_API_KEY="fc-..."
export OPENAI_API_KEY="sk-..."
export TENCENT_SECRET_ID="..."    # 腾讯云 TRTC，如果需要中文 ASR
export TENCENT_SECRET_KEY="..."

# === 测试 1: 网页 → 最直接 ===
oks ingest "https://lilianweng.github.io/posts/2023-06-23-agent/"
# 预期：直接走 Trafilatura 本地提取（无重依赖），最简单

# === 测试 2: 视频 URL → 关键测试 ===
# 当前: oks-connector watch → yt-dlp 下载 → ffprobe → faster-whisper ASR → RapidOCR
# 目标: yt-dlp 只取元数据和字幕 → 如果无字幕，音频发 Groq → 视觉层跳过（仅 transcript_only 模式）
oks ingest "https://www.youtube.com/watch?v=sznAe4rJkOM" --mode quick
# 关键指标: (a) 能拿到字幕或转录吗？(b) 没有 ffmpeg 时 yt-dlp 能否独立工作？

# === 测试 3: 本地 MP4 → 关键测试 ===
# 当前需要: ffprobe + faster-whisper + PySceneDetect + RapidOCR
# 目标: 用 av (PyAV) 做轻量 probe → 音频轨道提取 → Groq/腾讯云 ASR → 跳过 OCR（标记 pending）
cd test-assets/
oks ingest ./meeting-recording.mp4 --mode quick --transcript-only
# 关键指标: (a) 去掉 faster-whisper 后，远程 API 延迟和成本是否可接受？
#           (b) 中文转录准确率 vs 本地 faster-whisper？

# === 测试 4: PDF → 关键测试 ===
# 当前: MinerU（~3GB）
# 目标: pymupdf4llm（~20MB, 纯文本型PDF）+ Firecrawl /parse（扫描型兜底）
oks ingest "https://arxiv.org/pdf/1706.03762"  # 数字 PDF → 应走 pymupdf4llm
oks ingest ./scanned-chinese-contract.pdf      # 扫描中文 PDF → 应尝试 Firecrawl Fire-PDF
# 关键指标: (a) pymupdf4llm 能处理多少比例的真实 PDF？
#           (b) Firecrawl /parse 中文扫描件的准确率？

# === 测试 5: 图片 → 最轻 ===
# 当前: RapidOCR
# 目标: 远程视觉模型 API（GPT-4o / Claude 直接读图）或保持 RapidOCR（已经是纯 CPU 轻量）
oks ingest ./whiteboard-photo.jpg
# 关键指标: 远程视觉模型 vs 本地 OCR 的成本/质量对比
```

**Go/No-Go 阈值：**

| 提取能力 | Go 条件 | No-Go 条件 |
|----------|---------|------------|
| 网页 | Trafilatura 对英文技术博客成功 | —（几乎不可能失败） |
| 视频 URL (有字幕) | yt-dlp 不带 ffmpeg 也能拿到字幕文本 | yt-dlp 强制要求 ffmpeg 才能工作 |
| 视频 URL (无字幕) | Groq ASR 转录质量可理解（人工读一遍能懂 > 80%） | 转录结果是乱码或成本不可接受（> $0.50/视频） |
| 本地 MP4/音频 | 远程 ASR + PyAV probe 替代 ffprobe | ffprobe 不可替代，或远程 ASR 延迟 > 音频时长 |
| 数字 PDF | pymupdf4llm 正确提取文本+表格 | 大部分 PDF 走 pymupdf4llm 后内容缺失 > 30% |
| 扫描/中文 PDF | Firecrawl /parse 结果可读 | Firecrawl 中文识别准确率 < 60% |

**输出物：** `experiments/api-replacement-matrix-{date}.md` —— 5 种能力 × 本地 vs 远程的对比矩阵

**预估时长：** 3 小时

#### 实验 2.2：成本核算

基于实验 2.1 的结果，计算三种使用模式的月度成本：

```python
# 假设用户行为（月度）:
# - 摄入 30 个视频 URL（各 15 分钟）
# - 摄入 20 篇网页文章
# - 摄入 10 个 PDF
# - 摄入 5 段本地音频（各 30 分钟）
# - 摄入 3 张图片
# - 30 次 recall 查询

全本地模式:
  # 硬件: 一台带 GPU 的机器 (~$0.50/h)
  # 成本: 仅电费和硬件折旧

全远程模式:
  Groq ASR:  30视频×15min + 5音频×30min = 10h × $0.04  = $0.40
  Firecrawl: 20网页 + 10PDF = 30 credits                  = 免费额度内
  LLM蒸馏:   65次摄入 × ~50K tokens × $2/1M               ≈ $6.50
  Recall:    30次 × ~10K tokens × $2/1M                    ≈ $0.60
  ─────────────────────────────────────────────────────────
  月度总额:                                                 ≈ $7.50

混合模式 (Level C):
  Groq ASR: 同上                                            = $0.40
  yt-dlp 本地: $0                                         = $0
  pymupdf4llm 本地: $0                                    = $0
  Firecrawl: 同上                                          = 免费额度内
  LLM蒸馏:  同上                                           ≈ $6.50
  ─────────────────────────────────────────────────────────
  月度总额:                                                 ≈ $6.90
```

**Go/No-Go 阈值：**
- 全远程月度成本 < $15 → Go（比一杯咖啡还便宜的知识管理系统）
- $15-50 → Go 但有说明（需要让用户知道成本）
- > $50 → No-Go（对个人用户不可接受，需要设计本地 fallback）

**输出物：** `experiments/cost-model-{date}.md`

**预估时长：** 0.5 小时（基于实验 2.1 的 latency 数据计算）

---

### 问题三：飞书是否可以作为第一阶段知识收集入口？

**不验证飞书 CI 流水线，验证的是飞书作为"非技术用户提交内容的入口"的体验。**

#### 实验 3.1：飞书表单采集完整链路体验走查

当前飞书路径：飞书 Base 表单 → CI worker (`feishu_base_worker.py`) → Raw Bundle → Agent review

```bash
# 从头走一遍完整链路，记录每一步
# 1. 手机端: 打开飞书 → 进入 OKS 表单
#    记录: 表单加载时间？几个必填字段？打字体验？

# 2. 提交一个 URL 类型的内容
#    例如: https://zhuanlan.zhihu.com/p/123456
#    记录: 提交成功到收到反馈的延迟？

# 3. 提交一个文件类型的内容
#    例如: 一张白板照片 / 一段语音备忘录
#    记录: 文件上传速度和限制？移动端能否上传？

# 4. 从提交到 Draft 出现的端到端延迟
#    记录: worker 处理时间 + 通知到达时间

# 5. 人工审核: 在飞书中 approve/reject 的体验
#    记录: 审批卡片是否清晰？一键操作是否可用？

# 6. 提交一个故意有问题的内容（空字段、非法 URL、超大文件）
#    记录: 错误反馈是否及时且清晰？
```

**Go/No-Go 阈值：**

| 维度 | Go 条件 | 需改进才能 Go | No-Go 条件 |
|------|---------|-------------|------------|
| **移动端体验** | 表单在手机上可正常填写和提交，< 3 个必填字段 | 表单复杂但可简化 | 移动端无法正常上传文件或提交 |
| **端到端延迟** | 提交到 Draft 出现 < 3 分钟 | 3-10 分钟（可接受，需告知用户） | > 10 分钟或用户不知道什么时候完成 |
| **错误反馈** | 提交非法内容后 < 30 秒收到清晰错误提示 | 提示不够友好但能看懂 | 提交后无反馈或 crash |
| **审核体验** | approve/reject 一键完成，审核人能看到完整的 Draft 预览 | 预览不完整但可以接受 | 审批人无法判断 Draft 质量 |
| **内容类型覆盖** | 支持 URL、文本、图片上传 | 缺少文件类型但有合理替代方案 | 仅支持纯文本 |
| **用户主观感受** | 找 1 个人（非 OKS 开发者）走一遍，能自己完成从提交到 approve | 中途需要帮助 1 次 | 中途卡住 > 2 次或放弃 |

**输出物：** `experiments/feishu-entry-walkthrough-{date}.md` —— 每步截图 + 时间记录 + 问题清单

**预估时长：** 1.5 小时

#### 实验 3.2：飞书 vs 其他入口的对比

飞书不是唯一的入口选项。用一个简单的对比测试确定飞书在入口矩阵中的位置。

```
测试任务: 摄入同一篇知乎文章，三种方式:
  A. 复制 URL → 粘贴到飞书表单 → 提交
  B. 复制 URL → 终端执行 oks ingest <url>
  C. 下载文章为 Markdown → 拖入 OKS Inbox 文件夹

测试用户:
  - 1 名 OKS 开发者（你）
  - 1 名技术人员（非 OKS 开发者）
  - 1 名非技术人员（不用终端）

每个用户按随机顺序完成三种方式，记录:
  - 完成时间（从看到文章开始计时到确认摄入成功）
  - 失败次数（重试、错误）
  - 主观偏好排名（1-3）
```

**Go/No-Go 阈值：**
- 如果飞书在非技术用户的偏好排名中排第 1 → **飞书是合格的 Phase 1 入口**
- 如果飞书排在技术用户的第 3 → CLI 仍是主力入口，飞书是辅助
- 如果飞书的完成时间 ≥ CLI × 3 → 飞书体验需要优化

**输出物：** `experiments/entry-comparison-{date}.md`

**预估时长：** 1 小时

---

### 实验总览：最小执行计划

```
优先级（按阻塞关系排列）:

  ★ 1.1 依赖拆除 (2h)
       ↓
  ★ 2.1 API 端到端替换 (3h)  ← 这三个可以并行
  ★ 2.2 成本核算 (0.5h)       ← 依赖 2.1 结果
  ★ 3.1 飞书入口走查 (1.5h)
       ↓
  ★ 3.2 入口对比 (1h)
       ↓
     决策时间点 ← 基于以上数据，决定 Phase 1 的技术栈和入口策略

───────────────────────────────
总耗时: ~8 小时（可分两天完成）
  Day 1 AM: 1.1 依赖拆除 + 环境准备 (2h)
  Day 1 PM: 2.1 API 替换验证 (3h)
  Day 2 AM: 2.2 成本核算 + 3.1 飞书走查 (2h)
  Day 2 PM: 3.2 入口对比 + 决策总结 (2h)
```

### 需要的资源

| 资源 | 用途 |
|------|------|
| 当前 OKS 项目环境 | 实验 1.1 的拆除起点 |
| Groq API Key | 实验 2.1 的远程 ASR（免费 2000 req/day） |
| Firecrawl API Key | 实验 2.1 的远程抓取+PDF 解析（免费 1000 credits） |
| OpenAI API Key | 实验 2.1 LLM 蒸馏 + Fallback ASR |
| 腾讯云 TRTC 账号 | （可选）实验 2.1 中文 ASR 对比 |
| 飞书 OKS Base + 表单 | 实验 3.1 的走查对象（已存在） |
| 1 名非 OKS 开发者 | 实验 3.2 的用户测试 |
| 1 名非技术人员 | 实验 3.2 的用户测试 |
| 测试素材 | 3 个 URL + 2 个本地文件 + 1 段音频（总共 6 个测试内容） |

---

### 三个问题的预判答案

> 这是基于调查数据的假设。实验的目的就是验证或推翻这些假设。

**问题一（依赖能降到多少）：**
预判：Level C（拆 ASR + 拆浏览器 + 拆 PDF 重型解析）是合理的最低线。最终本地依赖约 50-100MB（Python + yt-dlp + pymupdf4llm），加上 Groq/Firecrawl/LLM 三个 API Key。主要风险是 yt-dlp 是否强依赖 ffmpeg——如果没有字幕的视频需要从音频轨道做 ASR，就必须 ffmpeg 或 ffprobe。如果 yt-dlp `--skip-download` + `--write-auto-subs` 可以不依赖 ffmpeg 拿到字幕，ffmpeg 就可以拆掉。

**问题二（API 部署是否可行）：**
预判：对于文本和字幕提取，可行——这是已验证的路径。主要风险是中文本地视频的 ASR 准确率和成本，以及中文扫描 PDF 的 Firecrawl 解析质量。如果这两个路径不可接受，就需要保留本地 faster-whisper 和/或 MinerU 作为特定场景的 fallback，但不用作为默认安装项。

**问题三（飞书作为第一阶段入口）：**
预判：飞书可以作为辅助入口，但不适合作为唯一入口。原因：(a) URL 粘贴到表单比 CLI 的 `oks ingest` 多一步操作（打开飞书 → 找到表单 → 粘贴 → 提交 vs 终端直接粘贴），对技术用户来说更慢；(b) 飞书的文件上传体验对非技术用户友好，但端到端延迟取决于 worker 轮询间隔；(c) 审核流程在飞书中完成体验不错（已有的 review_events 逻辑）。建议：Phase 1 保留三条路径并行（Agent / 飞书 / Watch Folder），不需要选一个"唯一入口"。

---

## 十、决策总结

### 不做的事

- ❌ 自建反爬系统或代理池
- ❌ DRM 破解
- ❌ 大规模视频/音频文件下载
- ❌ 付费墙绕过
- ❌ GPU 本地部署（POC 阶段）
- ❌ 与 yt-dlp/Firecrawl/MediaCrawler 竞争提取能力
- ❌ 自建 ASR/OCR 服务

### 实验驱动的 P0/P1/P2

| 轴 | P0（4 天内） | P1（P0 后） | P2（长期） |
|----|------------|------------|-----------|
| **提取能力** | A1 ASR 对比 + A2 Bilibili 降级 + E0 闭环 | A3 MediaCrawler 子进程 + A4 中文网页 | MediaCrawler REST 微服务 |
| **部署轻量** | B1 干净安装 + E0 全程远程化 | B2 安装体验 + B3 Fallback 链 | 多级退化全链路 + 单二进制分发 |
| **用户交互** | C1 Watch Folder 原型 + C2 入口对比 | 浏览器扩展原型 | 飞书/Telegram Bot + 微信小程序 |
| **反爬与合规** | D2 restricted 语义梳理 | D1 yt-dlp 反爬探测 | 用户侧采集工具矩阵 |

---

## 参考文献

- MediaCrawler: https://github.com/NanmiCoder/MediaCrawler (Apache-2.0, 59.4K stars)
- OpenAlex API: https://openalex.org/ (CC0, 2.5 亿论文)
- Groq Whisper: https://console.groq.com/ ($0.04/h whisper-large-v3-turbo)
- Firecrawl: https://firecrawl.dev (500 页/月免费)
- Obsidian Web Clipper: https://github.com/obsidianmd/obsidian-clipper
- Cubox: https://cubox.pro (555K+ 用户, 多端覆盖标杆)
- Readwise Reader: https://readwise.io/read ($9.99/月, 间隔重复+24源同步)
- TranscriptAPI: https://transcriptapi.com (ZeroPointRepo, ClawHub 集成)
- BibiGPT: https://bibigpt.co (30+ 平台视频摘要 API)
- bilibili-api-python: https://github.com/Nemo2011/bilibili-api (⚠️ 2026-07-06 已归档)
- Google v. SerpApi: N.D. Cal. Case No. 4:25-cv-08257 (2026-07-20 DMCA 索赔被驳回)

---

## 十一、2026-08-04 推广前纠偏附录

本附录以 `experiments/promotion-readiness-2026-08-04.md` 和 `experiments/promotion-capability-matrix-2026-08-04.md` 为准，覆盖本报告 v3 中被后续实测推翻或尚未完成的口径。历史实验数据保留，但不得继续把预判写成通过结论。

### 11.1 Level C 体积口径修正

在 Python 3.12.13 全新隔离环境中，以当前源码精确 wheel 和以下固定依赖实测：

```text
open-knowledge-studio-0.3.0
yt-dlp==2026.7.4
markitdown[docx,pptx]==0.1.6
pymupdf4llm==0.0.27
pymupdf==1.28.0
```

结果：

- Core venv：73,614,957 bytes；
- 上述 Level C venv：385,060,202 bytes；
- 加独立 Python 3.12 运行时：451,388,875 bytes；
- Level C 下载制品：101,885,833 bytes / 49 files；
- Level C 安装耗时：74.785s。

因此“本地 50–100MB 已验证可达”必须降级为“历史目标/估算，当前候选组合未达到”。主要增重来自 MarkItDown 的 Magika/ONNX Runtime/NumPy/SymPy、PyMuPDF 和 yt-dlp 安装目录。后续除非更换并重新验收依赖组合，不得用 50–100MB 做推广承诺。

### 11.2 轻量 PDF 路径修正

`pymupdf4llm==0.0.27` 对数字 PDF 的独立提取仍通过：33 页、82,229 chars、6.932s。但在同一 Level C 环境执行 `oks ingest` 时，PDF 路由仍检查 MinerU capability 并以退出码 2 终止。结论是：轻量解析器已作为独立能力验证，尚未接入 OKS 默认 PDF 路由；不能写成“Level C PDF 摄入已通过”。

### 11.3 中文扫描 PDF 修正

对固定的 3 页受控中文图像型 PDF（纯正文、表格、图文与红色印章，文本层为 0）：

- pymupdf4llm 返回 0 chars，符合其不做 OCR 的边界；
- MinerU 在 180 秒内没有生成 Raw，且留下需要精确清理的子进程树；
- Firecrawl `/parse` 因当前验收运行没有 `FIRECRAWL_API_KEY` 尚未测试。

因此扫描中文 PDF 仍为 `awaiting_human` / 未验证，不得继续写成 Firecrawl 已验证或 Level C 默认覆盖。

### 11.4 Bilibili 与 ffmpeg 修正

在隔离 PATH 中确认 ffmpeg/ffprobe 均不可见后，对当日热门接口返回的 10 个 Bilibili URL 执行 `yt-dlp --skip-download --list-subs`，10/10 在网页阶段返回 HTTP 412。Chrome 与 Edge Cookie 数据库复制也均失败。请求尚未到字幕写出阶段，所以该结果只能标记为 `environment_limited`，不能用来判断 ffmpeg 是否可拆。需要可用临时 Cookie 后复用同一组 URL 完成对照。

### 11.5 长音频 ASR 修正

12 秒中文音频的 whisper-1 结果仍然有效，但 5 分钟实验目前只完成固定样本准备：299.856 秒、1,800,066 bytes、SHA-256 为 `A5D0E8400DE490B0F51BB8E350420ABF11B8577C64EC2E8E64CB30841FC55FD3`。没有 OpenAI Key 时，延迟、费用和长段质量均保持 `awaiting_human`，不能从 12 秒结果外推。

### 11.6 当前推广原则

OKS 的知识闭环和飞书入口闭环保持冻结，不重复验证。推广重点应表述为“Agent 编排的可追溯知识闭环 + 能力按需安装 + 失败可恢复”，而不是“50–100MB 全来源采集”或“突破平台反爬”。

### 11.7 能力分层体积归因

后续隔离 venv 实测表明，部署体积应按 capability 分层，而不是把所有提取器合并成一个 Level C：

| 组合 | venv 实占 | 解释 |
|---|---:|---|
| Core + yt-dlp | 95,259,882 bytes | 视频元数据/字幕层，约 100MB 级 |
| Core + yt-dlp + pymupdf4llm | 150,729,647 bytes | 加数字 PDF 独立能力，约 150MB 级 |
| Core + MarkItDown | 277,830,593 bytes | 文档层，受 Magika/ONNX 依赖影响 |
| 全部合并 | 385,060,202 bytes | 不适合作为默认安装 |

因此新的推广口径应为“按来源安装能力，默认核心保持轻量”，而不是承诺所有来源共享一个 50–100MB 环境。详细命令和版本见 `experiments/promotion-readiness-2026-08-04.md` 的 P0-2b。
### 11.8 2026-08-04 B1 复测：Cookie 解密仍是前置阻塞

浏览器进程关闭后，使用同一组 10 个 Bilibili BV，在正常 PATH 和移除 ffmpeg/ffprobe 的隔离 PATH 中均执行 `yt-dlp --cookies-from-browser chrome --skip-download --write-subs --write-auto-subs --sub-langs 'zh.*,ai-zh' --sub-format vtt`。两组均为 `0/10`，20 次均在 Cookie 阶段报 `Failed to decrypt with DPAPI`，没有生成 `.vtt`，请求没有进入字幕阶段。因此本轮仍不能回答 A1；后续必须由用户提供仅用于本地测试的临时 Netscape `cookies.txt`，并记录为人工前置条件。

### 11.9 2026-08-04 P0-3/P0-4 补跑结论

- Firecrawl `/v2/parse` 对受控 3 页中文扫描 PDF 返回 HTTP 200，7.201 秒，548 chars，3 页和 6 行 Markdown 表格，消耗 3 credits；正文、表格和图文混排页均可读。结论是“远程 OCR fallback 可用”，不是“本地 Level C 扫描 PDF 已覆盖”。
- OpenAI `whisper-1` 5 分钟请求未获得 HTTP 响应；独立诊断显示当前网络到 `api.openai.com:443` 的 IPv4/IPv6 均超时。5 分钟延迟、质量和实际成本继续保持 `environment_limited`，不能从 12 秒样本外推。

### 11.10 2026-08-04 B1/A1 Cookie 对照定案

人工导出的 Netscape Cookie 解除了前置阻塞。对同一组 10 个 Bilibili BV，正常 PATH 和移除 ffmpeg/ffprobe 的隔离 PATH 均为 `7/10`，成功集合完全一致；成功样本实际落盘为 `.srt`，因为目标样本没有 VTT 格式。由此可确认：在有登录 Cookie 且平台提供字幕时，`yt-dlp --skip-download` 字幕采集不需要 ffmpeg/ffprobe，A1 通过；但 B1 仅为 `partial`，70% 成功率不能支撑“Bilibili 稳定全量采集”的推广承诺。

### 11.11 2026-08-04 最终推广口径

本轮实验支持的推广模型是“轻量 Core + 按需 capability + 远程 fallback + Feishu/Agent 编排”。All-in-one Level C 的实测安装体积不满足 50–100MB，因此不作为单体承诺；Bilibili 需要登录 Cookie 且字幕成功率受平台内容影响；扫描中文 PDF 由 Firecrawl 提供远程 OCR fallback；5 分钟 OpenAI ASR 和 MediaCrawler 仍是外部网络条件下的补证项。详细摘要见 `experiments/promotion-summary-2026-08-04.md`。
