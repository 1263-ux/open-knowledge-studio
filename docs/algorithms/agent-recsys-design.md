# Agent Recall System — 复杂版设计（基于 Triple-Layer Recall）

> 本文档基于 **CONSTITUTION A8: Triple-Layer Recall**（召回层 / 注入层 / 衰减层三层解耦）。
> 复杂版**不增加层数**——三层不变，是三层的"规模放大"：
> - 召回层从单路 Node-BM25 扩展到多路（CF / I2I / 双塔 / 序列作并列 backend）
> - 注入层从单 Agent Soul Boost 扩展到多 Agent 协同 Boost
> - 衰减层 Memory Curve 不变
>
> 与 `agent-recall-architecture.md`（蓝图 Phase 路线图）互补：本文是**召回算法复杂化**的完整设计。

---

## 0. 纠正：之前文档的两个错误

> 上一版 `agent-recsys-design.md` 有两处基于错误前提，现纠正：

1. **"6+1 因子 = DeepFM 退化版"是错的**。6+1 是 `native` backend（v0.6.0 前默认，向后兼容），**当前默认是 `fts5`（Node-BM25）**。召回层主力是 Node-BM25，不是 6+1。复杂版的多路召回是**召回层的新 backend**（和 fts5 并列，经 `entry_points(group="oks_search_backend")` 注册），不是替代 6+1。
2. **"四层存储"是错的**（已删 `remote-team-mode.md`）。OKS 是**三层**（A8），规模光谱是三层在 mini→cluster 的部署变形，不增层。见 `scale-spectrum.md`。

错误根因：违反 P6 精神——凭过时记忆（CONSTITUTION A2 旧文 + recall.py 旧注释都写"6+1/native default"，v0.6.0 后没更新）写文档，没先 `oks recall --explain` 核实当前 score_components。A8 + A2 修正已消除这个 P6 漂移。

---

## 1. 三层不变，是三层的放大

| 层 | 当前（mini） | 复杂版（cluster） | 不变的是什么 |
|----|-------------|------------------|-------------|
| **召回层** | Node-BM25（fts5 单路） | Node-BM25 + 多路 backend（CF/I2I/双塔/序列）经 entry_points 并列 | 召回找精度，不在召回层 re-rank（A8 不变量） |
| **注入层** | Soul Boost（单 Agent：type/review/generic/goal/memory） | Soul Boost + 多 Agent 协同 boost（CF 共现注入） | 注入做排序，label confidence（A8 不变量） |
| **衰减层** | Memory Curve（本地 cron） | Memory Curve（分布式 decay，但算法不变） | score = importance×e^(-λ×days) + 0.5×ln(1+access) + pin（A8 不变量） |

**核心不变量**（A8）：召回层和注入层解耦——灵魂因子（memory/goal/type/review）在召回层 re-rank 是**测得的负优化**（fusion R@1=0.805 < fts5 R@1=0.825）。复杂版的多路召回**仍是召回**（找候选），多 Agent 协同 boost **仍是注入**（排序），不混。

---

## 2. 召回层放大：从单路 Node-BM25 到多路召回

> 对应 fun-rec `chapter_1_retrieval`（CF/I2I/双塔/序列/流式索引）。
> **关键映射**：fun-rec 的每路召回都是 OKS 召回层的一个**并列 backend**，经 `entry_points(group="oks_search_backend")` 注册，和 fts5 平级，不替代。

### 2.1 当前的召回层（fts5 = Node-BM25）

```
query → FTS5Backend.search() → node-level BM25 top-N hits
  每 ## heading 段一 FTS5 row，多词同段 BM25 高分
  column weights: title 5x > tags 3x > body 1x > code 0.5x
  增量 diff（content_hash），持久化 .oks/fts5.db
```

R@1=0.825（50-case），是召回层默认。**召回层只做这个**——找候选，不做排序（排序是注入层）。

### 2.2 多路召回 = 召回层的并列 backend

fun-rec 的 5 路召回，每路映射成 OKS 召回层的一个 backend：

