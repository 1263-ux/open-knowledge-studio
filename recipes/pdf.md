# Recipe: PDF

source_type: pdf
description: Digital and scanned PDF documents.

required_capabilities:
  - document.text.extract

optional_capabilities:
  - document.structure.extract
  - document.render
  - image.ocr
  - image.observe
  - layout.understand

complete_when:
  - all_pages_accounted_for
  - text_or_observation_present_for_each_page

remote_processing:
  policy_required: true

degradation:
  primary:
    capability: document.text.extract
    providers: [pdf-lite, mineru, firecrawl]
  fallback:
    - capability: document.render
      providers: [mineru]
      condition: text_layer_empty
    - capability: image.ocr
      providers: [rapidocr, firecrawl]
      condition: rendered_pages_available
    - capability: image.observe
      providers: [agent-runtime]
      condition: page_images_available
    - capability: layout.understand
      providers: [agent-runtime]
      condition: table_or_chart_content_detected
    - capability: human.supply
      providers: [human]
      condition: all_automated_failed

notes: |
  Digital PDFs with text layers → pdf-lite (33 pages / 82K chars / 6.3s verified).
  Scanned PDFs → pdf-lite returns partial (49 chars) → rapidocr for OCR bbox
  + agent-runtime for page semantics (4 claims, offline verified).
  Remote OCR (firecrawl) requires user policy approval.
  MinerU is heavy (~300MB) — user must explicitly install.
