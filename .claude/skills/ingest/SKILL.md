---
description: Agent-native ingest — Source → Provider → EvidenceFragment → Manifest → oks raw commit → Candidate
---

# /ingest — Agent-Native Evidence Ingestion

Agent is the orchestrator.  OKS provides capability; Agent decides what to do.

## Flow

```
Source → Judge modality → Read Recipe → Select Providers → Execute
→ EvidenceFragment x N → Merge → EvidenceManifest → oks raw commit
→ AgentObservation → CandidateDraft → drafts/{slug}.md → Report
```

## Step 1: Accept Source

Source is a file path, URL, or plain text.  If a path, read the file.

## Step 2: Judge Modality

From `scripts/route.py:describe_source()`:
- `.md/.txt` -> text, `.pdf` -> pdf, `.docx/.pptx/.xlsx` -> office
- `.png/.jpg` -> image, `.mp4/.mkv` -> video, `.mp3/.wav` -> audio
- URL -> web (or video if bilibili/youtube/douyin)

## Step 3: Select Providers

Read `providers/*/provider.yaml`.  For the detected modality, find
providers whose `provides:` includes the relevant capability.
Prefer lowest-cost, local, stable providers first.
Use `oks capability catalog` to see available capability matrix.

## Step 4: Execute Providers

For each chosen provider:
1. Call the tool (Bash / MCP / API / Agent vision)
2. Save raw output to `.oks/runs/{run_id}/work/{provider}/`
3. Construct EvidenceFragment following `schemas/evidence-fragment-v0.1.schema.json`

Agent's own multimodal observation is also a fragment
(`producer: agent-runtime`, `agent_judgment: agent_observed`).

## Step 5: Merge into EvidenceManifest

Collect all fragments.  Create EvidenceManifest following
`schemas/evidence-manifest-v0.1.schema.json`.  Judge overall status:
- `complete` — all required evidence obtained
- `partial` — some missing, must declare `failure_disposition` and `warnings`
- If ALL fragments failed — do NOT submit; report failure to user

Record every step in `manifest.steps[]` including provider name,
capability, status, and reason for any fallback.

## Step 6: oks raw commit

Create the manifest directory:
```
.oks/runs/{run_id}/manifest/
  source-envelope.json
  evidence-manifest.json
  fragments/          (all EvidenceFragment snapshots)
  artifacts/          (all evidence files)
```

Run: `oks raw-commit .oks/runs/{run_id}/manifest/ --output raw/{date}/{source}/{slug}/`

On success: bundle_id returned.  On rejection: read error_code, do NOT retry blindly.

## Step 7: AgentObservation -> Candidate

1. Read the Raw Bundle's `evidence.jsonl`
2. Create AgentObservation (following `schemas/agent-observation-v0.1.schema.json`)
   - Each claim references `artifact_id + locator` from evidence
   - `supported` claims -> have direct evidence
   - `uncertain` claims -> Agent inference, need human verification
3. Call `observation_to_candidate()` from `scripts/observation_adapter.py`
4. Write `drafts/{slug}.md`

## Step 8: Write result.json

Save `.oks/runs/{run_id}/result.json`:

```json
{
  "status": "complete|partial",
  "source": "<source uri>",
  "providers_used": ["pdf-lite", "rapidocr"],
  "capabilities_used": ["document.text.extract", "image.ocr"],
  "evidence_summary": {
    "page_count": 3,
    "text_chars": 696,
    "bbox_regions": 43
  },
  "missing": [],
  "reasons": [],
  "impact": [],
  "remote_processing": false,
  "cost": 0,
  "latency_ms": 6200,
  "bundle_id": "bundle:2789f4ff",
  "candidate_path": "drafts/controlled-chinese-scan.md",
  "review_status": "pending"
}
```

## Step 9: Report to User

Use `result.json` to generate the user-facing summary.

### Complete scenario

```
已完成摄入

来源：controlled-chinese-scan.pdf
状态：完整

使用方式：
- pdf-lite 检测文本层
- RapidOCR 提取 43 个文字区域
- Agent 校验页面结构

证据：
- 3 个页面级定位
- 43 个 bbox 定位
- 共 696 字正文

远程处理：未使用
成本：0
耗时：6.2 秒

结果：
- Raw Bundle: bundle:2789f4ff
- Candidate: drafts/controlled-chinese-scan.md
- 当前状态：等待人工审核
```

### Partial scenario

```
状态：部分完成

已获得：
- 视频元数据
- 弹幕文本
- 7 张关键帧

缺失：
- 常规字幕正文

原因：
- Bilibili 需要登录权限

影响：
- 可以检索视频主题和弹幕
- 对完整口播内容的覆盖不足

当前状态：
- Raw 已保存
- Candidate 等待审核
```

### Failed scenario

```
状态：未能完成

来源：<source>

原因：所有 Provider 均失败
- pdf-lite: 文本层为空
- RapidOCR: 未安装
- Agent 视觉: 当前会话不支持

建议：
- 运行 oks capability install watch --yes
- 或在支持多模态的 Agent Host 中重试
```

## Constraints

- NEVER write to wiki/ directly — only drafts/
- NEVER upgrade partial to complete
- NEVER present agent inference as source text
- NEVER expose API keys, cookies, or tokens
- ALWAYS record failure reasons honestly
- ALWAYS preserve original tool output unmodified
