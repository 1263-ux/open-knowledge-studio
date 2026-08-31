# 规模光谱 — 三层在 mini → cluster 的部署变形

> OKS 是**三层架构**（CONSTITUTION A8: Triple-Layer Recall = 召回层 / 注入层 / 衰减层）。
> 这三层在**不同规模**下有不同部署形态，但**层数永远是三**——不因规模增加层。
> 从个人电脑 mini 到复杂集群，是**同一架构的连续缩放**，不是两个产品。
>
> 本文档取代已删的 `remote-team-mode.md`（那版自创"四层存储"跑偏了，违反 A8）。

---

## 0. 为什么不是"team 模式"

之前误写成"team 模式"是跑偏。OKS 没有"个人版/团队版"两个产品——是**一个架构的规模光谱**：
- 个人电脑可以很 **mini**（单机，少 Agent，纯本地）
- 也可以非常**复杂的集群版**（多机，大群体 Agent，分布式）
- 或很复杂的**Agent 知识推荐系统**（多路召回 + 协同 Boost）

三个不是三个产品，是**同一三层架构在不同规模的部署**。规模是连续光谱，不是断层。

---

## 1. 三层不变，是部署变形

| 规模 | 召回层 Node-BM25 | 注入层 Soul Boost | 衰减层 Memory Curve |
|------|-------------------|-------------------|---------------------|
| **mini**（个人电脑） | 本地 FTS5 db（`.oks/fts5.db`） | 本地 Boost（单 Agent） | 本地 cron decay |
| **standard**（小团队，<10 Agent） | 本地 FTS5 + git 同步 wiki | 多 Agent Boost（per-agent，`mail/.read/`） | 本地 decay + git 同步 |
| **cluster**（大群体，10-1000 Agent） | 分布式索引（FTS5 分片 or 对象存储 + 本地缓存） | 协同 Boost（CF 共现注入） | 分布式 decay（Hub 统一 or 各机自治） |
| **复杂推荐系统**（cluster + 多路召回） | 召回层扩多路（fts5 + collab + embedding backend） | 协同 Boost + MMR 重排 | decay + 协同信号 |

**核心不变量（A8）**：三层永远是三层。复杂版是召回层"宽"了（多路 backend），注入层"厚"了（多 Agent 协同），衰减层"散"了（分布式）——**层数不增**。

---

## 2. 规模光谱四档

### 2.1 mini（个人电脑）— 当前默认

```
单机文件系统 (P1, 文件即 DB)
  ├─ 召回层: 本地 .oks/fts5.db (Node-BM25)
  ├─ 注入层: _injection_boost (单 Agent Soul Boost)
  └─ 衰减层: store.apply_decay (本地 cron)
```

**适用**：个人知识库，1 个 Agent，纯本地。当前 OKS 默认形态。无远程依赖，P4 完全合规。

### 2.2 standard（小团队，<10 Agent）— git 同步

```
多机共享 KB (git 是 migration, P1 不破)
  ├─ 召回层: 各机本地 FTS5 (git 同步 wiki → 各自重建索引)
  ├─ 注入层: per-agent Boost (OKS_AGENT_ID 隔离, mail/.read/{id}.jsonl)
  └─ 衰减层: 各机本地 decay (git 同步 wiki frontmatter 的 tier)
```

**适用**：异步协作小团队。Agent 分布多机但共享 git 仓库。mail 跨 Agent 通信（D1 per-agent 读态 + D2 to: 过滤已修）。并发靠 git merge + 文件锁。

### 2.3 cluster（大群体，10-1000 Agent）— 分布式

```
分布式存储 + 本地缓存
  ├─ 召回层: 分布式索引 (FTS5 分片 by area / 对象存储 + 本地 LRU 缓存)
  ├─ 注入层: 协同 Boost (CF 共现矩阵从 inject.jsonl 聚合, 跨 Agent)
  └─ 衰减层: 分布式 decay (Hub 统一跑 or 各机自治 + 同步 tier)
```

**适用**：大群体生产。core 文件存对象存储（S3/MinIO）+ 本地缓存热数据。派生状态（FTS5/共现矩阵）可远程化（PG/Redis）或本地重建。并发用分布式锁。

**P4 边界**：core 命令（`oks recall`）永远本地——先查本地缓存命中，miss 再拉远程。remote sync 是**扩展命令**（opt-in），core 不依赖远程才能跑。

### 2.4 复杂推荐系统（cluster + 多路召回）

```
cluster 三层 + 召回层扩多路
  ├─ 召回层: fts5 + collab (CF) + embedding + (i2v/seq 远期) 经 entry_points 并列
  ├─ 注入层: Soul Boost + 协同 Boost + MMR 重排
  └─ 衰减层: 分布式 decay + 协同信号
```

**适用**：生产级 Agent 知识推荐系统。召回层从单路扩到多路（fun-rec 5 路 1:1 映射，见 `agent-recsys-design.md`），注入层加协同 Boost + MMR 打散。**仍是三层**——多路召回是召回层内部并列 backend，协同 Boost 是注入层增强。

---

## 3. 演进路径（每步可停）

| 阶段 | 存储 | 并发 | 召回层 | 注入层 | 适用 |
|------|------|------|--------|--------|------|
| **S0 mini** | 本地文件 | 文件锁 | 本地 FTS5 | 单 Agent Boost | 个人/同址小团队（当前） |
| **S1 git** | git push/pull | git merge | 各机 FTS5 | per-agent Boost | 异步协作团队 |
| **S2 cluster** | 对象存储+缓存 | 分布式锁 | 分布式索引 | 协同 Boost | 大群体生产 |
| **S3 复杂推荐** | S2 + 派生远程化 | S2 | 多路召回 | 协同+MMR | 生产推荐系统 |

