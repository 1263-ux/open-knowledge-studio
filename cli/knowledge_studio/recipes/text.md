# Recipe: Text

source_type: text
description: Plain text, Markdown, CSV files. Zero-dependency read.

required_capabilities:
  - document.text.extract

optional_capabilities:
  - metadata.fetch

complete_when:
  - full_text_content_available

remote_processing:
  policy_required: false

degradation:
  primary:
    capability: document.text.extract
    providers: [text-read, agent-runtime]
  fallback:
    - capability: human.supply
      providers: [human]
      condition: primary_returned_failed

notes: |
  Text files are the simplest source type.  Agent reads the file directly
  (provider: text-read or agent-runtime).  No external tools needed.
  Content hash is computed from raw bytes.  Locator uses kind=document.
