---
description: Prepare local oral videos as review bundles, then add human-approved Markdown to raw/misc/
---

# /media-ingest — Human-Gated Oral Video Intake

## Purpose

Convert a user-provided local oral video into a reviewable evidence bundle without changing the existing Raw → Draft → Wiki pipeline.

## Rules

- Start with oral videos only.
- Never summarize or invent missing content during preparation.
- Never write directly to `drafts/` or `wiki/`.
- `prepare` writes only to `.oks/intake/`.
- Before `approve`, ask the user to review `candidate.md` and `quality-report.md`.
- Only run `approve --confirm-human-review` after explicit user approval.
- Preserve the source URL, save reason, original ASR, warnings, and content hash.

## Workflow

1. Confirm the local video path, source URL, title, and save reason.
2. Install optional dependencies from `scripts/media_ingest_requirements.txt` when needed.
3. Run `python scripts/media_ingest.py prepare ...`.
4. Show the user the generated candidate and quality report paths.
5. Wait for explicit review approval.
6. Run `python scripts/media_ingest.py approve <capture-id> --confirm-human-review --review-note "..."`.
7. Hand the resulting `raw/misc/*.md` file to the existing `/ingest` skill.

See `docs/media-ingest.md` for command examples and current limitations.
