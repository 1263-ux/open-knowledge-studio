# OKS Core-Loop Execution Plan

- Date: 2026-07-29
- Authority: `Open Knowledge Studio 执行任务.docx`
- Source SHA-256:
  `bb6c9aaaeea47135acb7b954ee3951d7694f6abd7bac2ee4e30163d3fd501cd2`
- Branch: `codex/upstream-v0.2.3-integration`
- Status: `in_progress`

## 1. Understanding of the target

The current objective is not to make OKS look like a complete platform. It is
to prove, with repeatable evidence, that a new Agent can use existing Skills,
plugins, CLIs, and the smallest necessary dependencies to complete:

```text
Source
  -> traceable Raw
  -> Agent-authored Candidate
  -> explicit human review
  -> Wiki
  -> Search / Recall
  -> grounded output
  -> measured quality comparison
```

Optional extractors and Feishu are valuable only when they strengthen this
loop. Claude Code Marketplace, OpenClaw Skill Hub, browser tooling, model APIs,
and mature extractors are external capabilities to reuse, not subsystems for
OKS to reimplement.

## 2. Non-negotiable boundaries

- Never promote a Candidate without an explicit human `接受`.
- Keep Raw extraction, Agent interpretation, human review, and Wiki promotion
  as separate auditable states.
- Preserve `passed`, `failed`, `partial`, `not_run`, `awaiting_human`, and
  `environment_limited`; never replace them with “basically passed”.
- Do not implement distributed Workers, queues, Kubernetes, a plugin market,
  an Agent framework, or speculative registries in this cycle.
- Do not delete unknown user changes. The existing Feishu capture redaction
  diff and untracked `/accept` Skill remain separate from book-POC commits.
- Every independently reversible stage gets its own local commit after
  `git diff --check` and the tests appropriate to that stage.
- No push, Pull Request change, deployment, or external message without the
  user authorizing that exact external action.

## 3. Current evidence and gaps

| Requirement | Current evidence | State |
|---|---|---|
| UTF-8 public-book ingestion | Commit `0f0c855`; Raw validator `valid=true` | passed |
| Traceable Raw | Original file and SHA retained; only document-level evidence | partial |
| Candidate | Source facts checked against Chapter 20, sections 241-252 | passed |
| Exact acquisition URL | Landing page retained; final TXT URL/redirect chain absent | failed |
| Human review | Candidate awaits explicit user decision | awaiting_human |
| Wiki/Search/Recall | Cannot run before review | not_run |
| A group | Local no-tools model; `1/6` fully correct, hallucinations observed | passed |
| B group and A/B score | Depends on approved Wiki and Recall | not_run |
| Draft review CLI | YAML date caused `oks drafts list` crash; fixed in `f6784a7` | passed_after_fix |
| Feishu public form by human | Programmatic submission only | not_run |
| Feishu native review event | Consumer ready and WebSocket connected; zero events delivered | failed |
| Feishu recovery | `reconcile-review` previously recovered missed reply | passed_recovery_only |
| Clean OpenClaw deployment | Old acceptance environments exist; new prompt run not completed | not_run |
| Architecture/docs convergence | Old architecture and broken/missing links remain | failed |
| Anti-bot/lightweight research | Required final report path absent | not_run |
| Kimi K3 case | Required Raw/Candidate/Wiki/case/desktop evidence absent | not_run |

## 4. Execution phases

### Phase A — finish the book knowledge loop

1. Present the reviewed Candidate and this audit to the user.
2. Wait for `接受`, or apply the user's explicit edit/reject/defer decision.
3. On acceptance, promote only inside the isolated book-POC KB.
4. Verify the promoted page, then run `oks search`, `oks recall`, and `oks lint`.
5. Give the same six questions to the B-group model with only recorded Recall
   context; preserve the prompt, recalled pages, model/version, and output.
6. Score A and B with one fixed rubric: correctness, core-fact coverage,
   source fidelity, traceability, hallucination rate, and practical usefulness.
