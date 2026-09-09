# Office output contract

## Evidence package (preferred)

The preferred input is `oks-office-evidence/v1`; see
[evidence-package.md](evidence-package.md). It requires a source mapping for
each material claim and each rendered block. `build_office.py --package` and
`validate_evidence_package.py` normalize it into the outline below without
changing the claim text.

## Legacy outline

The adapters accept a JSON object with this minimum shape:

```json
{
  "title": "Deliverable title",
  "subtitle": "Audience or decision context",
  "summary": "Evidence-bounded executive summary",
  "summary_source_refs": ["oks-page-1"],
  "sections": [
    {
      "heading": "Section heading",
      "source_refs": ["oks-page-1"],
      "paragraphs": ["Paragraph text"],
      "bullets": ["Short point"],
      "tables": [
        {"rows": [["Column", "Value"], ["A", "B"]], "source_refs": ["oks-page-1"]}
      ]
    }
  ],
  "sources": [
    {"id": "oks-page-1", "label": "Wiki", "path": "wiki/example.md", "status": "reviewed"}
  ]
}
```

`title`, `sections`, and `sources` are required for a source-traceable output.
Every material section must have non-empty `source_refs` pointing to source
`id` values. A paragraph or bullet may be a string (inheriting the section
scope) or an object such as `{"text": "Claim", "source_refs": ["oks-page-1"], "claim_statuses": ["reviewed"]}`
when it needs a narrower source mapping. A non-empty summary requires
`summary_source_refs`. Source entries require non-empty `id`, `label`, `path`,
and a status from `reviewed`, `partial`, `failed`, `skipped`,
`environment_limited`, `unverified`, or `synthesis`. The normalized outline
may contain `tables` (each with `rows`, `source_refs`, and optional
`claim_statuses`); the singular `table` remains a legacy input. The builder renders text
literally; it does not infer or upgrade evidence status. Keep source labels
human-readable (`Wiki: <slug>`, `Raw: <path>`, or `Synthesis: <reason>`).

## Adapter expectations

| Format | Generator | Required QA |
|---|---|---|
| DOCX | Independently installed Anthropic `docx` host skill when available; otherwise `documents`; `python-docx` fallback for portable smoke | Render every page; inspect headings, tables, page breaks, Chinese glyphs, and source ledger |
| PDF | ReportLab for direct generation, or LibreOffice for a controlled conversion | Render every page; inspect fonts, clipping, page count, and selectable text |
| PPTX | `presentations` skill with artifact-tool for production; `python-pptx` only for portable smoke tests | Render every slide; inspect density, overflow, contrast, tables, and notes/source slide |
| XLSX | `spreadsheets` skill for production; `openpyxl` fallback | Preserve formulas, validations, named ranges, formats, and relevant worksheet views; render or open-check the result |

Use LibreOffice headless conversion only as a separately reported conversion
step with a timeout and isolated profile. It can improve interoperability, but
it does not prove that the source document's layout or semantics survived.
Keep the original artifact when both the editable source and PDF are requested.

## Evidence and failure states

Every output should retain a final Sources section or source slide. If a source
is partial, failed, skipped, or environment-limited, preserve that status in
the ledger. The portable PPTX smoke adapter splits long content into
continuation slides instead of dropping it; production decks must use the
`presentations` skill. If rendering is unavailable, report
`visual_qa: unavailable` rather than implying acceptance.
