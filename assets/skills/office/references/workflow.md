# OKS Office workflow

This is the OKS-specific orchestration layer. The adapters do not recall,
rewrite claims, or upgrade evidence status.

## 1. Recall and evidence boundary

Run `oks recall ... --format json --explain`, read the full relevant Wiki pages,
and inspect linked Raw/Profile evidence only where it supports a claim or an
audience constraint. Record the recall query and selected slugs in the package.
Do not copy a score into prose as if it were evidence.

## 2. Claims before prose

Create the evidence package and map every material claim to `source_refs`.
Write the outline from claims, not from an untracked free-form draft. The
package validator is fail-closed: no empty source ledger, unknown id, missing
claim mapping, irregular table, or unsupported review state passes.

## 3. Template-first generation

When a user supplies a DOCX/PPTX template, keep it as the base artifact. Learn
only the reusable visual profile needed for this run: page/slide size, margins,
fonts, color tokens, heading hierarchy, table treatment, footer/header, and
available layouts. Never commit private templates or extracted personal data.

The preferred sequence is `extract → comprehend (if needed) → verify →
generate`. A scratch layout is allowed only when no template exists, and it
must be labeled as a portable fallback until visual QA passes.

## 4. Format adapters

- DOCX: when independently installed in the active host, use Anthropic's
  `docx` skill directly; otherwise use the `documents` skill. Preserve template
  styles and render every page. The bundled builder uses an explicit OKS Word
  design profile and fixed OOXML table geometry, but remains a deterministic
  local fallback, not a substitute for visual QA.
- PDF: use the `pdf` skill or controlled ReportLab generation. A CJK font is a
  hard input, not a warning. LibreOffice conversion must use a timeout and an
  isolated profile; keep the editable source when both are requested.
- PPTX: use the `presentations` skill and its artifact-tool production path.
  Inspect template thumbnails, use one decision per slide, add speaker notes
  when useful, validate the OOXML package, then render and inspect every slide.
  The bundled `python-pptx` path only proves portable serialization and
  evidence-preserving continuation; it is not a production design system.
- XLSX: use the `spreadsheets` skill or openpyxl for ordinary workbook work;
  preserve formulas and relevant worksheet features, then render or open-check
  the workbook. Power Query, Data Model, native PivotTables, and VBA require a
  separately probed native Excel Adapter.

`office.markitdown` is an input parser for Office → Markdown. It is not an
output adapter and must not be used to claim a generated deliverable.

## 5. QA and publish

Run the package preflight, then structural checks, then visual QA. A file
existing on disk is not acceptance. Publish to the requested output only after
the artifact is atomically written and the relevant pages/slides are inspected.
Record `visual_qa: unavailable` with the missing tool and the owner action when
rendering cannot run.
