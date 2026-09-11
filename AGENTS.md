# Open Knowledge Studio

> A knowledge engineering workspace for Claude Code — raw → wiki → recall.

## What is this?

Open Knowledge Studio is a file-based knowledge base system designed for use with Claude Code. It provides:

- **5 cognitive buckets + 2 infrastructure layers**: profiles/, raw/, wiki/, drafts/, mail/ (cognitive), settings/ (config), _meta/ (schema)
- **Agent-Native ingestion pipeline**: Source → Provider → EvidenceFragment → EvidenceManifest → `oks raw-commit` → Raw Bundle v0.2 → Candidate → Human Review → Wiki
- **Triple-Layer recall (Constitution A8)**: Node-BM25 retrieval (SQLite FTS5 over `##` heading nodes, default `fts5` backend) + Soul Boost injection re-rank (type boost, review bonus, generic demotion) + Memory Curve decay; legacy native 6+1 backend kept for compatibility
- **Provider and capability catalogs**: inspect current Provider availability with `oks capability status`; do not copy changing counts into prose
- **Dreaming cycle**: raw → AI distill → drafts → human review → wiki
- **Decay system**: memory curve scoring with type-specific λ, tier classification (hot/warm/cold/evictable)
- **CLI tool (`oks`)**: run `oks --help` for the authoritative command tree; optional coordination commands include `mail` and `registry`

## Raw Material vs Memory — The Core Distinction

| | Raw Material (raw/) | Memory (wiki/) |
|---|---|---|
| **What** | Original article, paper, repo note, or conversation | Durable takeaway, distilled and curated |
| **Who writes** | Human collects, LLM reads only | LLM writes via Dreaming, human approves |
| **Decay** | None | Type-specific λ |
| **Recall** | Keyword + freshness | Triple-Layer: Node-BM25 relevance + Soul Boost re-rank + memory curve |
| **Advantage** | Date-based ({YYYY}/{MM}/{DD}/{source}/), A/B/C grading, fingerprint dedup | 22-domain structure, decay tiers, 4 relationships |

A strong workflow: save the source into `raw/`, then distill the parts worth keeping into `wiki/` memories.

## Quick Start

```bash
pipx install open-knowledge-studio && pipx ensurepath   # PyPI
# Developers: pipx install ./cli --force
oks init my-knowledge-base
cd my-knowledge-base
oks status
oks recall "git branch"
```

## Core Pipeline

```
raw/ (human-collected or tool-processed materials)
  ↓ /ingest skill — Agent-native evidence ingestion
  ↓ Source → Providers → EvidenceFragment → EvidenceManifest
  ↓ oks raw-commit → Raw Bundle v0.2
drafts/ (intermediate proposals)
  ↓ /promote skill — human review
wiki/ (curated knowledge, with decay)
  ↓ oks recall / /query skill — Triple-Layer recall
injected into Claude Code context
```

## Memory Architecture

See `CONSTITUTION.md` for the full memory design (A1-A5):

- **A1**: Cognitive buckets + two infrastructure layers + memory lifecycle (Observe→Write→Store→Retrieve→Inject→Forget)
- **A2**: Six-type memory model + injection order + source labels + conflict priority
- **A3**: Dreaming — human-reviewed knowledge evolution
- **A4**: Knowledge evolution — supersedes, enriches, confirms, challenges
- **A5**: Atomic file writes

## Directory Structure

There are **two trees with different laws**. Do not describe one with the
other's map.

### Map 1 — This repository (the factory)

This repo develops and packages OKS. It is **not** an instance: long-term
personal knowledge must live in an instance created by `oks init` (A1/P3
apply there, not here).

