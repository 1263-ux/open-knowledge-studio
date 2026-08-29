# OKS Office evidence package

The evidence package is the source-of-truth handoff between OKS recall and
Office adapters. It prevents a document from having a decorative Sources page
while its material claims are untraceable.

## Minimum shape

```json
{
  "schema_version": "oks-office-evidence/v1",
  "request": {
    "title": "Deliverable title",
    "audience": "Decision makers",
    "deliverables": ["docx", "pdf", "pptx"]
  },
  "recall": {
    "query": "the OKS recall query",
    "items": [{"slug": "wiki-page", "score": 0.82, "explain": "topic match"}]
  },
  "summary": {
    "text": "A bounded summary.",
    "claim_refs": ["claim-1"]
  },
  "claims": [
    {
      "id": "claim-1",
      "text": "A material statement from the recalled knowledge.",
      "source_refs": ["src-1"],
      "confidence": "high",
      "review_status": "reviewed"
    }
  ],
  "sections": [
    {
      "id": "section-1",
      "title": "What the evidence supports",
      "claim_refs": ["claim-1"],
      "blocks": [
        {"type": "paragraph", "text": "...", "claim_refs": ["claim-1"]},
        {"type": "bullets", "items": ["..."], "claim_refs": ["claim-1"]},
        {"type": "table", "rows": [["Metric", "Value"], ["Count", 0]], "claim_refs": ["claim-1"]}
      ]
    }
  ],
  "sources": [
    {"id": "src-1", "kind": "wiki", "label": "Wiki: wiki-page", "locator": "wiki/page.md", "status": "reviewed"},
    {"id": "src-research-1", "kind": "research", "label": "Research: primary source", "locator": "https://example.org/source", "retrieved_at": "2026-08-27T10:00:00+08:00", "status": "unverified"}
  ]
}
```

Every package must contain at least one `web` or `research` source from the
fixed research step and a non-empty OKS recall query. For `kind: web` or
`kind: research`, `locator` must be a direct HTTP(S) URL and `retrieved_at`
must be a timezone-aware ISO 8601 timestamp. Direct external research cannot
be `reviewed`; claims based on it remain `provisional` or `unverified`.

The validator requires every claim, summary, section, block, and object-form
bullet to point to known ids. It does not create or render an Office file;
the selected mature format skill owns that work.

Use the executable validator before authoring:

```powershell
python assets/skills/office/scripts/validate_evidence_package.py `
  --package tmp/oks-office-evidence.json --json
```

The package is data, not a place to invent missing facts. If a source is
partial, failed, skipped, unverified, or environment-limited, retain that
status and let the document state the limitation.
