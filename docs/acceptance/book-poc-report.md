# Book Knowledge Loop POC

- Date: 2026-07-28
- Overall status: `awaiting_human`
- Scope: one public-domain book chapter, one isolated OKS instance
- Book: Charles Babbage, *On the Economy of Machinery and Manufactures* (1832)
- Chapter: Chapter 20, "On the Division of Labour"
- Public source: <https://www.gutenberg.org/ebooks/4238>

## Task record: core direction

1. **Core problem.** OKS must turn external knowledge into traceable Raw
   material, an Agent-authored Candidate, a human-approved Wiki page, relevant
   recall, and a source-grounded output whose quality can be measured.
2. **Distinctive capability.** The useful product surface is the lifecycle and
   recall contract, not a new extraction platform or Agent framework. Current
   work remains on that surface only where it improves provenance, review, or
   recall.
3. **Recent design relevance.** The built-in connector and optional extractors
   serve capture. Further Worker modularization, generic registries, and new
   orchestration layers are not prerequisites for this POC.
4. **Over-design check.** The repository has accumulated optional modality and
   Feishu work ahead of a measured book loop. No new platform layer will be
   added in this POC.
5. **Reuse.** This run reused the existing `oks` CLI, the bundled connector,
   MarkItDown, the existing draft promotion and recall implementation, Project
   Gutenberg, and local Ollama for an independent A-group answer.
6. **Duplication check.** OKS should not recreate a Skill marketplace, browser,
   Agent runtime, model server, or extraction ecosystem. It should call those
   capabilities and preserve their evidence and failure states.

The first loop is **not complete yet**. Capture and Candidate generation have
run; Wiki promotion is intentionally blocked on human review. Search/recall,
the B-group answer, and the final quality comparison remain `not_run` until
that gate is satisfied.

## Source and location

| Field | Evidence |
|---|---|
| Downloaded file | Project Gutenberg UTF-8 plain text |
| Bytes | `645369` |
| SHA-256 | `08cfd812da8c31ceb2085f7a01cb54c3073c84dd2f7dd5a65285c3f1d3358ace` |
| Source location | lines `5818-6176` in the downloaded file |
| Raw location | lines `5709-6062` in `content.md` |
| Author paragraph range | sections 241-252 |

The isolated run lives under `.codex-tmp/book-poc/kb`. It does not change the
repository's existing Raw/Wiki state or the user's global OKS configuration.

## Pipeline status

```yaml
source_download: passed
source_hash_verification: passed
oks_init_isolated: passed
raw_bundle_generation: passed
raw_bundle_validation: passed
raw_processing_status: partial
exact_fetch_url_recording: failed
candidate_generation: passed
human_review: awaiting_human
wiki_promotion: not_run
search: not_run
recall: not_run
a_group_without_oks: passed
b_group_with_oks: not_run
quality_comparison: not_run
clean_reproduction: not_run
```

Raw is `partial`, not `complete`: coverage checks passed and the original file
was preserved, but the extractor emits one document-level evidence record and
does not provide page or paragraph locators for plain text. The Candidate adds
auditable file-line and author-paragraph locations, but that does not erase the
Raw evidence limitation.

The Project Gutenberg landing page and the downloaded file's SHA-256 are
recorded, but the acquisition run did not preserve the exact final plain-text
download URL or redirect chain. The local original remains verifiable; network
acquisition provenance for this run is incomplete.

## Observed product failure and fix

The first ingestion attempt failed because MarkItDown's plain-text converter
used ASCII decoding for a UTF-8 Project Gutenberg file. Commit `0f0c855` passes
explicit UTF-8 `StreamInfo` for TXT, Markdown, and CSV inputs and adds a
non-ASCII regression test.

Verification:

```text
4 targeted MarkItDown tests passed
147 repository tests passed
git diff --check passed
same-source ingest rerun exited 0
Raw validator returned valid=true
```

## Candidate review gate

Candidate:
`.codex-tmp/book-poc/kb/drafts/babbage-division-of-mental-labour.md`

Reviewed Candidate SHA-256:
`9392090bfb466043eea945d0a20ae2b9b9ec5a4f7cae7ed75e3cf9e456f741a1`.

It separates source-supported facts from `[inferred]` engineering lessons and
records the source URL, SHA-256, chapter, source lines, Raw lines, and author
paragraph numbers. Promotion must not occur until a human accepts or edits it.

On 2026-07-29 the Candidate's seven source-supported claims were checked
against source lines 5872-6084 and Raw lines 5763-5973. No unsupported factual
claim was found. Its two engineering lessons remain explicitly `[inferred]`.
The review added the missing acquisition-URL limitation. Human acceptance is
still outstanding.

The same review exposed a separate CLI failure: YAML parsed `drafted_at` as a
`date`, causing `oks drafts list` to crash before review. Commit `f6784a7`
converts display cells to strings and adds a regression test. Verification:

```text
6 targeted CLI tests passed
148 repository tests passed
oks drafts list displayed the Candidate and 2026-07-28
git diff --check passed
```

## Acceptance questions

1. What were the responsibilities and approximate sizes of de Prony's three
   sections?
2. Why were two workshops used, and what assurance did that provide?
3. What surprising accuracy observation did Babbage make about the third
   section?
4. Which section did Babbage expect a calculating engine to replace, and what
   work would remain for analysts?
5. Which three initial values are sufficient in the square-number difference
   example, and why?
6. What two conditions does the chapter give for extensive division of labour?

## A group: no OKS recall

The local `gpt-oss:20b` model answered in an isolated, no-tools, no-network
context. The response was materially wrong:

- invented section sizes and physical-fabrication responsibilities;
- expanded reciprocal checking into unsupported machinery-failure redundancy;
- invented a quotation about physical tolerances;
- said the engine would replace section II instead of section III;
- gave `1, 4, 3` instead of the source's `1, 3, 2` seeds;
- replaced the stated demand/capital constraints with generic workflow advice.

Baseline artifact: `.codex-tmp/book-poc/baseline/a-group.md`.

| Metric | A-group result |
|---|---:|
| Answer correctness | `1/6` fully correct |
| Core-fact coverage | `2/6` partially present |
| Source fidelity | `failed` |
| Traceability | `0/6` answers cited |
| Hallucination control | `failed` (unsupported quote and details) |

These values are provisional until the B-group response is generated and both
groups are scored with the same rubric.

## Current primary failure points

1. Human review has not yet occurred, so the knowledge loop cannot be marked
   complete.
2. Plain-text Raw evidence has document-level rather than paragraph-level
   locators.
3. Raw warning strings are mojibake in generated JSON even though extracted
   source text is correct UTF-8.
4. A cloud Codex baseline attempt was `environment_limited`: repeated transport
   timeouts ended in `401` from an expired API key. The local model supplied the
   successful independent baseline instead.

## Next gate

A human must review the Candidate and choose `accept`, `edit`, `reject`, or
`defer`. Only `accept` or an approved edit permits Wiki promotion and the B
group experiment.