```
open-knowledge-studio/            # 源码仓库 = 工厂
├── cli/                          # Python 包：oks CLI 与 knowledge_studio 包
│   └── knowledge_studio/
│       ├── (代码模块)            # recall.py / store.py / cli.py …
│       ├── providers/            # 包内数据：Provider 定义 (provider.yaml + SKILL.md)，importlib 读取
│       ├── capabilities/         # 包内数据：capability 动作目录 (actions.yaml)
│       ├── recipes/              # 包内数据：模态 recipe (text/pdf/office/…)
│       ├── schemas/              # schemas/ 的运行时校验镜像 —— 由 scripts/sync_schemas.py 同步，禁止手改
│       └── search/               # 召回后端 (fts5 / native / fusion)
├── assets/                       # init 物化层：实例得到的一切的唯一来源（setup.py 契约）
│   ├── agent-config/ hooks/ profiles/ rules/ settings/ skills/ templates/
│   └── _meta/                    # 实例 _meta/ 的模板（含 schemas/ 镜像，同步于根 schemas/）
├── schemas/                      # 协议 schema 唯一事实源（P8：镜像漂移由 CI --check 抓住）
├── docs/                         # GitHub Pages 站点 —— 每个 .md 都是已发布页面
├── scripts/                      # 维护脚本（check_links / sync_schemas / locomo_to_oks）
├── records/                      # 版本化验收与可复现实验记录（大体积第三方数据不进 git）
├── reference-implementations/    # 可选集成参考实现（oh-my-feishu），不随包分发
├── images/                       # README 与品牌图（站点用图在 docs/assets/）
├── settings/                     # 本仓库自己的开发实例配置 —— 不随包分发，勿与 assets/settings/ 混淆
├── templates/                    # 实例模板样例（examples/）
├── .claude/ .codex/ .agents/ .pi/  # 各宿主的开发期配置；maintainer-only skills 只在 .claude 与 .agents
└── CONSTITUTION.md  AGENTS.md  CLAUDE.md  README.md  README.zh.md  SKILL.md  CHANGELOG.md
```

**打包边界（一条规则）**：会随 wheel 发给用户的数据只有两条通道 ——
`assets/`（init 物化到实例）或包内数据目录（Python importlib 读取）。
同一份数据只允许一条通道；新增数据时先选通道，再选目录。

### Map 2 — An instance (the memory)

`oks init <path>` 产出的实例仓库，结构由宪法 A1 定义。`docs/concepts/` 的
概念页描述它的运行，写作契约在 `docs/maintainers/`。

```
<instance>/
├── profiles/         # ① Portraits — team, users, projects, recipes, goals
├── raw/              # ② Raw materials — date-based: {YYYY}/{MM}/{DD}/{source}/
├── wiki/             # ③ Curated, human-reviewed knowledge
├── drafts/           # ④ Dreaming candidates
├── mail/             # Agent communication — inbox/ + sent/
├── settings/         # Config layer — recall.yaml, tool registry, input sources
├── _meta/            # Schema layer — raw evidence, recall case, trace event
├── capabilities/  recipes/  providers/  security/   # 由包内数据物化
└── .claude/ .codex/ .qoder/ .pi/                    # hook 与 skills 安装目标
```

## Claude Code Skills

| Skill | Purpose |
|-------|---------|
| `/assess` | Q&A builds profile + active goals, verify recall boost (initial setup + tuning) |
| `/ingest` | Agent-native evidence ingestion (Source → Provider → Fragment → Manifest → raw-commit) |
| `/query` | Triple-Layer recall → inject into context → AI answers with citations |
| `/lint` | Scan wiki/: frontmatter, orphans, broken links, stale |
| `/compile` | Re-compile concept pages from sources → drafts/ |
| `/status` | Overview: wiki count, tier distribution, drafts, quality |
| `/archive` | Capture conversation transcript → raw/conversations/, distill Q&A → drafts/ (never writes wiki directly) |
| `/promote` | Review drafts/ → promote/reject/edit |
| `/accept` ⚙ | Evidence-first isolated capability acceptance (maintainer-only, not in wheel) |
| `/media-ingest` | Experimental video intake adapter (currently unavailable — scripts not yet packaged) |

Agents skills mirror Claude skills with identical content. Maintainer-only
skills such as `/accept` live only in this repo's `.claude/skills` and
`.agents/skills` (never in `assets/skills`), so they are not shipped in the Wheel.

## CLI Commands

