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

`reviewed` means human-reviewed in the OKS lifecycle. Direct external research
must use a timezone-aware ISO 8601 retrieval time and may only be `unverified`,
`partial`, `failed`, `skipped`, or `environment_limited`. Claims based on it
cannot be `reviewed`; promote reviewed material through the OKS lifecycle
instead. The generated source ledger makes provisional research visible.

## Research procedure

1. Research the topic as a fixed baseline. Prefer the primary issuer,
   regulator, standard, paper, or vendor.
2. Read the target page, record its direct URL and retrieval time, and capture
   only claims the page supports. Search result snippets are not evidence.
3. Recall relevant OKS knowledge to add team context, reviewed material, and
   prior decisions. Read the full selected pages; a recall score is a lead, not
   evidence. Record a non-empty recall query even when it returns no relevant
   local material.
4. If a source cannot be read, preserve `failed`, `partial`, `skipped`, or
   `environment_limited`; do not turn it into a confident claim.
5. Write the package before authoring. Each claim, summary, section, and block
   must resolve to source ids through claim ids.

Run the executable fail-closed validator before any renderer:

```powershell
python assets/skills/office/scripts/validate_evidence_package.py `
  --package tmp/oks-office-evidence.json --json
```

Place a copy of the validated package beside the final artifact as
`<artifact>.evidence.json` when provenance must survive beyond the local run.
