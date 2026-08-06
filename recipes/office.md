# Recipe: Office

source_type: office
description: DOCX, PPTX, XLSX, and HTML documents.

required_capabilities:
  - document.text.extract

optional_capabilities:
  - document.structure.extract
  - document.render
  - image.observe
  - chart.interpret
  - layout.understand

complete_when:
  - main_text_content_extracted
  - tables_preserved_when_present
  - slide_or_sheet_structure_accounted_for

remote_processing:
  policy_required: true

degradation:
  primary:
    capability: document.text.extract
    providers: [markitdown, firecrawl]
  fallback:
    - capability: document.structure.extract
      providers: [markitdown]
      condition: text_extraction_partial
    - capability: document.render
      providers: [mineru]
      condition: layout_complex
    - capability: chart.interpret
      providers: [agent-runtime]
      condition: charts_or_graphs_present
    - capability: human.supply
      providers: [human]
      condition: all_automated_failed

notes: |
  MarkItDown is the default local path (DOCX table structure preserved, PPTX
  list structure weaker than native, XLSX formulas lost).
  Firecrawl /parse is remote alternative (1 credit/file, ~1-3s).
  Complex layouts with formulas, embedded media, or charts need agent-runtime
  visual supplement (requires rendered pages — soffice/LibreOffice needed).
  Office 278MB dependency not in default lightweight install.
