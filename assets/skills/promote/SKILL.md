---
description: Review drafts — list, promote to wiki/, or reject
---

# /promote — Draft Review & Promotion

## Purpose

List drafts in `drafts/`, let user review, promote accepted ones to `wiki/` or reject.

## Steps

1. **List drafts** — `oks drafts list`
2. **Read the exact Candidate** — `oks drafts get <slug>`
3. **For each draft** — Show content, ask: `promote`, `reject`, or `edit`
4. **Promote** — `oks drafts promote <slug>` (optionally with `--title`, `--type`, `--area`, `--slug-hint`, repeated `--tag`)
5. **Reject** — `oks drafts reject <slug>` (confirm first; the Candidate leaves the pending queue)
6. **Edit** — Open for editing, then promote or reject

## Rules

- Require explicit `draft_type` and `draft_area`, or review overrides `--type`
  and `--area`. Use canonical domains from `oks wiki domains`. Missing or
  unknown classification stops promotion and leaves the Candidate intact.
- A matching body with a different domain or type is a classification conflict.
  Review the existing page explicitly; the Candidate is not consumed.
- Source material (`content_role: source_material`, including legacy
  `source_type: local-ocr-import`) cannot promote directly. Keep OCR in Raw;
  distill a separate Candidate with evidence references for human review.

- Promoted pages get `status: active`, `human_reviewed_at`, and `importance: 0.7`
- If a draft carries a `source_note` (human intake comment), promote copies it
  verbatim onto the wiki page as `human_note` — the human's judgement survives.
- Rejected drafts leave the pending queue; OKS preserves a review receipt under `drafts/rejected/`
- Always confirm before rejecting
