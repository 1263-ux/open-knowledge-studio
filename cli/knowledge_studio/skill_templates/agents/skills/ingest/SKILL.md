---
description: Agent-native ingest — Source → Recipe → Capability Status → Provider Cluster → EvidenceFragment → Manifest → oks raw commit → Candidate
---

# /ingest — Agent-Native Evidence Ingestion

Agent is the orchestrator.  OKS provides capability; Agent decides what to do.

## Flow

```
oks ingest prepare <source>  →  SourceEnvelope + Manifest skeleton
→ Judge modality → Read Recipe → Query capability status → Select minimum sufficient provider set
→ Execute provider cluster (one execution → multiple evidence fragments)
→ Fill evidence_records  →  oks raw commit
→ AgentObservation → CandidateDraft → drafts/{slug}.md → Report
```

## Step 0: Prepare (use the CLI — do NOT hand-craft protocol JSON)

Run `oks ingest prepare <source>` to create the workspace and generate
the protocol skeleton (source-envelope.json, evidence-manifest.json,
artifacts/).  This command fills all deterministic fields — source_id,
content_hash, schema_version, timestamps, artifact hashes — so the
Agent only needs to supply evidence content.  For text sources the
skeleton includes pre-filled evidence fragments.

DO NOT manually construct SourceEnvelope, EvidenceManifest, or
EvidenceFragment JSON.  Use `oks schema show <name>` to inspect
schema requirements when filling evidence records.

## Step 1: Check text_ready

`oks ingest prepare` outputs a `text_ready` field in its JSON response.

**IF `text_ready` is `true`:**
- The source is a local Markdown (`.md`) or plain text (`.txt`) file.
- SourceEnvelope, EvidenceManifest, EvidenceFragment, and artifact are all pre-filled.
- All evidence is mechanically complete — no Provider execution is needed.
- **Skip Steps 2-5.** Go directly to Step 6 (`oks raw-commit`).
- Then proceed to Step 7 (Candidate), Step 8 (result.json), and Step 9 (Report).
- In result.json, set `providers_used: ["text-read"]` and
  `provider_selection.chosen: "text-read"`.

**IF `text_ready` is `false`:**
- Continue to Step 2 (Judge Modality) for full Provider orchestration.

## Step 2: Judge Modality

Determine the source's modality from its file extension or URL pattern:

- `.md/.txt` → text, `.pdf` → pdf, `.docx/.pptx/.xlsx` → office
- `.png/.jpg` → image, `.mp4/.mkv` → video, `.mp3/.wav` → audio
- URL → web (or video if bilibili/youtube/douyin)

## Step 3: Assess Evidence Demand vs Current Capability

### 3a. Read the Recipe

Read `recipes/{modality}.md` to understand what evidence is needed:

- **required_capabilities**: MUST be satisfied — if any are missing after execution, the ingest is `partial` or `failed`
- **optional_capabilities**: nice-to-have — missing optional capabilities don't block Candidate generation
- **degradation**: priority-ordered fallback chain when a required capability fails

### 3b. Query Current Capability

Run **one** command to get the complete environmental facts:

```bash
oks capability status --json
```

This returns:
- Every action with its Chinese label and description
- Which providers supply each action
- Each provider's current availability (`ready`, `not_configured`, `unavailable`, `runtime_only`)
- Each provider's execution type, known limits, and platform metadata

You now have everything needed to select providers.  Do NOT also run
`oks capability catalog` or `oks capability doctor` — `status` is the
single source of truth.

### 3c. Select Minimum Sufficient Provider Set

For each required capability, find available providers from the status output.
**Prefer the lightest reliable evidence path:**

1. **Agent Runtime** — for public pages, images, layout understanding, charts.  Zero setup, always available.
2. **Local managed providers** (pdf-lite, trafilatura, rapidocr) — for text extraction, OCR.  Fast, free, private.
3. **External providers** (Firecrawl, AgentKey) — for JS-heavy pages, anti-bot sites, platform APIs.  Costs credits or requires API keys.
4. **MediaCrawler** — for Chinese social platform content (小红书, 抖音, B站).  User must install separately.
5. **partial + needs-human** — all automated paths failed.

