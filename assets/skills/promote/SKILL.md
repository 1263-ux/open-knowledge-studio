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

- Promoted pages get `status: active` and `human_reviewed_at`. Human approval
  records the review; it does not automatically raise the draft's confidence.
- Preserve the draft's `importance` and `confidence`, including explicit `0`.
  Both fields must be YAML numbers in `[0, 1]`; invalid values stop promotion
  and leave the draft intact. When omitted, new pages default to `importance: 0.7`
  and `confidence: 0.8` for compatibility with older drafts.
- When the body matches an existing Wiki page, promotion reuses that page and
  records the review. An explicit draft `confidence` replaces the existing
  assessment without a reconfirmation boost. Without that field, the existing
  reconfirmation rule applies.
- Use `draft_type` and `draft_area` in Candidate frontmatter; `type` and `area`
  do not select the promotion destination. Missing fields default to `concept`
  and `computing`; `--type` and `--area` override those choices during review.
- If a draft carries a `source_note` (human intake comment), promote copies it
  verbatim onto the wiki page as `human_note` — the human's judgement survives.
- Rejected drafts leave the pending queue; OKS preserves a review receipt under `drafts/rejected/`
- Always confirm before rejecting