```bash
# Instance scaffold
oks init <path> [--set-default|--no-set-default] [--git|--no-git] [--upgrade] [--force]
oks skills-install [--force]

# Raw ingestion
oks raw-commit <manifest-dir> [--output/-o <dir>] [--overwrite] [--json/--text]
oks ingest prepare <source>
oks ingest run <source>   # compatibility entry point; no Wiki promotion

# Recall (the single retrieval entry — Agent-facing, injected via hook)
oks recall <query> [--topic-id ID] [--limit 5] [--scope AREA] [--type strategy] [--knowledge-only] [--goal active|none|SLUG] [--format table|json] [--explain]

# Wiki
oks wiki list [--domain] [--type] [--status active]
oks wiki get <slug>
oks wiki create --title "..." --type concept --area computing --importance 0.7
oks wiki pin <slug> | archive <slug>
oks wiki use <slug>   # explicit "this page was used" signal

# Drafts
oks drafts list | get <slug> | promote <slug> | reject <slug>
oks distill [--dry-run]

# Read-only VFS
oks fs ls|tree|stat|read|overview|find <uri-or-query>

# Maintenance
oks lint | status | metrics [--html] | decay

# Capability
oks capability list
oks capability install <name> [--yes]
oks capability status [--json/--text]
oks capability guide <provider-id>

# Optional coordination
oks mail send|inbox|read|count
oks registry list|bind|remove
oks team init <path> [--name NAME]

# Protocol and security
oks schema show <document-kind>
oks security sanitize <file>

# Feishu (参考实现，已从核心迁出 → reference-implementations/oh-my-feishu/)
# 不再随 oks CLI 分发；见 reference-implementations/oh-my-feishu/code/ 的 feishu_base_worker.py / feishu_setup.py

# Hooks (opt-in auto-recall + post-tool conflict detection)
oks hook install [--editor claude|qoder|codex|both] [--path DIR]
oks hook status

# Evaluation
oks eval recall <dataset.yaml> --output <run.json>
oks eval compare <baseline.json> <candidate.json> [--output <comparison.json>]

# Execution traces
oks trace start <goal-id> [--run-id ID]
oks trace append <run-id> --type <event> --actor <actor> --payload '<json>'
oks trace judge <run-id> --outcome pass --comment "..."
oks trace feedback <run-id> --outcome accepted --comment "..."
oks trace blocker <run-id> --reason "..." --needed "..."
oks trace propose <run-id> --kind wiki|skill --title "..." --summary "..."
oks trace finish <run-id> --result '{"outcome":"success"}'
oks trace validate <run-id> [--completed]
oks trace show <run-id>

# Config
oks config init | show | set <key> <value>
```

## Conventions

- **raw/** is human-collected or tool-processed. Tools preserve maximum fidelity — they convert format, not knowledge. LLM does not write knowledge to raw/.
- **wiki/** is LLM-written, human-approved via drafts/ review.
- **Intake is Agent-orchestrated** — `/ingest` is the recommended path. `oks ingest run` is a compatibility entry point that delegates mechanical acquisition and extraction to the separately packaged `oks-connector`.
- **Global config** (`~/.oks/config.json`) enables cross-project access — `oks recall` works from any directory (resolution: `OKS_ROOT` env → config `knowledge_base_path` → cwd).
- **Code repo vs instance repo** — THIS repo is the reusable tool/template: it ships clean (wiki/ & drafts/ gitignored) so others can use it. Your personal knowledge lives in a separate instance created by `oks init <path>`, which TRACKS memory in git. Practices proven in an instance flow back here as PRs.
- **Git IS the migration** — no database, schema changes versioned through _meta/.
- **Atomic writes** — all persistent writes use mkstemp + fsync + os.replace.
- **Never auto-promote** raw content to wiki/ without human review.

## Project-specific safety rules

- Personal knowledge lives in a separate instance created by `oks init <path>`; this repository is reusable Studio code and must not remain the long-term destination for personal Wiki or Raw state.
- Every `git push`, Pull Request create/update/close, Merge, Pages/Release publication, deployment, remote setting change, or external message requires the user's explicit authorization for that exact action. A general "continue" or authorization for a different action does not count.
- Without that authorization, stop after local editing, validation, diff review, and read-only remote inspection. A Draft PR is still an external action.
- Context compaction is controlled by the client or runtime; this file cannot set an automatic threshold or reveal an unexposed usage percentage. If the client explicitly reports 80% usage, or at major milestones and around unusually large tool output, preserve a structured checkpoint before invoking an actually available compaction mechanism.
- Preserve `partial`, `failed`, and `skipped` states exactly. Mechanical extraction, AI interpretation, human review, and Wiki promotion are separate layers and must remain traceable.
