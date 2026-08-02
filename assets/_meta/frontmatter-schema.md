# Frontmatter Schema v1.0

This file is the canonical metadata contract materialized by `oks init`.
The CLI is API-free: model configuration and credentials do not belong in these files.

## Wiki page

```yaml
---
title: "Use Typer for CLI tools"       # required, non-empty string
type: strategy                         # required: concept | strategy | anti-pattern
area: computing                        # required, non-empty string
status: provisional                    # provisional | active | stale | dropped | superseded
source_type: auto                      # auto | manual
importance: 0.7                        # number in [0, 1]
confidence: 0.8                        # number in [0, 1]
created: "2026-07-27T12:00:00Z"        # ISO-8601 date/time
pinned: false                          # boolean
archived: false                        # boolean
tags: "python, cli"                    # comma string or string list
fingerprint: "0123456789abcdef"        # optional content fingerprint
traces:                                # optional evidence references
  - id: "run-001"
    kind: execution
    url: "raw/executions/run-001/events.jsonl"
review:                                # optional review result
  decision_correct: true
  outcome: success
  lesson: ""
relates_to: "older-page"               # optional related page slug
relationship: confirms                 # supersedes | enriches | confirms | challenges
superseded_by: "newer-page"            # required when status=superseded
---
```

Required identity fields are `title`, `type`, and `area`. The CLI supplies defaults
for lifecycle fields when it creates a page. `access_count`, memory score, tier, and
quality score are computed at read time and must not be copied into frontmatter.

Relationship invariants:

- `relationship` and `relates_to` must appear together.
- `status: superseded` requires `superseded_by`.
- `traces` is a list of objects. Trace payloads must never contain credentials.

## Draft

```yaml
---
title: "CLI framework decision"
draft_type: strategy                   # concept | strategy | anti-pattern
draft_area: computing
source_pages: ["raw/source-note.md"]
source_note: "Optional provenance note"
drafted_at: "2026-07-27"
status: draft
---
```

A draft is a proposal. Promotion converts `draft_type` to `type` and `draft_area`
to `area`. AI-generated content must enter through `drafts/`; formal `wiki/`
promotion remains an explicit human action.

## Goal profile

```yaml
---
title: "Ship structured memory"
type: goal
status: active                         # active | inactive | completed
domains: [computing]
keywords: [recall, evaluation, trace]
---
```

Goal profiles live under `profiles/goals/`. `oks recall --goal active` merges active
profiles; `--goal <slug>` selects exactly one profile; `--goal none` is the baseline.

## Related machine contracts

- `recall-case.schema.json`: offline recall dataset
- `trace-event.schema.json`: append-only execution event
- `run-manifest.schema.json`: execution run manifest
- `learning-schema.json`: learning record
- `raw-evidence-schema.md`: generic raw evidence boundary
