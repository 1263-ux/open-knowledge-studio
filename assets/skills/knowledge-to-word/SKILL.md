---
name: knowledge-to-word
description: Backward-compatible Word-only entry point for OKS Office. Use when an existing workflow asks for this legacy skill name.
---

# Knowledge to Word (compatibility alias)

`knowledge-to-word` is retained so existing explicit Word/DOCX prompts and
automations keep working. Route the request to [`office`](../office/SKILL.md)
with `deliverables: ["docx"]` and follow its fixed research, OKS context,
document Adapter, and QA rules.

Do not maintain a separate recall, citation, template, or rendering policy
here. For template-preserving edits, current external research, or tracked
changes, use the Office document route. If its mature DOCX host skill is not
available, report `environment_limited` rather than generating a substitute
local document.
