# Office evidence contract

`oks-office-evidence/v1` is the immutable handoff from knowledge selection to
an Office adapter. It is deliberately separate from the editable artifact so
a Word, PPTX, PDF, and XLSX cannot quietly diverge in factual content.

## Evidence sources

Use `wiki`, `raw`, `profile`, `template`, or `synthesis` for local material.
Use `web` or `research` only for externally obtained material. Each external
source must contain an `http(s)` `locator` and `retrieved_at` timestamp.

```json
{
  "id": "src-web-1",
  "kind": "research",
  "label": "Research: issuer publication",
  "locator": "https://example.org/report",
  "retrieved_at": "2026-08-27T10:00:00+08:00",
  "status": "unverified"
}
```

`reviewed` means human-reviewed in the OKS lifecycle. An Agent may evaluate a
primary external source, but it must record it as `unverified` or `partial`
until a human has reviewed it. Claims based on external research are normally
`provisional`; the generated source ledger makes that visible.

## Research procedure

1. Use OKS recall first and identify the exact knowledge gap.
2. Research only material gaps, current facts, or user-requested external
   context. Prefer the primary issuer, regulator, standard, paper, or vendor.
3. Read the target page, record its direct URL and retrieval time, and capture
   only claims the page supports. Search result snippets are not evidence.
4. If a source cannot be read, preserve `failed`, `partial`, `skipped`, or
   `environment_limited`; do not turn it into a confident claim.
5. Write the package before authoring. Each claim, summary, section, and block
   must resolve to source ids through claim ids.

Run the executable fail-closed validator before any renderer:

```powershell
python assets/skills/office/scripts/validate_evidence_package.py `
  --package tmp/oks-office-evidence.json --json `
  --normalized-outline tmp/oks-office-outline.json
```

Place a copy of the validated package beside the final artifact as
`<artifact>.evidence.json` when provenance must survive beyond the local run.
