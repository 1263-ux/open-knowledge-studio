# OKS Office workflow

This is the OKS-specific orchestration layer. The adapters do not recall,
rewrite claims, or upgrade evidence status.

## 1. Research and OKS context

Research every Office request first. Prefer primary sources, read the target
page rather than a search snippet, and record each direct URL and retrieval
time. Then run `oks recall ... --format json --explain`, read the full relevant
Wiki pages, and inspect linked Raw/Profile evidence only where it supports a
claim or audience constraint. Record the recall query and selected slugs in the
package. Do not copy a score into prose as if it were evidence.

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
generate`. A scratch layout is allowed only when no template exists; it must
still pass the selected mature skill's visual QA.

## 4. Format adapters

- DOCX: when independently installed in the active host, use Anthropic's
  `docx` skill directly; otherwise use the `documents` skill. Preserve template
  styles and render every page.
- PDF: use the `pdf` skill or controlled mature conversion. A CJK font is a
  hard input, not a warning. LibreOffice conversion must use a timeout and an
  isolated profile; keep the editable source when both are requested.
- PPTX: use the `presentations` skill and its artifact-tool production path.
  Inspect template thumbnails, use one decision per slide, add speaker notes
  when useful, validate the OOXML package, then render and inspect every slide.
- XLSX: use the `spreadsheets` skill for ordinary workbook work; preserve
  formulas and relevant worksheet features, then render or open-check the
  workbook. Power Query, Data Model, native PivotTables, and VBA require a
  separately probed native Excel Adapter.

`office.markitdown` is an input parser for Office → Markdown. It is not an
output adapter and must not be used to claim a generated deliverable.

## 5. QA and publish

Run evidence validation, then the format skill's structural checks and visual QA. A file
existing on disk is not acceptance. Publish to the requested output only after
the artifact is atomically written and the relevant pages/slides are inspected.
Record `visual_qa: unavailable` with the missing tool and the owner action when
rendering cannot run.
