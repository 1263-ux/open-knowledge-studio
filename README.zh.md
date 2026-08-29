<div align="center">

<img src="images/oks-logo-readme.png" width="360" alt="Open Knowledge Studio">

### Open Knowledge Studio：面向编码 Agent 的文件化外部记忆

[English](README.md) / 中文

[![](https://img.shields.io/github/v/release/open-agent-power/open-knowledge-studio?color=369eff\&labelColor=black\&logo=github\&style=flat-square)](https://github.com/open-agent-power/open-knowledge-studio/releases)
[![](https://img.shields.io/github/stars/open-agent-power/open-knowledge-studio?labelColor\&style=flat-square\&color=ffcb47)](https://github.com/open-agent-power/open-knowledge-studio)
[![](https://img.shields.io/github/issues/open-agent-power/open-knowledge-studio?labelColor=black\&style=flat-square\&color=ff80eb)](https://github.com/open-agent-power/open-knowledge-studio/issues)
[![](https://img.shields.io/badge/license-MIT-white?labelColor=black\&style=flat-square)](./LICENSE)
[![](https://img.shields.io/github/last-commit/open-agent-power/open-knowledge-studio?color=c4f042\&labelColor=black\&style=flat-square)](https://github.com/open-agent-power/open-knowledge-studio/commits/main)

[文档站](https://open-agent-power.github.io/open-knowledge-studio/) · [实验数据](#实测效果) · [复现](#复现) · [更新日志](./CHANGELOG.md)

</div>

***

## 什么是 Open Knowledge Studio

Open Knowledge Studio（OKS）是一个开源的**文件化外部记忆**，面向编码 Agent。它不靠黑盒向量库，而是把知识存成一个可人工审计、git 版本化的文件系统——`profiles/`、`raw/`、`wiki/`、`drafts/`、`mail/`——Agent 用 `oks recall`、`oks wiki list`、`oks trace` 来浏览。内容经过一条可审计的流水线（来源 → 证据片段 → Manifest → Raw → Candidate → 人工审核 → Wiki），像真实记忆一样衰减，按需召回。完整介绍：[从这里开始](https://open-agent-power.github.io/open-knowledge-studio/)。

```
你的来源 → Candidate → 人工审核 → Wiki → 召回 → 注入 Agent 上下文
```

## 为什么选 Open Knowledge Studio

- **一套文件系统装下所有记忆。** profiles、raw、wiki、drafts、mail 各占一个目录，有不同的信任边界。Agent 确定性地定位和操作上下文，就像开发者操作文件一样。→ [文件系统范式](https://open-agent-power.github.io/open-knowledge-studio/concepts/file-system-paradigm/) · [记忆模型](https://open-agent-power.github.io/open-knowledge-studio/concepts/memory-model/)
- **人工审核是唯一入口。** 原始材料 ≠ 结论，Candidate ≠ 长期知识。任何东西都不会自动晋升到 Wiki——每条持久记忆都经过人审。→ [Dreaming 周期](https://open-agent-power.github.io/open-knowledge-studio/concepts/memory-model/#dreaming)
- **三层召回压制幻觉。** Node-BM25 召回*什么*匹配，Soul Boost 重排*什么到达* Agent（反模式 ×1.5、review bonus、generic 降权），Memory Curve 评分*多新鲜*——所以置信度永远不会盖过事实。→ [召回引擎](https://open-agent-power.github.io/open-knowledge-studio/algorithms/recall-engine/)
- **知识像真实记忆一样衰减。** 不用的页面沿着 hot → warm → cold → evictable 降温；用过的页面会浮现。`importance × e^(-λ×days) + ln(1+access) + pin_bonus`。→ [衰减系统](https://open-agent-power.github.io/open-knowledge-studio/algorithms/decay-system/)
- **每次召回都可观测。** 每个查询都保留各因子分数和匹配路径（`oks recall "<q>" --explain`）；每次注入都记到 `records/inject.jsonl`。结果看着不对时，你能看到是哪个因子产生的。→ [评估](https://open-agent-power.github.io/open-knowledge-studio/algorithms/recall-evaluation/)

各部分怎么拼一起：[架构](https://open-agent-power.github.io/open-knowledge-studio/architecture/oks-core-architecture/)。设计背后的思考：[CONSTITUTION.md](./CONSTITUTION.md)。

```
open-knowledge-studio/
├── profiles/              # 团队、用户、项目、recipe、goal —— 稳定上下文
├── raw/                    # 人工收集的来源，按日期 {YYYY}/{MM}/{DD}/{source}/
├── wiki/                   # 人审过的记忆：concept、strategy、anti-pattern
├── drafts/                 # Candidate 提议，待审
├── mail/                   # agent 间通信：inbox/ + sent/ —— 不是长期知识
├── settings/               # recall.yaml（唯一参数源）、工具注册表
├── _meta/                  # schema 层：原始证据、召回 case、trace 事件
└── records/                # 版本验收证据 + 实验运行结果
```

三层召回：

- **Node-BM25（召回）**：SQLite FTS5 + BM25，按 markdown `##` 标题分 node，列权重 title 5× > tags 3× > body 1× > code 0.5×。召回过程零文件读（abstract 零读，v0.6.10）。
- **Soul Boost（注入）**：type_boost + review_bonus + generic_demotion 在 hit 到达 Agent 前重排——失败教训排得比通用 concept 高。
- **Memory Curve（衰减）**：类型差异 λ、access_count ln 增长、pin_bonus——不依附任何 backend，在 `store.py` 跑。

## 实测效果

OKS 在一个 50-case 语义改写数据集上做过评估（严格精确 slug 匹配）。完整结果、消融表、复现脚本在 [docs/algorithms/recall-evaluation.md](./docs/algorithms/recall-evaluation.md)；数据集和 run JSON 在 [./records/experiments](./records/experiments)。

### 三层消融 —— 50-case，严格精确 slug 匹配

查询是语义改写——query 不含 slug 的关键词，测试同义词/改写召回。匹配是严格的：期望 slug 必须出现在 top-k。

| backend | R@1 | R@3 | MRR | nDCG@5 | p50 |
|---------|------|------|------|---------|------|
| **fts5（完整三层）** | **0.825** | **0.925** | **0.907** | **0.893** | 93ms |
| native（page-level 6+1，无 Node-BM25） | 0.525 | 0.647 | 0.630 | 0.624 | 137ms |
| fusion（fts5 + native re-rank） | 0.805 | 0.905 | 0.900 | 0.887 | 226ms |

- **Node-BM25 全面碾压 page-level 6+1**：R@1 +57%（0.525→0.825），MRR +44%（0.630→0.907）。多词同段 BM25 高分，语义改写召回精准。
- **Soul Boost 必须在注入层，不在召回层**：native 6+1 的 memory curve / goal boost / review bonus 放到召回层 re-rank *反而降精度*（R@1 0.825→0.805）——不相关 page 高分挤掉精确命中。
- **fts5 还更快**：93ms vs native 137ms vs fusion 226ms。SQLite 持久索引比实时遍历快。

### Embedding backend —— 语义召回对比（v0.6.2）

| backend | R@1 | MRR | p50ms |
|---------|------|------|-------|
| **fts5（Node-BM25 字面）** | **0.825** | **0.907** | 93 |
| embedding（MiniLM cosine） | 0.617 | 0.733 | 18304 |

- 在中文术语重合度高的小库上，BM25 字面已能命中（术语和 wiki 重合）；embedding 的语义泛化反而引入噪声——而且慢 197 倍。
- **决策**：fts5 仍是默认。embedding 作 fts5 miss 时的 **fallback**，不替代。embedding 真正的价值在大库 + 跨语言 + 同义词重的场景。

### 逐层消融

| 消融 | 去掉什么 | R@1 | MRR | 证明 |
|---------|-------------|------|------|--------|
| 完整三层 | — | 0.825 | 0.907 | baseline |
| 去 Node-BM25 | 召回 fts5→native | 0.525 | 0.630 | Node-BM25 是精度主力（−36%） |
| 去 Soul Boost（fusion 误用） | 灵魂搬到召回层 re-rank | 0.805 | 0.900 | 灵魂在注入层才对，召回层 re-rank 是负优化 |

### Abstract 零读 & tier 降级（v0.6.10 / v0.6.12）

- **Abstract 零读**：fts5 schema `node-v2` 加了 `abstract` 列；`body_preview` 从 SQLite 读——**召回过程零文件读**。R@1 持平（0.429），p50 121ms（略快）。
- **Tier 降级**：`_apply_budget()` 在 token budget 命中时按 tier 降级——L2（全文，200c）→ L1（概览，100c）→ L0（abstract，50c）→ title-only（0c，rel < `0.5`）→ 截断。验证：5×200c 在 300c budget 下 → 150c ≤ 300。

> 这些数字是某个时间点一个知识库的历史基准，不是通用 SLA。任何一个都能复现——见[复现](#复现)。

## 快速开始

> 💡 **第一次用 OKS？** 先读[从这里开始](https://open-agent-power.github.io/open-knowledge-studio/)——它讲清记忆生命周期和 OKS 在你 Agent 栈里的位置。

需要 Python 3.10+。

```bash
pipx install open-knowledge-studio && pipx ensurepath
oks init my-knowledge-base
cd my-knowledge-base
oks status          # wiki 数量、tier 分布、drafts、质量
oks recall "git branch"   # 三层召回 → 注入匹配的记忆
```

可选自动召回 hook（把召回接到你的 Agent 宿主）：

```bash
oks hook install --editor claude   # 或：qoder | codex | both
oks skills-install                # 打包 skills + agent-config 到 .claude/.qoder/.pi/.codex
```

接下来：

- CLI 参考、hook 配置、评估：[CLI 文档](https://open-agent-power.github.io/open-knowledge-studio/reference/cli/) · [上下文注入](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/)
- 备份、导出、会话：[备份与导出](https://open-agent-power.github.io/open-knowledge-studio/connect/backup-export/)

## 跟你的 Agent 一起用

OKS 在每次 prompt 注入人审过的记忆（UserPromptSubmit），并在每次工具调用后检测冲突（PostToolUse → `mail/`）：

- [Claude Code](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) —— `.claude/hooks/` + `settings.json`
- [Codex](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) —— `.codex/hooks.json`
- [qoder](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) —— `.qoder/settings.json`（共享 `.claude/hooks/`）
- [pi](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) —— `.pi/extensions/*.ts`（TS extension，共享 `.claude/hooks/`）
- [其他 shell](https://open-agent-power.github.io/open-knowledge-studio/usage/context-injection/) —— 任何能跑 shell hook 的宿主

每个的设置：`oks hook install --editor <claude|qoder|codex|both>` 然后 `oks skills-install`。

## 产品边界

**开源版不阉割。** 这个仓库里的 OKS 在 MIT 下完全开源：没有功能门、不要账号、不要激活码。CLI 核心无 API（CONSTITUTION P4）——`oks` 只做文件操作；核心不调远程 AI API。AI 在你自接的可选 provider/skill 里。

- **OKS 不训练模型权重。** "知识模型"是文件系统。
- **OKS 不自动晋升 raw → Wiki。** 人审。
- **OKS 不替代你的 Agent。** 它提供召回原语；宿主 Agent 决定。
- **Git 就是迁移。** 没有数据库；schema 变更通过 `_meta/` 版本化。全程原子写。

<a id="复现"></a>
## 复现

50-case 数据集和所有 run JSON 都归档了：

```
records/experiments/
├── eval-50.yaml                 # 50 个语义改写 query + 期望 slug
└── runs/
    ├── eval-50-fts5.json        # R@1=0.825, MRR=0.907
    ├── eval-50-native.json      # R@1=0.525, MRR=0.630
    ├── eval-50-fusion.json      # R@1=0.805, MRR=0.900
    └── eval-50-embedding.json   # R@1=0.617, MRR=0.733
```

重跑任意 backend：

```bash
oks eval recall records/experiments/eval-50.yaml \
  --output my-run.json \
  --search-backend {fts5|native|fusion}

oks eval compare records/experiments/runs/eval-50-fts5.json my-run.json
```

逐 query 拆解：`oks recall "<query>" --explain` 显示每个因子分数。

**注意**：OKS 没有官方标注数据集——50-case 是一个知识库的历史。指标在那个数据集上跨 backend 可比；不是通用 SLA。建你自己的标注集再跑。

## 路线图

- **AI abstract 生成**（Dreaming 层）—— LLM 写 `abstract:` frontmatter，把 abstract 零读质量提到机械首段之上。
- **RecallLedger** —— 跨 turn 去重，同一个页面不会在 cooldown 内重复注入。
- **Query expansion** —— 同义词 / 中英互译，在召回层桥接同义词鸿沟，不走 embedding。
- **native→fts5 dispatch 统一** —— 现在两条路径（native 带灵魂层，fts5 不带）；统一让 fts5 也接灵魂层。

## 社区与贡献

- **文档**：[open-agent-power.github.io/open-knowledge-studio](https://open-agent-power.github.io/open-knowledge-studio/)
- **设计契约**：[CONSTITUTION.md](./CONSTITUTION.md) —— 记忆架构（A1–A5）
- **更新日志**：[CHANGELOG.md](./CHANGELOG.md) —— 完整发布历史
- **贡献**：bug 修复和新功能都欢迎——fork 一个分支，开 PR

## 安全与隐私

OKS 完全跑在你本地文件系统上。无遥测，核心不调远程（CONSTITUTION P4）。你的知识库留在你的 git remote（或不要 remote）下。

## License

[MIT](./LICENSE)