7. Continue only if B shows measurable improvement. Otherwise diagnose Raw,
   Candidate granularity, Wiki structure, query, scoring, and context injection.
8. Update `docs/acceptance/book-poc-report.md` and commit the completed evidence.

Acceptance: the report contains commands, exit codes, paths, hashes, recalled
context, both answers, per-question scoring, and an honest conclusion about
whether OKS improved the output.

### Phase B — correct and retest the Feishu boundary

1. Create `docs/acceptance/feishu-e2e-status.md` with separate capture and
   review paths and corrected historical labels.
2. Verify a dedicated test Base exposes only the six human fields.
3. Give the public form URL to the user; the user must open it and submit a URL
   or attachment. API submission cannot satisfy this check.
4. In an isolated environment, let the Worker claim the record and request
   only the required extractor; verify Raw and Candidate.
5. Start a bounded event consumer and record its ready marker.
6. The user replies `接受`; only native `im.message.receive_v1` delivery,
   automatic association, promotion, and post-promotion recall count as real
   event-chain success.
7. Keep `reconcile-review` as a separately reported recovery test.

Acceptance: each assertion is one of the explicit states above. If the platform
does not deliver the event, Feishu remains `partial`.

### Phase C — clean-server Agent prompt validation

1. Hash and archive the reports that must survive.
2. List exact test-owned paths, environments, processes, and temporary files.
3. Confirm `/home/artboy-knowledge-studio`, OpenClaw itself, and unrelated
   services are outside the deletion set.
4. Remove only test-owned environments after exact-path and process checks.
5. Create a new isolated root and ask the existing OpenClaw Agent to follow one
   platform-neutral installation prompt from a clean state.
6. Record environment detection, package source/commit, install size/time,
   commands, exit codes, Raw/Candidate/human gate/Wiki/Recall/Lint evidence, and
   cleanup.

Acceptance: OpenClaw follows the prompt without source edits or hidden manual
repair. Any operator intervention is recorded as friction or failure.

### Phase D — converge docs and architecture

Create or update:

```text
docs/architecture/oks-core-architecture.md
docs/deployment/agent-one-prompt-installation.md
docs/acceptance/book-poc-report.md
docs/acceptance/feishu-e2e-status.md
docs/research/platform-antibot-and-lightweight-deployment.md
docs/cases/kimi-k3-deep-analysis.md
docs/future-considerations.md
README.md
```

The main diagram must show the core loop first, Feishu as an optional control
plane, Agent/runtime and external Skills as execution sources, explicit human
gates, and verified/partial/not-run status without implying that design equals
validation. Mermaid or SVG must render in GitHub Markdown, and all local links
must resolve.

### Phase E — anti-bot and lightweight deployment research

Use dated primary documentation and recorded tests to distinguish official API,
API key, OAuth, browser session, public fetch, mature third-party tool, and
restricted/not-recommended routes for YouTube, Bilibili, Web, PDF, and
script-rendered sources. Compare local versus remote OCR/ASR/document/video
providers by dependency weight, privacy, cost, provenance, stability, and
failure semantics. Do not claim an API key bypasses login, DRM, paid access, or
platform terms.

### Phase F — Kimi K3 case

1. Prefer official model card, technical report, official release material,
   and clearly labelled secondary analysis.
2. Ingest legal public sources through OKS and preserve platform failures.
3. Produce a Candidate with `[verified]`, `[inferred]`, `[user-stated]`, and
   `[unverified]` labels.
4. Stop for explicit human review before Wiki promotion.
5. After promotion, recall the K3 Wiki to write the case; compare a no-OKS
   baseline against the Recall-grounded report using the same rubric.
6. Save the final report in project docs and copy it to the requested desktop
   target(s), then verify file existence and hashes.

## 5. Current next action

The reviewed book Candidate is factually supported, but it now records one
additional provenance limitation: the exact final TXT acquisition URL was not
retained. It remains `awaiting_human`. The next irreversible semantic action is
Wiki promotion, so execution pauses at that gate until the user replies with
`接受` or an explicit edit/reject/defer instruction.