**The goal is the MINIMUM set of providers that covers all required
capabilities — not one provider per capability.**

A single provider often satisfies multiple demands at once.  For example:
- **Firecrawl** one execution → `web.fetch` + `web.extract` + `metadata.fetch` (3 capabilities, 1 call)
- **Agent Runtime** one observation → `image.observe` + `layout.understand` + `chart.interpret` (3 capabilities, 1 observation)
- **pdf-lite** one execution → `document.text.extract` + `document.structure.extract` + `metadata.fetch` (3 capabilities, 1 call)

## Step 4: Execute Provider Cluster

A **Provider Cluster** is one provider execution that produces multiple
EvidenceFragments — do NOT iterate per capability.

### For each chosen provider:

1. Call the tool (Bash / MCP / API / Agent vision) **once**
2. Save raw output to `.oks/runs/{run_id}/work/{provider}/`
3. **For external providers: sanitize before saving.**  Run `oks security sanitize .oks/runs/{run_id}/work/{provider}/output.json` to strip API keys, bearer tokens, session cookies, and internal IPs from the raw output before it enters the Raw Bundle.
4. Construct **one EvidenceFragment per satisfied capability** — not one per provider.  Get the fragment schema: `oks schema show evidence-fragment`

### Provider-specific evidence construction:

**Firecrawl (one /scrape call → multiple fragments):**
- Fragment 1: `web.fetch` → `kind: "source_capture"`, `method: "http_fetch"`, text is raw response metadata
- Fragment 2: `web.extract` → `kind: "text"`, `method: "html_extract"`, text is extracted markdown
- Fragment 3: `metadata.fetch` → `kind: "metadata"`, `method: "html_metadata"`, text is title/author/date
- `producer.provider: "firecrawl"`, `agent_judgment: "mechanical"`

**Agent Runtime (one multimodal observation → multiple fragments):**
- Fragment 1: `image.observe` → `kind: "observation"`, `method: "agent_multimodal_observation"`
- Fragment 2: `layout.understand` → `kind: "observation"`, `method: "agent_layout_analysis"`
- Fragment 3: `chart.interpret` → `kind: "observation"`, `method: "agent_chart_reading"`
- `producer.provider: "agent-runtime"`, `agent_judgment: "agent_observed"`
- **IMPORTANT:** Agent observation is valid evidence but MUST be labeled as such.  Never present agent-observed content as raw source text.

**pdf-lite (one pymupdf4llm call → multiple fragments):**
- Follow `providers/pdf-lite/SKILL.md` for the 3-step workflow
- Fragment per page OR one fragment covering all pages with `locator: {kind: "page", page: N}`
- `producer.provider: "pdf-lite"`, `agent_judgment: "mechanical"`

## Step 5: Coverage Check & Merge into EvidenceManifest

After executing all providers, compare obtained evidence against the Recipe's demands:

### Required capabilities check:
- All required satisfied → status: `complete`
- Some required missing:
  - Auto-fallback to next degradation priority if available
  - If no fallback available: status `partial`, `failure_disposition: "needs_user_action"`
  - Present the gap to the user in plain language (see Step 9 Guided UX)

### Optional capabilities check:
- Satisfied → bonus, record in manifest
- Missing → note in warnings, do NOT block — optional means optional

Collect all fragments and create the EvidenceManifest (`oks schema show evidence-manifest`).
Record every step in `manifest.steps[]` including provider name, capabilities satisfied,
status, and reason for any fallback.

**If ALL fragments failed — do NOT submit; report failure to user with actionable guidance.**

### Missing capability → Guided UX (NOT silent partial)

When a required capability cannot be satisfied:

1. Query `oks capability status --json` to see if any unconfigured provider could help
2. If an auto-fallback is possible (e.g., trafilatura → Firecrawl) → execute it directly, don't ask
3. If the only path forward needs user action (install, auth, cost) → explain in user language:

