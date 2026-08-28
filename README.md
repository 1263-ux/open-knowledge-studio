<div align="center">

<img src="docs/assets/oks-logo-readme.png" width="420" alt="Open Knowledge Studio">

# Open Knowledge Studio

Host your learning. Train a reviewable knowledge model that helps your Agent stay
grounded across long-running work.

[English](#english) · [中文](#chinese)

[项目首页](https://open-agent-power.github.io/open-knowledge-studio/) · [完成第一条知识闭环](https://open-agent-power.github.io/open-knowledge-studio/first-knowledge-loop.html) · [真实案例](https://open-agent-power.github.io/open-knowledge-studio/oh-my/)

**OKS Office：** [从已审核知识生成 Word、PDF、PPT 和 Excel](https://open-agent-power.github.io/open-knowledge-studio/usage/office.html)

</div>

---

<a id="english"></a>

## English

Open Knowledge Studio (OKS) explores one question: how can an Agent keep learning
through human collaboration and remain stable across long-running work? It does
not train model weights. It builds a filesystem-first external knowledge model:
humans set goals and approve knowledge; Agents collect evidence, execute work,
propose Candidates, and recall reviewed decisions later.

Start with one real source and one reviewed decision; the technical architecture
and protocol references remain available when you need them.

```text
your source → Candidate → human review → Wiki → Recall
```

### Install with an Agent

You do not need to open a terminal or memorize commands. Give your coding Agent
this one request:

> Follow the [OKS setup skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md) to install Open Knowledge Studio for me: create a separate knowledge-base instance, never write my personal knowledge into the source repository, then report the instance location, available capabilities, and every incomplete step in plain language.

The Agent checks the environment, installs or connects OKS, creates the
separate instance, and reports any failure or limitation honestly. For a team,
add the team name and the boundaries its members must confirm.

### Complete one useful loop

Give the Agent one real source and ask it to preserve the source, distinguish
evidence from interpretation, and propose reviewable knowledge rather than
silently saving a conclusion. You review the Candidate; a later task then
confirms whether the reviewed knowledge is useful and still within evidence.

### Product Boundaries

- Core owns filesystem protocols, validation, human review, and Recall; it does
  not call AI APIs.
- `oks-connector` owns acquisition and mechanical extraction.
- Providers create evidence, not Wiki knowledge. Candidate promotion always
  requires human review.
- Evidence and execution states remain traceable, including `partial`,
  `failed`, `skipped`, and `environment_limited`.

### Recall Architecture — OKS Triple-Layer Recall

Recall and injection are decoupled across three layers:

- **Node-BM25** (retrieval) — fts5 node-level BM25 (one FTS5 row per `##`
  heading, multi-word same-section scores high). 50-case ablation: R@1=82.5%,
  MRR=0.907 (vs native 6+1 R@1=52.5%).
- **Soul Boost** (injection) — goal re-rank + `injection_boost` annotation
  (type×1.5/0.8/0.6 + review×1.2 + generic×0.5). Does not change retrieval
  order; visible in `--explain`.
- **Memory Curve** (decay) — type-specific λ → tier `hot/warm/cold/evictable`,
  an independent subsystem in `store.py`.

Ablation proves the layering: adding native 6+1 re-rank back into retrieval
(fusion) *lowers* R@1 0.825→0.805 — the "soul" belongs in the injection layer,
not the retrieval layer.

#### 50-case ablation (semantic-paraphrase queries, strict exact-slug match)

| backend | R@1 | R@3 | R@5 | MRR | nDCG@5 | p50 |
|---------|------|------|------|------|---------|------|
| **fts5 (full Triple-Layer)** | **0.825** | **0.925** | 0.927 | **0.907** | **0.893** | 93ms |
| native (−Node-BM25, 6+1 page-level) | 0.525 | 0.647 | 0.689 | 0.630 | 0.624 | 137ms |
| fusion (fts5 + native re-rank) | 0.805 | 0.905 | 0.927 | 0.900 | 0.887 | 226ms |

Node-BM25 lifts R@1 +57% over native; fusion re-rank *lowers* precision — the
soul factors must live in the injection layer, never in retrieval. Runs archived
in `records/experiments/runs/`. Reproduce:
`oks eval recall records/experiments/eval-50.yaml -o run.json --search-backend fts5`.

See [Recall Evaluation](docs/algorithms/recall-evaluation.md).

### Learn More

- [Project home](https://open-agent-power.github.io/open-knowledge-studio/)
- [Daily workflow](https://open-agent-power.github.io/open-knowledge-studio/usage/)
- [Complete your first knowledge loop](https://open-agent-power.github.io/open-knowledge-studio/first-knowledge-loop.html)
- [托管你的学习](https://open-agent-power.github.io/open-knowledge-studio/oh-my/study.html)
- [Knowledge to Word skill](assets/skills/knowledge-to-word/SKILL.md) — create source-traceable `.docx` files from OKS knowledge
- [OKS Office skill](assets/skills/office/SKILL.md) — recall into one evidence package, then preflight and render source-traceable Word, PDF, or PowerPoint
- [Verify that OKS works](https://open-agent-power.github.io/open-knowledge-studio/verify.html)

*Advanced:*

- [Manual installation, CI, and troubleshooting](docs/reference/cli.md)
- [Architecture principles](docs/concepts/constitution.md)
- [Ingest boundaries](docs/reference/ingest.md)

---

<a id="chinese"></a>

## 中文

**托管你的学习。** Open Knowledge Studio（OKS）研究一个问题：Agent 如何在人机协同中
持续学习，并保证长任务执行的稳定？它不训练模型权重，而是构建一套文件化的外部知识模型：
人类设定目标、边界并审核知识，Agent 收集证据、执行任务、提出 Candidate，并在后续任务中
召回经过确认的判断。

从一份真实材料和一条经审核的判断开始；需要时再阅读技术架构和协议参考。

```text
你的资料 → Candidate → 人工审核 → Wiki → Recall
```

### 交给 Agent 安装

不需要打开终端或记忆命令。把这一句话交给你正在使用的编码 Agent：

> 请按 [OKS 上游安装 Skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md) 为我安装 Open Knowledge Studio：把个人知识放进独立实例，不要写入源码仓库；完成后用自然语言告诉我实例位置、可用能力和所有未完成项。

Agent 会检查环境、安装或连接 OKS、创建独立实例，并如实报告失败和限制。团队使用时，再补充团队名称和成员必须确认的边界。

### 跑通一条有用的闭环

把一份真实材料交给 Agent，并要求它保留来源、区分证据与解释、只提出待审核知识而不自行保存结论。你审核 Candidate；后续任务再验证这些经过审核的知识是否真正有用、是否仍在证据范围内。

### 召回架构 — OKS Triple-Layer Recall

召回与注入解耦，三层架构：

- **Node-BM25**（召回层）—— fts5 node-level BM25（每个 `##` heading 段一个 FTS5
  row，多词同段高分）。50-case 消融：R@1=82.5%，MRR=0.907（vs native 6+1 R@1=52.5%）。
- **Soul Boost**（注入层）—— goal 重排 + `injection_boost` 标注
  （type×1.5/0.8/0.6 + review×1.2 + generic×0.5）。不改召回顺序，`--explain` 可见。
- **Memory Curve**（衰减层）—— type-specific λ → tier `hot/warm/cold/evictable`，
  `store.py` 独立子系统。

#### 50-case 消融实验（语义改写 query，严格精确 slug 匹配）

| backend | R@1 | R@3 | R@5 | MRR | nDCG@5 | p50 |
|---------|------|------|------|------|---------|------|
| **fts5（完整 Triple-Layer）** | **0.825** | **0.925** | 0.927 | **0.907** | **0.893** | 93ms |
| native（去 Node-BM25，6+1 page-level） | 0.525 | 0.647 | 0.689 | 0.630 | 0.624 | 137ms |
| fusion（fts5 + native re-rank） | 0.805 | 0.905 | 0.927 | 0.900 | 0.887 | 226ms |

Node-BM25 R@1 较 native +57%；fusion re-rank 反而*降*精度——灵魂因子必须留在注入层，
不能放召回层。run json 归档 `records/experiments/runs/`。复现：
`oks eval recall records/experiments/eval-50.yaml -o run.json --search-backend fts5`。

详见 [召回评估](docs/algorithms/recall-evaluation.md)。

### 产品边界

- Core 负责文件协议、校验、人工审核和 Recall，不调用 AI API。
- `oks-connector` 负责资料获取与机械提取。
- Provider 产生证据，不直接产生 Wiki 知识；Candidate 晋升必须经过人工审核。
- 证据与执行状态必须可追溯，包括 `partial`、`failed`、`skipped` 和
  `environment_limited`。

### 继续阅读

- [项目首页](https://open-agent-power.github.io/open-knowledge-studio/)
- [日常使用](https://open-agent-power.github.io/open-knowledge-studio/usage/)
- [完成第一个知识闭环](https://open-agent-power.github.io/open-knowledge-studio/first-knowledge-loop.html)
- [托管你的学习](https://open-agent-power.github.io/open-knowledge-studio/oh-my/study.html)
- [Knowledge to Word skill](assets/skills/knowledge-to-word/SKILL.md) — 从 OKS 知识生成带来源说明的 `.docx`
- [OKS Office skill](assets/skills/office/SKILL.md) — 将一次召回的知识整理成证据包，经 preflight 后按同一事实生成 Word、PDF 或 PowerPoint
- [确认 OKS 正在工作](https://open-agent-power.github.io/open-knowledge-studio/verify.html)

*进阶内容：*

- [手动安装、CI 与排错](docs/reference/cli.md)
- [架构原则](docs/concepts/constitution.md)
- [摄入边界](docs/reference/ingest.md)

## License

MIT
