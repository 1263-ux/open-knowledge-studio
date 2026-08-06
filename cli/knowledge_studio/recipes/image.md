# Recipe: Image

source_type: image
description: Screenshots, photos, scanned pages, diagrams.

required_capabilities:
  - image.observe

optional_capabilities:
  - image.ocr
  - layout.understand
  - chart.interpret

complete_when:
  - visual_content_described
  - embedded_text_ocr_or_observed

remote_processing:
  policy_required: false

degradation:
  primary:
    capability: image.observe
    providers: [agent-runtime, rapidocr]
  fallback:
    - capability: image.ocr
      providers: [rapidocr]
      condition: text_extraction_needed
    - capability: human.supply
      providers: [human]
      condition: all_automated_failed

notes: |
  Best path is hybrid: rapidocr for bbox + confidence (46 blocks/5.5s verified)
  + agent-runtime for page semantics (4 claims, identifies page context,
  video subtitles vs browser UI, account/date/interaction elements).
  Agent alone can understand what a page IS; OCR alone can tell what text IS.
  Neither alone is sufficient for complex screenshots.
