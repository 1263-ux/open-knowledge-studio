---
name: knowledge-to-word
description: Create a polished, source-traceable Word document from relevant OKS Wiki, profile, and raw knowledge. Use when the user asks for a report, brief, proposal, or other .docx grounded in their knowledge base.
---

# Knowledge to Word

Turn recalled OKS knowledge into a human-readable `.docx` without writing generated prose back into `wiki/`.

## Workflow

1. Clarify the deliverable only when the audience, document type, or output path materially changes the result. Otherwise choose a sensible report structure and use `./output/<slug>.docx`.
2. Recall before drafting:

   ```bash
   oks recall "<topic and intended decision>" --limit 8 --format json --explain
   ```

   Prefer active-goal mode when the request names a goal. Treat recall output as a lead list, not as the complete evidence.
3. Read the full top Wiki pages with `oks wiki get <slug>`. Read linked `raw/` evidence or profiles only when they support a claim, audience context, or source caveat. Keep a source ledger of the exact path/slug used for each section.
4. Separate evidence from synthesis. Preserve uncertainty, confidence, review status, and conflicting sources. Do not turn a draft, raw excerpt, or unverified estimate into a fact.
5. Plan a compact document before authoring: title/decision summary, 2–5 topical sections, recommendations or next actions, then a source ledger. Use tables only for real comparisons or repeated fields.
6. Immediately before the first create/edit authoring command, run the documents workflow marker exactly once:

   ```bash
   node container_tools/mark_artifact_operation_started.mjs --operation-kind create --expected-output-count 1 --output-format docx
   ```

   Resolve bundled runtimes with `load_workspace_dependencies`; use the returned Python/Node paths rather than system runtimes.
7. Build the DOCX using the bundled document tooling or `scripts/build_docx.py` when a deterministic outline is sufficient. Human-facing citations must be normal labels such as `Wiki: <slug>` or `Raw: <path>`; never place tool citation tokens in the file.
8. Render and inspect every page with the documents skill's `render_docx.py`. Check clipping, page breaks, heading hierarchy, tables, Chinese glyphs, source labels, and empty pages. Fix the document and rerender if needed.
9. Deliver the DOCX path, a one-sentence evidence note, and any unresolved uncertainty. Do not claim a Word document was verified unless the latest render was inspected.

## Boundaries

- Read from `profiles/`, `wiki/`, and `raw/`; do not mutate them while generating a document.
- Never promote drafts or write directly to `wiki/` as part of this skill.
- Do not invent citations. If a claim has no supporting source, label it as synthesis or omit it.
- Keep private profiles and sensitive raw material out of the document unless the user explicitly asks for them and the output scope is clear.
- For a provided `.docx` template, preserve its style and use the documents skill's edit workflow instead of replacing it with the deterministic helper.

## Deterministic helper

Use `scripts/build_docx.py` for a repeatable builder when the agent has already recalled and curated the content into a JSON outline. The helper does not run recall and does not decide what is true; the agent remains responsible for evidence selection and citations.
