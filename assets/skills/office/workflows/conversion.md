# Conversion workflow

`office.markitdown` is the default intake route for DOCX, PPTX, and XLSX to
Markdown. It supports evidence acquisition, not document generation. Retain
the original asset and mark formulas, embedded media, and complex layout as
partial when extraction cannot establish fidelity.

When converting editable Office files to PDF, use an isolated temporary
profile and timeout. Retain both source and converted outputs, then render the
PDF for visual comparison. Report conversion limitations separately from
source evidence status.
