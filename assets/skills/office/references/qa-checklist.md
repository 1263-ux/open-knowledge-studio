# OKS Office QA checklist

## Evidence and content

- [ ] Package validator passes; schema version and request are present.
- [ ] Every material claim/block has a claim id and resolves to at least one source.
- [ ] Source labels, locators, statuses, recall query, and owner inputs remain visible or recoverable.
- [ ] External research sources carry a direct URL and retrieval time; they are not labeled reviewed without human review.
- [ ] The normalized outline is the same input for all requested formats.
- [ ] No generated step writes `wiki/`, `drafts/`, or `raw/`.

## Structural

- [ ] DOCX/PDF/PPTX/XLSX opens and has expected page/slide/sheet count.
- [ ] Tables are rectangular and preserve `0`, `False`, Chinese text, and long values.
- [ ] PPTX continuation slides preserve all source text; no silent truncation.
- [ ] OOXML package validation passes where the production adapter provides it.
- [ ] DOCX tables use fixed layout, explicit DXA widths, shaded/repeating headers, and a verified Word profile.
- [ ] CJK PDF has an explicit readable font; otherwise generation fails.
- [ ] XLSX formulas, validations, named ranges, number formats, and requested worksheet features survive the selected route.

## Visual

- [ ] Render every page and slide, not only the first.
- [ ] Check clipping, overflow, blank pages, glyphs, contrast, table density, and source ledger readability.
- [ ] Check template fidelity: page/slide geometry, styles, colors, headers/footers, and layouts.
- [ ] If rendering is unavailable, record `visual_qa: unavailable`, the missing dependency, and the human verification step.

## Delivery

- [ ] Artifact paths and evidence-package path are reported.
- [ ] Temporary smoke outputs are not presented as production-quality deliverables.
- [ ] The final result states any partial/failed/skipped/environment-limited evidence.
