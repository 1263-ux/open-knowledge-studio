<div align="center">

<img src="images/oks-logo-readme.png" width="360" alt="Open Knowledge Studio">

### Open Knowledge Studio: A Filesystem-First External Memory for Coding Agents

English / [中文](README.zh.md)

[![](https://img.shields.io/github/v/release/open-agent-power/open-knowledge-studio?color=369eff\&labelColor=black\&logo=github\&style=flat-square)](https://github.com/open-agent-power/open-knowledge-studio/releases)
[![](https://img.shields.io/github/stars/open-agent-power/open-knowledge-studio?labelColor\&style=flat-square\&color=ffcb47)](https://github.com/open-agent-power/open-knowledge-studio)
[![](https://img.shields.io/github/issues/open-agent-power/open-knowledge-studio?labelColor=black\&style=flat-square\&color=ff80eb)](https://github.com/open-agent-power/open-knowledge-studio/issues)
[![](https://img.shields.io/badge/license-MIT-white?labelColor=black\&style=flat-square)](./LICENSE)
[![](https://img.shields.io/github/last-commit/open-agent-power/open-knowledge-studio?color=c4f042\&labelColor=black\&style=flat-square)](https://github.com/open-agent-power/open-knowledge-studio/commits/main)

[Documentation](https://open-agent-power.github.io/open-knowledge-studio/) · [Experiments](#proof-it-works) · [Reproduce](#reproduce) · [Changelog](./CHANGELOG.md)

</div>

***

## What is Open Knowledge Studio

Open Knowledge Studio (OKS) is an open-source **filesystem-first external memory** for coding agents. Instead of a black-box vector store, it stores knowledge as a human-reviewable, git-versioned filesystem — `profiles/`, `raw/`, `wiki/`, `drafts/`, `mail/` — that an Agent browses with `oks recall`, `oks wiki list`, and `oks trace`. Content moves through a reviewable pipeline (Source → EvidenceFragment → Manifest → Raw → Candidate → human review → Wiki), decays like real memory, and is recalled on demand. Full introduction: [Start here](https://open-agent-power.github.io/open-knowledge-studio/).

```
your source → Candidate → human review → Wiki → Recall → injected into Agent context
```

## Why Open Knowledge Studio

- **One filesystem for all memory.** Profiles, raw materials, curated wiki, drafts, and agent mail each get a directory with a different trust boundary. An Agent locates and manipulates context deterministically, like a developer working with files. → [File-system paradigm](https://open-agent-power.github.io/open-knowledge-studio/concepts/file-system-paradigm/) · [Memory model](https://open-agent-power.github.io/open-knowledge-studio/concepts/memory-model/)
- **Human review is the gate.** Raw material ≠ conclusion; Candidate ≠ long-term knowledge. Nothing auto-promotes to Wiki — every durable memory is human-approved. → [Dreaming cycle](https://open-agent-power.github.io/open-knowledge-studio/concepts/memory-model/#dreaming)
- **Triple-Layer Recall cuts hallucination.** Node-BM25 retrieves *what* matches, Soul Boost reorders *what reaches* the Agent (anti-pattern ×1.5, review bonus, generic demotion), Memory Curve scores *how fresh* — so confidence never outranks truth. → [Recall engine](https://open-agent-power.github.io/open-knowledge-studio/algorithms/recall-engine/)
- **Knowledge decays like real memory.** Unused pages cool down through hot → warm → cold → evictable tiers; used pages resurface. `importance × e^(-λ×days) + ln(1+access) + pin_bonus`. → [Decay system](https://open-agent-power.github.io/open-knowledge-studio/algorithms/decay-system/)
- **Every recall is observable.** Each query preserves its factor scores and match path (`oks recall "<q>" --explain`); every injection is logged to `records/inject.jsonl`. When a result looks wrong, you see exactly which factor produced it. → [Evaluation](https://open-agent-power.github.io/open-knowledge-studio/algorithms/recall-evaluation/)

How the pieces fit together: [Architecture](https://open-agent-power.github.io/open-knowledge-studio/architecture/oks-core-architecture/). The thinking behind the design: [CONSTITUTION.md](./CONSTITUTION.md).

```
open-knowledge-studio/
├── profiles/              # team, users, projects, recipes, goals — stable context
├── raw/                    # human-collected sources, date-based {YYYY}/{MM}/{DD}/{source}/
├── wiki/                   # human-reviewed memory: concept, strategy, anti-pattern
├── drafts/                 # Candidate proposals, awaiting review
├── mail/                   # agent-to-agent: inbox/ + sent/ — never long-term knowledge
├── settings/               # recall.yaml (single param source), tool registry
├── _meta/                  # schema layer: raw evidence, recall case, trace event
└── records/                # versioned acceptance evidence + experiment runs
```

The three recall layers:

- **Node-BM25 (retrieval)**: SQLite FTS5 + BM25 over markdown `##` headings, column weights title 5× > tags 3× > body 1× > code 0.5×. No file reads during retrieval (abstract zero-read, v0.6.10).
- **Soul Boost (injection)**: type_boost + review_bonus + generic_demotion reorder hits before they reach the Agent — failure lessons rank higher than generic concepts.
- **Memory Curve (decay)**: type-specific λ, access_count ln-growth, pin_bonus — independent of backend, runs in `store.py`.

## Proof it works

OKS has been evaluated on a 50-case semantic-paraphrase dataset (strict exact-slug match). Full results, ablation tables, and reproduction scripts are in [docs/algorithms/recall-evaluation.md](./docs/algorithms/recall-evaluation.md); the dataset and run JSONs live in [./records/experiments](./records/experiments).

### Triple-Layer ablation — 50-case, strict exact-slug match

Queries are semantic paraphrases — the query does not contain the slug's keyword, testing synonym/rewrite recall. Match is strict: the expected slug must appear in top-k.

| backend | R@1 | R@3 | MRR | nDCG@5 | p50 |
|---------|------|------|------|---------|------|
| **fts5 (full Triple-Layer)** | **0.825** | **0.925** | **0.907** | **0.893** | 93ms |
| native (page-level 6+1, no Node-BM25) | 0.525 | 0.647 | 0.630 | 0.624 | 137ms |
| fusion (fts5 + native re-rank) | 0.805 | 0.905 | 0.900 | 0.887 | 226ms |

- **Node-BM25 dominates page-level 6+1**: R@1 +57% (0.525→0.825), MRR +44% (0.630→0.907). Multi-word same-section BM25 scores high; synonym/rewrite recall is precise.
- **Soul Boost must live in injection, not retrieval**: native 6+1's memory curve / goal boost / review bonus applied as retrieval re-rank *lowers* precision (R@1 0.825→0.805) — irrelevant pages score high and displace exact matches.
- **fts5 is also faster**: 93ms vs native 137ms vs fusion 226ms. SQLite persistent index beats live traversal.

### Embedding backend — semantic recall comparison (v0.6.2)

| backend | R@1 | MRR | p50ms |
|---------|------|------|-------|
| **fts5 (Node-BM25 literal)** | **0.825** | **0.907** | 93 |
| embedding (MiniLM cosine) | 0.617 | 0.733 | 18304 |

- On a small Chinese-term-heavy KB, BM25 literal already hits (terms overlap with wiki); embedding's semantic generalization introduces noise — and is 197× slower.
- **Decision**: fts5 stays default. Embedding is a **fallback** for fts5-miss cases, not a replacement. Embedding's real value is large KBs + cross-lingual + synonym-heavy domains.

### Layer-by-layer ablation

| Ablation | Remove what | R@1 | MRR | Proves |
|---------|-------------|------|------|--------|
| Full Triple-Layer | — | 0.825 | 0.907 | baseline |
| Remove Node-BM25 | retrieval fts5→native | 0.525 | 0.630 | Node-BM25 is the precision engine (−36%) |
| Remove Soul Boost (fusion misuse) | soul moved to retrieval re-rank | 0.805 | 0.900 | soul in injection = right; re-rank in retrieval = negative optimization |

### Abstract zero-read & tier degradation (v0.6.10 / v0.6.12)

- **Abstract zero-read**: fts5 schema `node-v2` added an `abstract` column; `body_preview` reads it from SQLite — **zero file reads during retrieval**. R@1 held (0.429), p50 121ms (slightly faster).
- **Tier degradation**: `_apply_budget()` degrades hits by tier when a token budget is hit — L2 (full, 200c) → L1 (overview, 100c) → L0 (abstract, 50c) → title-only (0c, rel < `0.5`) → truncate. Verified: 5×200c under 300c budget → 150c ≤ 300.

> These numbers are historical baselines from one knowledge base at one point in time, not a universal SLA. Re-run any of them — see [Reproduce](#reproduce).

## Quick start

> 💡 **New to OKS?** Read [start-here](https://open-agent-power.github.io/open-knowledge-studio/) first — it walks through the memory lifecycle and where OKS fits in your Agent stack.

Requires Python 3.10+.

```bash
pipx install open-knowledge-studio && pipx ensurepath
oks init my-knowledge-base
cd my-knowledge-base
oks status          # wiki count, tier distribution, drafts, quality
oks recall "git branch"   # Triple-Layer recall → injects matched memory
```

Optional auto-recall hooks (wire recall into your Agent host):

```bash
oks hook install --editor claude   # or: qoder | codex | both
oks skills-install                # bundle skills + agent-config into .claude/.qoder/.pi/.codex
```

Next steps:

- CLI reference, hook configuration, and evaluation: [CLI docs](https://open-agent-power.github.io/open-knowledge-studio/reference/cli/) · [Context injection](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/)
- Backup, export, and conversations: [Backup & export](https://open-agent-power.github.io/open-knowledge-studio/connect/backup-export/)

## Use it with your agent

OKS injects reviewed memory into your Agent's context on every prompt (UserPromptSubmit) and detects conflicts after each tool call (PostToolUse → `mail/`):

- [Claude Code](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) — `.claude/hooks/` + `settings.json`
- [Codex](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) — `.codex/hooks.json`
- [qoder](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) — `.qoder/settings.json` (shares `.claude/hooks/`)
- [pi](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) — `.pi/extensions/*.ts` (TS extension, shares `.claude/hooks/`)
- [Other shells](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) — any host that runs a shell hook

Setup for each: `oks hook install --editor <claude|qoder|codex|both>` then `oks skills-install`.

## Product boundaries

**The open-source edition is not crippled.** OKS in this repo is fully open source under MIT: no feature gates, no account, no activation key. The CLI core is API-free (CONSTITUTION P4) — `oks` does file operations only; no remote AI API calls from core. AI lives in optional providers/skills you wire yourself.

- **OKS does not train model weights.** The "knowledge model" is the filesystem.
- **OKS does not auto-promote raw → Wiki.** Humans approve.
- **OKS does not replace your Agent.** It provides a Recall primitive; the host Agent decides.
- **Git is the migration.** No database; schema changes versioned through `_meta/`. Atomic writes throughout.

<a id="reproduce"></a>
## Reproduce

The 50-case dataset and all run JSONs are archived:

```
records/experiments/
├── eval-50.yaml                 # 50 semantic-paraphrase queries + expected slugs
└── runs/
    ├── eval-50-fts5.json        # R@1=0.825, MRR=0.907
    ├── eval-50-native.json      # R@1=0.525, MRR=0.630
    ├── eval-50-fusion.json      # R@1=0.805, MRR=0.900
    └── eval-50-embedding.json   # R@1=0.617, MRR=0.733
```

Re-run any backend:

```bash
oks eval recall records/experiments/eval-50.yaml \
  --output my-run.json \
  --search-backend {fts5|native|fusion}

oks eval compare records/experiments/runs/eval-50-fts5.json my-run.json
```

Per-query breakdown: `oks recall "<query>" --explain` shows every factor score.

**Caveat:** OKS has no official labeled dataset — the 50-case set is one KB's history. Metrics are comparable across backends *on that dataset*; they are not a universal SLA. Build your own labeled set and re-run.

## Roadmap

- **AI abstract generation** (Dreaming layer) — LLM writes `abstract:` frontmatter, lifting abstract zero-read quality beyond mechanical first-paragraph.
- **RecallLedger** — cross-turn dedup, so the same page is not re-injected within cooldown.
- **Query expansion** — synonyms / EN↔ZH translation to bridge the synonym gap at retrieval, not via embedding.
- **native→fts5 dispatch unification** — currently two paths (native carries Soul Boost, fts5 does not); unify so fts5 wires the Soul Boost layer too.

## Community & contributing

- **Docs**: [open-agent-power.github.io/open-knowledge-studio](https://open-agent-power.github.io/open-knowledge-studio/)
- **Design contract**: [CONSTITUTION.md](./CONSTITUTION.md) — the memory architecture (A1–A5)
- **Changelog**: [CHANGELOG.md](./CHANGELOG.md) — full release history
- **Contribute**: bug fixes and new features both welcome — fork a branch, open a PR

## Security and privacy

OKS runs entirely on your local filesystem. No telemetry, no remote calls from core (CONSTITUTION P4). Your knowledge base stays under your git remote (or no remote at all).

## License

[MIT](./LICENSE)
