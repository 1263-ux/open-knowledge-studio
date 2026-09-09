---
description: Prepare local oral or screen-recording videos as review bundles, then add human-approved Markdown to raw/misc/
---

# /media-ingest — Human-Gated Video Intake

## Purpose

Convert a user-provided local video into a reviewable evidence bundle without changing the existing Raw → Draft → Wiki pipeline.

## Rules

- Support only local oral and screen-recording videos in this stage.
- Never summarize or invent missing content during preparation.
- Never write directly to `drafts/` or `wiki/`.
- `prepare` writes only to `.oks/intake/`.
- Before `approve`, ask the user to review `candidate.md` and `quality-report.md`.
- Only run `approve --confirm-human-review` after explicit user approval.
- Preserve the source URL, save reason, original ASR, warnings, and content hash.

## Workflow

The module ships as `oks_connector.media_ingest`. Invoke it as
`python -m oks_connector.media_ingest` after `pipx install`, or as
`python scripts/media_ingest.py` from a source checkout.

1. Confirm the local video path, source URL, title, save reason, and whether the content is oral or screen-based.
2. Install optional dependencies when needed. `scripts/media_ingest_requirements.txt`
   exists only in a source checkout — it is not packaged, so on an installed
   copy read the imports the run reports as missing and install those.
3. Run `python -m oks_connector.media_ingest prepare ...`.
4. Show the user the generated candidate and quality report paths.
5. Wait for explicit review approval.
6. Run `python -m oks_connector.media_ingest approve <capture-id> --confirm-human-review --review-note "..."`.
7. Hand the resulting `raw/misc/*.md` file to the existing `/ingest` skill.

This local-video command is an experimental adapter, not the canonical multimodal pipeline. The canonical contract and capability manifests live in the independent `oks-connector` repository under `schemas/` and `capabilities/`.