```
这份 PDF 的正文已完整提取（12 页，15,000 字），但其中 3 页是扫描图片，
目前缺少文字内容。

我可以：
1. 安装本地 OCR 后重新提取这 3 页 — 首次安装需要下载约 200MB
2. 使用远程 OCR 处理 — 需要配置 Firecrawl
3. 先生成待审核知识，标记"3 页图片内容缺失"

推荐选项 3：正文已经足够覆盖核心内容，图片缺失不影响主要知识的完整性。
```

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

## Step 7: AgentObservation → Candidate

1. Read the Raw Bundle's `evidence.jsonl`
2. Create AgentObservation — each claim references `artifact_id + locator`
   from evidence.  `supported` claims have direct evidence; `uncertain` are
   Agent inference needing human verification.
3. Write Candidate to `drafts/{slug}.md` with valid YAML frontmatter:
   ```yaml
   title: "Human-readable title"
   type: concept
   area: computing
   importance: 0.7
   confidence: 0.5
   created: "YYYY-MM-DD"
   tags: "comma, separated"
   status: provisional
   source_type: agent-ingest
   ```

   **Important:** Candidate is a draft Markdown document written to `drafts/{slug}.md`.
   Candidate is NOT an OKS protocol schema object.
   Do NOT call `oks schema show candidate` — it does not exist as a schema.
   Use `oks drafts list` to see existing candidates.

## Step 8: Write result.json

MUST write `.oks/runs/{run_id}/result.json` before reporting to user.

```json
{
  "status": "complete|partial",
  "source": "<source uri>",
  "providers_used": ["pdf-lite", "agent-runtime"],
  "capabilities_used": ["document.text.extract", "image.observe"],
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
  "review_status": "pending",
  "provider_selection": {
    "chosen": "pdf-lite",
    "candidates_considered": ["pdf-lite", "rapidocr", "agent-runtime"],
    "rationale": "pdf-lite selected as primary text extraction; rapidocr for OCR supplement; agent-runtime as fallback",
    "fallback_activated": false,
    "degradation_path": []
  }
}
```

### provider_selection fields

- **chosen** (required): the provider ultimately used
- **candidates_considered** (required): all providers evaluated, in preference order
- **rationale** (required): WHY the chosen provider was selected over alternatives
- **fallback_activated** (required): true if the first-choice provider failed
- **degradation_path** (required when fallback activated): ordered list of `{provider, status, reason}` for every attempt

### Degradation path status values

- `success` — provider succeeded
- `failed` — provider returned no useful output
- `blocked` — anti-bot, paywall, or access restriction
- `unavailable` — provider not configured or not installed
- `skipped` — provider was considered but not attempted (cost, maturity, etc.)

## Step 9: Report to User (Guided UX)

MUST output the unified result card as the final user-facing message.

**All user-facing text MUST be in Chinese natural language.**
**NEVER expose provider IDs, capability IDs, or schema names to the user.**
Translate everything into plain-language descriptions.

### Complete result:

```
✅ 摄入完成

来源：{source_uri}

已获得：
- 正文内容（12 页，约 15,000 字）
- 文档结构（标题层级和段落划分）
- 页面元数据（标题、作者）

缺失：无

待审核知识：{candidate_path}

下一步：
使用 /promote 审核、编辑或拒绝该 Candidate。
```

### Partial result (with guided recommendation):

```
⚠️ 部分完成

来源：{source_uri}

已获得：
- 正文内容（12 页，约 15,000 字）— PDF 文本层提取
- 文档结构 — 标题和段落划分

缺失：
- 3 页扫描图片中的文字内容 — 这些页面没有文本层

影响：这 3 页是附录中的扫描表格，不影响文档主体论证的完整性。

推荐：先生成待审核知识并标注"3 页图片缺失"。正文证据已足够覆盖核心内容。
如果后续需要完整的表格数据，可以再安装 OCR 补充处理。

待审核知识：{candidate_path}

下一步：
使用 /promote 审核 Candidate。你可以接受、修改或要求补充缺失的图片内容。
```

