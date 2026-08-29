# Office output contract

## Before generation

Create and validate one `oks-office-evidence/v1` package; see
[evidence-package.md](evidence-package.md). It records the fixed research
source, the OKS recall query, claim-to-source mapping, and source status. Run:

```powershell
python assets/skills/office/scripts/validate_evidence_package.py `
  --package tmp/oks-office-evidence.json
```

The package is an internal handoff to the selected mature format skill. Do not
generate from an untracked free-form outline.

## Delivery

Every deliverable includes a readable source ledger: a Sources section for a
document or PDF, source slide/notes for a presentation, or a Sources worksheet
or note for a spreadsheet. Preserve `partial`, `failed`, `skipped`, and
`environment_limited` statuses exactly.

| Format | Generator | Required QA |
|---|---|---|
| DOCX | Independently installed Anthropic `docx` host skill; otherwise `documents` | Render every page; inspect headings, tables, page breaks, Chinese glyphs, and source ledger |
| PDF | `pdf` skill or controlled mature conversion | Render every page; inspect fonts, clipping, page count, and selectable text |
| PPTX | `presentations` skill | Render every slide; inspect density, overflow, contrast, tables, and notes/source slide |
| XLSX | `spreadsheets` skill | Preserve formulas, validations, named ranges, formats, and relevant worksheet views; render or open-check the result |

If rendering is unavailable, report `visual_qa: unavailable` and the missing
tool; do not imply that visual acceptance occurred.
