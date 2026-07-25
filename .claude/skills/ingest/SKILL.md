---
description: Multi-modal intake — route → ingest → digest → Candidate → review → Wiki
---

# /ingest — Multi-Modal Intake

## 核心流程

```
oks ingest <source>  →  Raw Bundle (content.md + evidence.jsonl + digest.md)
Agent 读 raw/index.json  →  找未处理条目
Agent 读 digest.md       →  快速了解内容
Agent 读 content.md      →  需要深入时
Agent 读 evidence.jsonl  →  需要引用事实时
Agent 写 draft           →  Candidate
用户审核                  →  accept/edit/reject/defer
oks drafts promote       →  Wiki
oks recall / oks search  →  知识可用
```

## Phase 1: 采集

### 直接采集

```bash
oks ingest "https://www.youtube.com/watch?v=..." --mode quick
oks ingest "https://www.youtube.com/watch?v=..." --mode forensic
oks ingest /path/to/file.pdf --mode quick
oks ingest /path/to/file.pptx --mode quick
```

- 输出到 `raw/<timestamp>-<slug>/`
- 自动生成 `raw/index.json`（全局索引）和 `<bundle>/digest.md`（摘要）

### 飞书采集（可选组件）

```bash
oks feishu submit "https://..." --thought "为什么保存"
oks feishu run-once
```

### 能力安装（按需）

```bash
oks capability install watch --yes     # 视频/音频
oks capability install document --yes  # Office/HTML
oks capability install pdf --yes       # PDF
oks capability install formula --yes   # 公式OCR
```

## Phase 2: 阅读 Raw

### 第一步：扫索引

```bash
cat raw/index.json
```

了解有哪些采集、状态、证据量、警告数。挑出待处理的条目。

### 第二步：读摘要

```bash
cat raw/<bundle>/digest.md
```

~500 字，包含：标题、来源、模态、证据统计、警告、人工核验建议。

### 第三步：深入（需要时）

- `content.md` — 提取正文（合段去重后的可读文本）
- `evidence.jsonl` — 原子证据（时间戳、bbox、置信度），引用编号即可
- `quality-report.json` — 覆盖检查、逐模态状态

## Phase 3: 生成 Candidate

从 Raw 到 Candidate 的原则：

1. **读 digest.md 判断是否值得处理**。如果状态是 `failed` 且无法恢复，跳过。
2. **读 content.md 理解内容**。不要逐条看 evidence。
3. **需要引用事实时**才查 evidence.jsonl。引用编号如 `watch-speech-000042`。
4. Candidate 写入 `drafts/{slug}.md`：

```markdown
---
title: 主题标题
type: concept
area: computing
source: https://...
source_bundle: raw/20260725-.../
status: draft
---

# 我的理解

...（Agent 用自己的话总结，不是复制 content.md）

# 需要你判断

1. ...（1-3 个关键问题）
```

5. **绝不能**复制 Raw 内容到 Wiki。Candidate 是 Agent 的**理解和提炼**。

## Phase 4: 审核与晋升

### 飞书审核（已配置飞书时）

Agent 通过飞书消息发送 Candidate，用户自然语言回复 accept/edit/reject/defer。

### CLI 审核

Agent 汇报 Candidate，用户确认后：

```bash
oks drafts promote <slug>
oks wiki use <slug>        # 记录使用
```

## 状态处理

| Raw 状态 | 含义 | Agent 该怎么做 |
|---|---|---|
| `partial` | 提取完成但有警告（最常见） | 正常使用，注意 warnings |
| `failed` | 提取失败 | 跳过或要求重试 |
| `skipped` | 该模态未执行 | 不影响其他模态 |
| `EXTRACTION_TIMEOUT` | 超时 | 可重试，加大 --timeout-seconds |

## 能力路由速查

| 输入 | 提取器 | 安装命令 |
|---|---|---|
| YouTube/Bilibili/抖音 | watch | `oks capability install watch --yes` |
| .mp4 .mp3 .wav | watch | 同上 |
| .pdf | mineru | `oks capability install pdf --yes` |
| .pptx .docx .html .txt | markitdown | `oks capability install document --yes` |
| .png .jpg .webp | rapidocr | 同上（包含在 watch 中） |

未安装能力时，`oks ingest` 会自动提示正确的安装命令。
