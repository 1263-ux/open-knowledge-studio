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

Run `oks capability catalog --json` to see available capabilities.
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
1. Call the tool
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
3. Write `drafts/{slug}.md`

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

## Constraints

- NEVER write to wiki/ directly — only drafts/
- NEVER upgrade partial to complete
- NEVER present agent inference as source text
- NEVER expose API keys, cookies, or tokens
- ALWAYS record failure reasons honestly
- ALWAYS preserve original tool output unmodified