### Failed result (all providers exhausted):

```
❌ 无法完成

来源：{source_uri}

尝试了以下方式：
- 直接获取网页 — 失败（反爬保护）
- 远程抓取 — 失败（需要配置访问密钥）

当前无法自动获取此来源。建议：
1. 手动复制网页正文，粘贴到 Markdown 文件后重新摄入
2. 配置 Firecrawl API 密钥以启用远程抓取能力

如果你能提供页面正文，我可以立即继续处理。
```

### Card principles:

- **摄入完成**: `complete` (all required evidence obtained), `partial` (some evidence missing, usable), `failed` (no usable evidence)
- **已获得**: bullet list in plain Chinese — describe WHAT was obtained, not HOW (say "正文内容" not "web.extract via Firecrawl")
- **缺失**: bullet list with impact explanation — always state what's affected
- **推荐**: always provide a recommended next step, don't just list options
- **下一步**: always points to `/promote` for human review
- **Provider chain**: only shown internally (result.json), not in user-facing card

## Guided UX Principles

These principles MUST be followed in every ingest session:

### 1. Ask users for judgment, not implementation

| Wrong | Right |
|-------|-------|
| "AgentKey 未配置。是否切换 MediaCrawler Provider？" | "这个页面需要登录态才能完整读取。我可以：1. 使用浏览器登录状态继续 2. 只收录公开内容。推荐 1。" |
| "RapidOCR capability unavailable." | "这张图片是文字截图。我可以直接使用当前视觉能力识别，也可以安装本地 OCR 后再处理。这次只有一张图片，推荐直接识别。" |
| "请运行 oks capability catalog。" | "让我确认一下当前可以使用的处理能力……" (Agent runs it internally) |

### 2. Proactive gap discovery

When capability is missing:
1. Query `oks capability status --json` to check for remediable capabilities
2. If auto-fallback possible → do it immediately, don't ask
3. If user action needed → explain impact → give actionable options → recommend one

Never: `capability missing → status: partial → done`

### 3. Plain Chinese, no internal IDs

User-facing text requirements:
- ✓ "正文内容" — ✗ "web.extract 能力"
- ✓ "远程网页抓取" — ✗ "Firecrawl Provider"
- ✓ "可以处理" — ✗ "status: ready"

Internal IDs (provider names, capability IDs, schema names) exist ONLY in:
- `result.json` (Step 8)
- `manifest.steps[]` (Step 5)
- Agent's internal reasoning (never shown to user)

### 4. Recommendation over menu

When presenting options, always recommend one. Don't dump a list of choices.

### 5. Three levels of detail

- **Level 0 (default)**: Task → Progress → Result → Missing → Choices → Review
- **Level 1 (user asks "why this way?")**: "因为页面是动态渲染的，直接获取拿不到正文，所以使用了远程抓取。"
- **Level 2 (user runs `oks capability doctor --verbose`)**: Full technical matrix — provider IDs, availability, checks

## Constraints

- NEVER write to wiki/ directly — only drafts/
- NEVER upgrade partial to complete
- NEVER present agent inference as source text
- NEVER expose API keys, cookies, or tokens
- NEVER expose provider IDs, capability IDs, or schema names in user-facing messages
- ALWAYS record failure reasons honestly
- ALWAYS preserve original tool output unmodified
- ALWAYS explain missing evidence in terms of user impact, not technical failure
- ALWAYS recommend a default action when presenting choices to the user
- MUST write result.json to `.oks/runs/{run_id}/result.json` before reporting to user
- MUST include `provider_selection` in result.json with chosen, candidates_considered, and rationale
- MUST include `degradation_path` in provider_selection when fallback was activated
- MUST output the unified result card as the final user-facing message (Step 9 format)
- MUST record every attempted provider in degradation_path even if it failed
- MUST use Chinese natural language for all user-facing text
- MUST run `oks capability status --json` (not catalog + doctor separately) for capability decisions
- MUST treat one provider execution as a cluster that can satisfy multiple demands simultaneously