| fun-rec 召回路 | OKS 召回层 backend | 数据源 | 算法 |
|--------------|-------------------|--------|------|
| **CF**（ItemCF/UserCF/Swing） | `collab` backend（★新增，团队版核心） | `records/inject.jsonl` 跨 Agent 共现 | 统计共现 / Swing（小数据稳健） |
| **I2I**（word2vec/item2vec/EGES） | `i2v` backend（设想，Phase 远期） | inject slug 序列当句子 | Word2Vec 学 doc 向量 |
| **双塔**（FM/DSSM/YoutubeDNN） | `embedding` backend（已有 connector 扩展点） | Agent 行为 + doc 内容 | BGE 预训练（P4 不训 DSSM） |
| **序列**（MIND/SDM） | `seq` backend（设想，Phase 远期） | inject 时序 | 多兴趣聚类 + 长短期 |
| **流式索引**（Trinity/StreamingVQ） | fts5 增量（已有） | wiki 文件变更 | FTS5 增量插入 |

**Snake Merge 蛇形合并**：多路 backend 各 Top-N，蛇形交错合并去重（round-robin），避免单路刷屏。这是召回层内部的融合，不跨层。

### 2.3 多路召回的 P4 边界

- **fts5**（Node-BM25）：core 自带，P4 合规（无模型）
- **collab**（CF）：core 可带（统计共现，无模型）——团队版核心增量
- **embedding**：connector 扩展（oks-connector[embedding]，BGE 预训练，不调远程 API，P4 合规但慢默认关）
- **i2v/seq**：设想，需 Word2Vec/序列模型——P4 约束下要在 host 侧 or connector，不进 core

### 2.4 不在召回层做的事

**不在召回层 re-rank 灵魂因子**（A8 不变量，fusion 实测负优化）。召回层返回候选后，**注入层**做 Soul Boost 排序。多路召回的融合（Snake Merge）是召回层内部，不引入注入层逻辑。

---

## 3. 注入层放大：从单 Agent 到多 Agent 协同 Boost

> 对应 fun-rec 排序层（特征交叉/多目标/多场景）+ 重排层（贪心/个性化）。
> **关键映射**：fun-rec 的排序+重排 = OKS **注入层 Soul Boost 的增强**，不是新层。

### 3.1 当前的注入层（Soul Boost）

```
fts5 hits → _injection_boost(page, hit) → 标注 injection_boost
  type×1.5/0.8/0.6 + review×1.2 + generic×0.5
  + goal reorder（goal 命中 slug 往前排）
  + memory curve score（从衰减层注入）
→ 按 boost 后顺序注入会话
```

### 3.2 多 Agent 协同 Boost（注入层增强）

fun-rec 多目标排序的 Agent 版——**注入层加协同信号**：

| fun-rec 排序 | OKS 注入层 Boost | 实现 |
|-------------|-----------------|------|
| 特征交叉（DeepFM） | Soul Boost 现有因子（type/review/generic/goal/memory）= 启发式交叉 | 已有，不训模型（P4） |
| 多目标（CTR/CVR/时长） | 多目标 Boost：相关性 + use 转化率 + 新鲜度 | `injection_boost` 加 use_prob 项（设想） |
| 多场景（首页/详情/搜索） | scope Boost：不同 area 权重不同 | 已有 scope 参数 |

**重排（MMR）= 注入层增强**：
```
贪心 MMR: 选 argmax [boost(d) - λ·max sim(d, selected)]
  sim = area 重合 + type 重合
  λ 从 recall.yaml 配
```
MMR 在注入层做（召回层只找候选，注入层排序+打散），不违反 A8。

### 3.3 多 Agent 协同 Boost 的数据

团队版核心增量——从 `records/inject.jsonl` 跨 Agent 聚合：
- **ItemCF Boost**：当前 Agent 召回过 doc X，"召回过 X 的其他 Agent 也召回过 Y" → Y 的 boost +
- **UserCF Boost**：和当前 Agent 行为相似的 Agent 召回过但当前没召回的 doc → boost +
- **per-agent 读态**：`mail/.read/{agent_id}.jsonl`（D1 修复已有），inject 也按 agent_id 隔离

