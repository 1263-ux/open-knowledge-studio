---
name: office
description: Use only when the user explicitly asks to create, edit, review, or convert a Word/DOCX, Excel/XLSX, PowerPoint/PPTX, or PDF file. Research the topic, combine it with OKS knowledge, then create a checked, editable Office deliverable.
---

# OKS Office

`office` is the single user-facing entry point for explicit Office-file work.
It is an orchestrator, not an Office rendering engine.

## Trigger boundary

Use this skill only when the user explicitly names Word, DOCX, Excel, XLSX,
PowerPoint, PPTX, PDF, a supplied Office file, or asks to generate/edit/review
an Office document. Do **not** trigger it merely because a user says "write a
report", "summarize this", "make a plan", or asks a normal question. In those
cases, answer in the requested medium unless the user also requests an Office
file.

## Route every request

1. Identify the explicit file task: create, revise a supplied file, revise a
   currently open desktop file, analyze, or convert. Read
   [adapter routing](references/adapter-routing.md).
2. Research the topic as a fixed step. Prefer current primary sources, read the
   source page rather than a search snippet, and record its direct URL and
   retrieval time. Do not relabel agent-researched web material as `reviewed`
   until a human review has occurred.
3. Recall relevant OKS knowledge to add team context, prior decisions, and
   reviewed material. Read the full pages behind useful hits; recall scores are
   leads, not evidence.
4. Create one concise source ledger before prose or rendering. Internally it
   may be stored as `oks-office-evidence/v1`; it maps every material claim to
   a source and retains that source's review status. Read
   [the evidence contract](references/evidence-contract.md).
5. Follow the selected format workflow:
   [Word](workflows/document.md), [Excel](workflows/spreadsheet.md),
   [PowerPoint](workflows/presentation.md), [PDF](workflows/pdf.md), or
   [conversion](workflows/conversion.md).
6. Run the applicable structural checks and render-based visual QA. Deliver
   the editable artifact, a readable source ledger, and the QA result. Never
   call a file "visually accepted" without inspecting the latest render.

## Mature capability first

For DOCX, first use an independently installed mature host skill. When the
Anthropic `docx` skill is available in the active host, call it directly; it is
not copied into or redistributed by OKS because its upstream license is
Proprietary. In Codex environments, use the host `documents` skill when
available. If neither is available, report `environment_limited`; do not
replace a mature Office workflow with a local OOXML renderer. See
[document workflow](workflows/document.md).

For PPTX, XLSX, and live desktop editing, use the same rule: prefer the
specialized host or optional adapter only after its local probe passes; when it
is unavailable, report the environment limit rather than pretending a local
fallback provides the same capability.

## Boundaries

- Read from `profiles/`, `wiki/`, `raw/`, and directly cited external sources;
  do not mutate those knowledge stores while generating an artifact.
- Preserve `partial`, `failed`, `skipped`, and `environment_limited` exactly.
- Never fabricate citations, research findings, metrics, or an Adapter's
  readiness. Missing facts are owner input required or omitted.
- `office.markitdown` is Office-to-Markdown intake only, never a generator.
- Keep supplied templates and private source material local unless the user
  explicitly authorizes sharing them.