**演进原则**：
- S0→S1 已有基础（git 是 OKS 的 migration，P1）
- S1→S2 是存储层升级（对象存储 + 分布式锁），三层架构不变
- S2→S3 是召回层扩多路（collab backend + 协同 Boost），三层架构不变
- **每步可停**——小团队永远 S0/S1，大群体才上 S2/S3

---

## 4. 三层在各规模的关键技术

### 4.1 召回层

| 规模 | FTS5 索引 | 多路 | 延迟 |
|------|----------|------|------|
| mini | 本地 `.oks/fts5.db` | 单路（fts5） | <20ms |
| standard | 各机本地 + git 同步 wiki | 单路 | <20ms |
| cluster | 分片/对象存储+缓存 | + collab（CF） | 本地命中<20ms，miss 拉取+重建 |
| 复杂推荐 | 分布式索引 | + embedding + i2v/seq | 多路并行 + Snake Merge |

### 4.2 注入层

| 规模 | Boost 信号 | per-agent | 重排 |
|------|-----------|-----------|------|
| mini | type/review/generic/goal/memory（Soul Boost） | 单 Agent | 无 |
| standard | + per-agent 读态（D1） | `mail/.read/{id}.jsonl` | 无 |
| cluster | + CF 协同 Boost（ItemCF/UserCF 共现） | per-agent inject | MMR 打散 |
| 复杂推荐 | + 多目标（use 转化率+新鲜度） | + Agent 画像 | 个性化 MMR |

### 4.3 衰减层

| 规模 | decay 执行 | tier 同步 | 算法 |
|------|-----------|----------|------|
| mini | 本地 cron | 本地 frontmatter | 不变 |
| standard | 各机 cron | git 同步 frontmatter tier | 不变 |
| cluster | Hub 统一 or 各机自治 | 对象存储同步 | 不变 |
| 复杂推荐 | 分布式 + 协同信号 | + 共现矩阵影响 access | 公式不变 |

**衰减层最稳**——公式和 tier 阈值在所有规模都不变（A8 不变量），只有执行位置变。

---

## 5. P4 / P1 / A8 边界

**P1（文件即 DB）**：core 的 wiki/raw/profiles/mail 永远是文件 + frontmatter。对象存储是"文件存哪"，不是"文件变 DB 行"。mini/standard 完全 P1；cluster 的 core 文件存对象存储，本地是缓存（P1 部分退化但语义不变）。

**P4（API-free）**：core 命令（`oks recall/fs/init`）永远本地操作，不调远程 API。remote sync 是 opt-in 扩展命令。Hub 服务（若用）是独立部署，core 不依赖。mini/standard 完全 P4；cluster 的 remote sync 是扩展层，core 仍本地优先。

**A8（三层不变量）**：所有规模都是三层。复杂版是召回层宽（多路）、注入层厚（协同）、衰减层散（分布式）——**层数永远三**。不在召回层 re-rank 灵魂（fusion 实测负优化，所有规模适用）。

---

## 6. 不做的事

- ❌ **不增加第四层**——A8 三层不变，复杂版是三层放大不是加层
- ❌ **core 不依赖远程**——P4，remote 是 opt-in 扩展
- ❌ **core 不训模型**——P4，复杂模型（DeepFM/Word2Vec）是 connector 扩展
- ❌ **不强迫小团队上 cluster**——规模光谱每步可停，S0/S1 永远够

---

## 7. 路线图（规模光谱，合并 architecture Phase）

| Phase | 规模 | 内容 | 优先 |
|-------|------|------|------|
| 1 ✅ | 设计 | A8 三层入宪 + scale-spectrum + recsys-design | 🔴 |
| 2 ✅ | mini | P6 修正（recall.py 注释 + A2） | 🔴 |
| 3 | standard | per-agent 读态 + to: 过滤（D1/D2 已修 v0.6.22） | 🟡 |
| 4 | standard | registry 补全 + Agent 画像目录 | 🟡 |
| 5 | cluster | 对象存储 backend（core 文件 + 本地缓存） | 🟡 |
| 6 | cluster | 分布式锁（替代文件锁） | 🟡 |
| 7 | 复杂推荐 | collab backend（CF 召回，团队核心） | 🟡 |
| 8 | 复杂推荐 | 协同 Boost（注入层 CF 信号） | 🟡 |
| 9 | 复杂推荐 | MMR 重排（注入层打散） | 🟢 |
| 10 | 复杂推荐 | 多路 Snake Merge | 🟢 |
| 11 | cluster | 分布式索引（FTS5 分片） | 🟪 |
| 12 | cluster | 分布式 decay（Hub 统一） | 🟪 |
| 13 | 远期 | i2v/seq backend（P4 外，connector） | ⚪ |
| 14 | 远期 | 联邦多 Hub（跨组织） | ⚪ |

---

## 8. 参考

- 宪法：`CONSTITUTION.md` A8（三层不变量）+ P1（文件即DB）+ P4（API-free）
- 算法复杂版：`docs/algorithms/agent-recsys-design.md`（多路召回 + 协同 Boost，三层放大）
- 蓝图：`docs/algorithms/agent-recall-architecture.md`（Phase 路线图）
- 召回引擎：`docs/algorithms/recall-engine.md`（三层架构现状）
- 评测：`docs/algorithms/recall-evaluation.md`（fusion 负优化证据，A8 依据）
