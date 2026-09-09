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
here. For a mature DOCX host skill, template-preserving edits, current external
research, or tracked changes, use the Office document route. The local
`scripts/build_docx.py` helper remains a compatibility fallback only when the
Office route explicitly selects it.
