# Raw 多模态一键录入

> 目标：把用户明确提供的现实素材交给成熟提取器，生成诚实、可追溯、可校验的 Raw Markdown。

本入口不摘要、不纠错、不评价内容价值，也不决定素材是否进入 Wiki。

## 1. 当前支持

| 来源 | 成熟提取器 | Raw 证据 |
|---|---|---|
| 本地视频 | Watch Skill、faster-whisper、ffmpeg | ASR 时间段、关键帧、OCR |
| 本地音频 | Watch Skill、faster-whisper | ASR 时间段 |
| 图片 | RapidOCR | OCR 文本、置信度、bbox、原图 |
| PDF | MinerU | Markdown、页码/版面证据、图片资产 |
| PPTX、DOCX、XLSX、HTML、TXT、CSV | MarkItDown | Markdown、文档证据、可提取的内嵌资产 |

B站等平台 URL 可以被识别并路由，但真实平台字幕录入目前仍为 `blocked`：现有三个样本没有公开字幕，当前网络中的 yt-dlp 请求遇到 HTTP 412。本地视频 ASR 回退已经验证，二者不能混称为“平台字幕已验证”。

## 2. 环境

Windows 实测环境为 Python 3.12，并将重型依赖隔离为三个环境：

- Watch/图片环境：`scripts/watch_extract_requirements.txt`；
- 文档环境：`scripts/raw_extract_requirements.txt`；
- MinerU 环境：`scripts/mineru_extract_requirements.txt`；
- 可选公式候选环境：`scripts/formula_extract_requirements.txt`；
- 系统命令：ffmpeg 与 ffprobe。

复制 `settings/raw-tools.example.json` 为 `.oks/raw-tools.json`，填写本机解释器和命令路径。`.oks/` 已被 Git 忽略，本机绝对路径不会提交。

也可以使用环境变量覆盖：

```text
OKS_WATCH_PYTHON
OKS_DOCUMENT_PYTHON
OKS_MINERU_PYTHON
OKS_FORMULA_PYTHON
OKS_FFMPEG
OKS_FFPROBE
```

## 3. 先运行 doctor

```powershell
.\.venv\Scripts\python.exe scripts\raw_ingest.py doctor --json
```

`doctor` 只报告解释器、模块、CLI 和版本，不自动安装、不修改系统环境，也不隐藏缺失依赖。

## 4. 一条命令生成 Raw

```powershell
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\lesson.mp4" `
  --output ".oks\intake\lesson"
```

其他格式使用相同入口：

```powershell
# 图片
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\shot.png" `
  --output ".oks\intake\shot"

# Office 或 HTML
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\notes.docx" `
  --output ".oks\intake\notes"

# PDF；扫描件可显式使用 --mineru-method ocr
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\paper.pdf" `
  --output ".oks\intake\paper" --mineru-method auto

# 中文技术音频：主ASR保持不变，额外保存热词上下文候选
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\java.mp3" `
  --output ".oks\intake\java" --transcript-only `
  --asr-language zh --hotwords "Java,三元运算符,键盘录入"

# 软件截图：只对用户明确指定的正文区域做OCR，坐标仍回映射到原图
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\screen.png" `
  --output ".oks\intake\screen" --ocr-roi "650,300,2200,1400"

# 屏幕录制：用内容变化而非均匀时间点选择证据帧
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\ide.mp4" `
  --output ".oks\intake\ide" --video-profile screen `
  --screen-sample-seconds 1 --screen-change-threshold 3

# PDF：对MinerU已定位的独立公式图片生成PP-FormulaNet第二候选
.\.venv\Scripts\python.exe scripts\raw_ingest.py ingest "D:\sample\math.pdf" `
  --output ".oks\intake\math" --formula-secondary --formula-max-regions 20
```

命令会自动执行 `validate`。成功只表示 Raw 结构、证据和资产没有机械断链，不表示 ASR、OCR、公式或表格已经正确。

热词和公式结果均作为候选保存，不自动覆盖主提取结果。OCR ROI外的内容仍存在于原图，但不会进入OCR正文。`screen`路线按显式采样间隔观察变化，短于采样窗口的瞬时画面可能遗漏。

## 5. 实测闭环（2026-07-15）

| 样本 | 耗时 | 结果 |
|---|---:|---|
| Open Knowledge Studio HTML 快照 | < 1 秒 | 文档证据，校验通过 |
| 2560×1600 会议截图 | 约 8 秒 | 86 条证据，校验通过 |
| Java 课程 60 秒音频 | 约 34 秒 | 56 条时间戳证据，校验通过 |
| Java 三元运算符 142 秒视频 | 约 111 秒 | 221 条 ASR/视觉证据，校验通过 |
| 高中数学公式大全 7 页 PDF | 约 251 秒 | 299 条页码/版面证据，校验通过 |

PDF 首次复跑暴露了 Windows 系统代理把 MinerU 的本地 API 请求送到代理端口、返回 502 的问题。统一入口仅在 MinerU 子进程中为 `127.0.0.1` 和 `localhost` 设置直连，不修改用户的系统代理。

隔离召回测试可以从 PDF 的 `content.md` 命中“函数极限/洛必达法则”。Windows 旧代码页若无法显示数学 Unicode 字符，可在执行 `oks recall` 前设置：

```powershell
$env:PYTHONUTF8="1"
```

## 6. 下一阶段：浏览器登录态入口

本地 Raw 解析稳定后，再增加“用户正在浏览的页面”入口：

```text
用户明确选择当前页面/媒体
  → 复用浏览器登录态获取页面、字幕或媒体
  → 保存来源 URL、获取方式和原始快照
  → 调用同一个 raw_ingest / Raw Adapter
  → Raw Markdown
```

该入口属于来源获取层，不改变 Raw Schema。Cookie 和令牌不得写入 Raw 或 Git；平台获取失败必须保留真实原因，并允许用户改用本地文件、页面快照或导出字幕回退。

第一批验收应使用一个确实存在登录态字幕的视频，而不是继续用当前三个无公开字幕样本证明不存在的能力。