**这是注入层的事**——协同信号 boost 注入排序，不是召回层找候选。区分：
- 召回层 `collab` backend：用 CF 共现**找候选**（doc 没在 fts5 候选里但 CF 说相关）
- 注入层协同 Boost：候选已在，用 CF 信号**排序**（doc 在候选里，CF 说更该用）

两者都用 CF 共现矩阵，但作用层不同——召回层扩候选池，注入层精排序。

---

## 4. 衰减层不变：Memory Curve

> fun-rec 没有"衰减"对应（电影评分不过期）。这是 OKS 独有——知识会过时。

Memory Curve（store.py `apply_decay`）复杂版**不变**：
- 公式不变：`score = importance×e^(-λ×days) + 0.5×ln(1+access) + pin`
- tier 不变：hot(≥0.7)/warm(≥0.4)/cold(≥0.15)/evictable
- 复杂版唯一增量：分布式 decay（多机各自跑本地 wiki 的 decay，或 Hub 统一跑）——算法不变，部署变（见 scale-spectrum.md）

---

## 5. P4 诚实边界（复杂版不破）

**不做的**：
- ❌ 召回层 re-rank 灵魂因子（A8 不变量，fusion 实测负优化）
- ❌ core 训模型（DeepFM/DSSM/Word2Vec）——P4，用判别式退化 + connector 扩展
- ❌ 增加第四层——A8 三层不变，复杂版是三层放大

**替代**：
- ✅ 多路召回 = 召回层并列 backend（entry_points 扩展，fts5 是默认）
- ✅ 多 Agent 协同 = 注入层 Boost 增强（collab 信号 boost 排序）
- ✅ MMR 重排 = 注入层打散（不新层）
- ✅ 复杂模型（DeepFM/Word2Vec）= connector 扩展（host 侧，不进 core）

---

## 6. 路线图（合并 architecture Phase）

| Phase | 层 | 内容 | 形态 |
|-------|-----|------|------|
| 1 ✅ | 设计 | A8 三层入宪 + 本文档 + architecture | 共用 |
| **2** | 召回 | dispatch 注释/doc 修正（已做 P6）+ fts5 稳固 | 共用 |
| 3 | 召回 | `collab` backend（CF 召回，团队版核心） | 团队 |
| 4 | 注入 | 协同 Boost（CF 信号 boost 排序，注入层） | 团队 |
| 5 | 注入 | MMR 重排（注入层打散） | 共用 |
| 6 | 召回 | Snake Merge 多路融合 | 共用 |
| 7 | 召回 | `embedding` fallback 完善（已有 connector） | 共用 |
| 8 | 召回 | `i2v`/`seq` backend（设想，远期，P4 外） | 远期 |
| 9 | 注入 | 多目标 Boost（use 转化率 + 新鲜度） | 共用 |
| 10 | 衰减 | 分布式 decay（scale-spectrum.md） | cluster |

**执行顺序**：P2（P6 修正，已做）→ P3-4（团队协同，collab backend + 协同 Boost，复杂版核心）→ P5-6（重排+融合）→ P7-9（完善）→ P10（分布式）。

---

## 7. 参考

- 宪法：`CONSTITUTION.md` A8（Triple-Layer Recall 三层解耦不变量）
- 蓝图：`docs/algorithms/agent-recall-architecture.md`（Phase 路线图）
- 规模光谱：`docs/architecture/scale-spectrum.md`（三层在 mini→cluster 的部署变形）
- 召回引擎现状：`docs/algorithms/recall-engine.md`（三层架构 + 双路召回 + 可插拔 backend）
- 评测：`docs/algorithms/recall-evaluation.md`（50-case 消融，fusion 负优化证据）
- 蓝本：`raw/2026/08/31/fun-rec/docs/_sources/`（chapter_1_retrieval 召回5路 / chapter_2_ranking 排序 / chapter_3_rerank 重排）
- 实现位置：`recall.py::dispatch`（召回层）/ `recall.py::_injection_boost`（注入层）/ `store.py::apply_decay`+`compute_tier`（衰减层）
