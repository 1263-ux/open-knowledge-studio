# Agent Recall Architecture — 面向 Agent 的文档推荐系统

> 生产级蓝图：把推荐系统工程架构一比一迁移到"面向 Agent 的文档召回/搜索"。
> 蓝本：datawhalechina/fun-rec `chapter_10_projects`（电影推荐 → 文档推荐）。
> 定位：OKS 的 recall 引擎升级为漏斗式三阶段流水线，生产级可用。

---

## 1. 为什么是"面向 Agent 的推荐系统"

传统推荐系统服务人类用户（电影/商品），OKS recall 服务 Agent（claude/qoder/pi/codex）。两者**架构同构**——都是"从海量候选中，在有限延迟内，为特定消费者选出最相关的小集合"。区别只在物品域（电影→文档）和消费者域（人→Agent）：

| 维度 | 电影推荐（fun-rec） | Agent 文档推荐（OKS） |
|------|---------------------|----------------------|
| 物品 | 电影（movies 表） | wiki 页 + raw 页（文件即记录） |
| 消费者 | 用户（users 表） | Agent（OKS_AGENT_ID） |
| 反馈信号 | 评分 ratings | `oks wiki use` + inject.jsonl 的 `used` + recall 命中 |
| 物品类型 | 电影类型 genres | 文档 area/type/topic |
| 物品向量 | item_embeddings.npy | 文档 embedding（默认关，可开 bge-small-zh） |
| 用户行为序列 | history（最近观影） | inject.jsonl 的 slugs 序列（最近召回） |
| 候选规模 | 10 万电影 | 百~万页 wiki |

**核心不变量**：漏斗式三阶段（召回→排序→重排）、多路召回融合、冷启动处理、特征存储与计算分离——全部一比一迁移。

---

## 2. 整体架构图（一比一映射）

```
                        ┌─────────────────────────────────────┐
                        │        离线系统（生产，定期）          │
                        │  特征工程 → 索引重建 → 画像积累 → 部署  │
                        └───────────────┬─────────────────────┘
                                        │ 产出物写入
                    ┌───────────────────▼───────────────────┐
                    │           存储层（解耦）                │
   文件即DB(P1)      │  wiki/+raw/  .oks/fts5.db  profiles/  │
   Git是migration    │  (业务数据)   (派生索引)   (Agent画像) │
                    │  settings/recall.yaml (参数=共享目录)    │
                    └───────────────┬───────────────────────┘
                                    │ 加载
                    ┌───────────────▼───────────────────────┐
                    │       在线系统（服务，Agent 每次 recall）  │
                    │  冷启动检测 → 多路召回 → 精排 → 多样性重排 → 组装 │
                    └───────────────────────────────────────┘
                                    │
                            Agent 上下文注入
```

---

## 3. 离线系统（生产）

对应 fun-rec `2.architecture` 离线流水线。OKS 的离线 = 索引重建 + 画像积累 + 参数调优。

### 3.1 特征工程（Feature Engineering）
从 wiki frontmatter + inject.jsonl 提取：
- **文档特征**：type / area / topic / decay(tier) / access_count / fingerprint
- **Agent 特征**：agent_id / 活跃 goal（profiles/goals/）/ 偏好 area（从历史 recall 统计）
- **行为序列特征**：Agent 最近 N 次 recall 的 slugs（inject.jsonl 按 agent_id 分组）

### 3.2 召回索引训练（Retrieval Indexing）
fun-rec 训练 YoutubeDNN 双塔。OKS 当前用 FTS5（BM25 倒排）作主召回——对应"轻量召回模型"角色。可选加 embedding（bge-small-zh）作语义召回通路（当前默认关，慢且小库无增益）。

### 3.3 排序"模型"（Ranking Scorer）
fun-rec 训练 DeepFM。OKS 的 6+1 因子打分（token overlap + substring + topic trace + type boost + review bonus + memory curve + goal boost）**就是排序模型**——判别式打分函数 `Score = f(Query, Page, Context)`。无需训练，参数在 settings/recall.yaml。

### 3.4 部署 + 特征上线
- **模型部署** = recall.yaml 参数 + fts5.db 索引（写 .oks/）
- **特征上线** = wiki frontmatter（已是预计算特征：decay/tier/access_count 写在每页）+ profiles/（Agent 画像/goals）

---

## 4. 在线系统（服务，Agent 每次 recall）

对应 fun-rec `4.online_pipeline`。**这是迁移的核心——OKS 当前是单阶段，要升级为三阶段漏斗**。

### 4.1 冷启动检测（Cold Start Detection）
判断 Agent 是否新（inject.jsonl 中该 agent_id 的历史 < 阈值）：
- **新 Agent** → 冷启动流程（见 §6.3）
- **老 Agent** → 正常多路召回流程

### 4.2 多路召回（Multi-Channel Recall）
并行执行多路召回策略，各路粗筛 top-N 候选：

| 召回路 | 对应 fun-rec | OKS 实现 |
|--------|-------------|----------|
| 关键词召回 | YoutubeDNN 向量 | FTS5 BM25（当前主路） |
| 主题召回 | 物品相似度 | topic trace（同 topic 页） |
| 目标召回 | 偏好类目 | goal boost（active goals 提升同 scope 页） |
| 协同召回 | —（fun-rec 无） | inject.jsonl 行为序列："召回过 X 的 Agent 也召回 Y" |

**融合策略**：Snake Merge（蛇形合并）——各路轮流取候选，确保每路有代表性进入排序。替代当前单路 top-k 截断。

### 4.3 精准排序（Ranking）
6+1 因子对召回候选（数百）精确打分，取 top-k。**复用离线参数**（recall.yaml），模型不可用时降级到召回分数排序（fun-rec 同款降级）。

### 4.4 多样性重排（Reranking）★ 新增
fun-rec 用连续打散（类型+年代维度）。OKS 迁移：
- **打散维度**：area（避免同域刷屏）+ type（避免同类型连续）
- **策略**：连续同 area/type 的候选降权或间隔插入
- **配置**：`rerank.dispersion_on: bool` + `rerank.max_consecutive: int`

这是 OKS 当前**缺失**的层——当前 recall top-k 可能全是同 area（如 computing 刷屏），重排提升多样性。

### 4.5 结果组装（Assembly）
从 wiki/ 读完整页（title + body + source 路径），按 inject budget 分层截断（L0 标题/L2 摘要，当前已有）。组装成 Agent 上下文注入格式。

---

## 5. 数据存储层（一比一映射）

| fun-rec 存储 | 角色 | OKS 对应 | 性质 |
|-------------|------|---------|------|
| PostgreSQL | 业务数据 | `wiki/` + `raw/` + `profiles/`（文件即 DB，P1 Git 是 migration） | 唯一真值源 |
| Redis | 特征缓存 | `.oks/fts5.db`（FTS5 倒排索引）+ `profiles/`（Agent 画像/goals） | 派生状态（从 wiki 重建） |
| 共享文件目录 | 模型/向量/字典 | `settings/recall.yaml`（参数）+ `.oks/`（索引/db） | 配置 + 派生 |
| Elasticsearch | 搜索倒排 | OKS FTS5（SQLite FTS5，已是倒排索引） | 派生状态 |

**原则不变**：文件即数据库（P1），派生状态（fts5.db）不入 git、可从 wiki 重建（A5/P12）。

---

## 6. 关键设计决策（一比一迁移 fun-rec §关键设计）

### 6.1 召回与排序分离
**问题**：OKS 当前 dispatch 双路径（native 含灵魂层 soul boost，fts5 无）是架构债——fts5 路径缺排序精排。
**迁移**：明确 FTS5=召回（粗筛 top-N）→ 6+1=排序（精排 top-k）。重构 dispatch 让 fts5 路径接 6+1 排序 + 灵魂层。当前 native 路径的"灵魂层"= goal boost + review bonus，fts5 路径要同样接入。

### 6.2 多路召回与融合
**问题**：OKS 当前单路（FTS5 or native），可能遗漏（关键词召回漏语义相关，topic 召回漏跨域）。
**迁移**：多路并行 + Snake Merge。新增"协同召回"路（基于 Agent 行为序列，fun-rec 无但推荐系统经典）。

### 6.3 冷启动处理
**问题**：新 Agent（首次 recall，无 inject.jsonl 历史）——当前 OKS 无显式冷启动，goal boost 是唯一信号。
**迁移**：三级冷启动策略（对应 fun-rec UCB + 偏好 + 热门）：
1. **UCB topic 探索**：未访问的 topic 给更高探索奖励（平衡 exploit 已知 vs explore 新域）
2. **goal 兜底**：active goals 提升同 scope 页（已有，保留）
3. **热门兜底**：access_count 高的页（"热门"对应）
随 Agent 积累 recall 历史，逐渐过渡到正常多路召回。

### 6.4 特征存储与计算分离
**问题**：在线 recall 对延迟敏感（hook 要求毫秒级）。
**迁移**：OKS 已有——fts5.db 是预计算倒排索引（从 wiki 重建），recall 从索引读不重算 BM25 全库。wiki frontmatter 的 decay/tier/access_count 是预计算特征（decay 命令定期更新）。**已符合，无需改**。

---

## 7. 迁移路线图（Phase 1-6）

| Phase | 内容 | 改动范围 | 优先级 |
|-------|------|---------|--------|
| **1** | 本架构文档 + CONSTITUTION A8（Agent recall pipeline 漏斗） | docs + 宪法 | 🔴 地基 |
| **2** | dispatch 重构：FTS5=召回 → 6+1=排序，fts5 接灵魂层 | recall.py | 🔴 还债 |
| **3** | 多路召回 + Snake Merge（FTS5 + topic + goal + 协同） | recall.py 新模块 | 🟡 |
| **4** | 多样性重排层（area/type 打散） | recall.py rerank | 🟡 |
| **5** | 冷启动处理（UCB topic 探索 + 热门兜底） | recall.py cold_start | 🟢 |
| **6** | 生产级（延迟监控 p50/p99 + 离线索引重建 cron + Agent 画像积累） | health.py + cli | 🟢 |

**Phase 1 先行**（本文档 + 宪法），确认架构后再动代码。Phase 2 是还架构债（dispatch 双路径），为 3-5 铺路。

---

## 8. 与 fun-rec 的本质差异（不盲搬）

1. **物品域**：电影是结构化记录（DB 行），文档是半结构化 markdown（frontmatter + 正文）。OKS 用文件 + frontmatter，不用 DB。
2. **消费者**：Agent 不像人有"偏好"——Agent 的"偏好"= active goals + 历史 recall 的 topic 分布。冷启动信号更弱（新 Agent 无任何画像），需 goal + 热门兜底。
3. **规模**：电影 10 万，wiki 百~万页。漏斗压缩比不同，但三阶段架构仍必要（万页级时召回粗筛不可省）。
4. **延迟预算**：电影推荐 200ms，OKS hook recall 要毫秒级（<50ms）。更激进地依赖预计算索引，少在线重算。
5. **生成式**：fun-rec 下篇生成式推荐（OneRec/HSTU）**不迁移**——OKS 是"检索已有记忆"不是"生成新记忆"，dreaming 层的"生成"是生成知识表示不是生成召回结果。

---

## 参考

- 蓝本：`raw/2026/08/31/fun-rec/docs/_sources/chapter_10_projects/`（architecture/offline_pipeline/online_pipeline）
- OKS 现状：`cli/knowledge_studio/recall.py`（dispatch + 6+1 因子）+ `assets/settings/recall.yaml`（参数）
- 设计约束：`CONSTITUTION.md` A1-A7（P1 文件即DB / P4 API-free / A5 原子写 / A6 wiki 命名 / A7 mail 存储）

---

# Part B：个人版 + 团队版双形态

> 推荐系统多用户场景，和团队多 Agent 1:1 同构。OKS 分两种形态：
> **个人版**（单 Agent）和 **团队版**（多 Agent 共享 KB + 协同召回）。
> 这是把 fun-rec 的多用户推荐 1:1 复用到 Agent 域。

## 9. 为什么是双形态

传统推荐系统天然服务多用户（每个用户独立画像 + 行为序列 + 协同过滤）。OKS 当前是单 Agent 视角——一个 Agent 用一个 KB。但团队场景（多个 Agent 协作一个 KB：claude 写 wiki、qoder 改代码、pi 调研、codex review）和推荐系统多用户**完全同构**：

| 推荐系统多用户 | OKS 团队版多 Agent |
|---------------|-------------------|
| users 表（用户记录） | `profiles/agents/{agent_id}/`（Agent 画像目录） |
| 用户画像（偏好/人口统计） | Agent 画像（scope/goals/历史 topic 分布/能力） |
| 用户行为序列（最近观影） | `inject.jsonl` 按 agent_id 分组的 slugs 序列 |
| 协同过滤 CF（看过 X 的人也看 Y） | Agent 间协同召回（召回过 X 的 Agent 也召回 Y） |
| 偏好类目召回 | Agent 偏好 scope/topic 召回 |
| 冷启动新用户 | 新 Agent 入团（无 inject 历史） |
| 多样性（跨用户视角） | 跨 Agent 多样性（避免同 Agent 视角刷屏） |

## 10. 个人版（当前 OKS）

```
单实例 (文件即 DB, Git 是 migration, P1)
  ├─ 单 Agent 或多 Agent 但无显式画像隔离
  ├─ mail 跨 Agent 通信 (A7, 已有)
  ├─ 6+1 因子召回 (判别式打分, §3.3)
  └─ profiles/agents/registry.jsonl (Agent 注册, 当前只 1 个)
```

定位：**个人知识库**——一个 Agent 维护、一个用户消费。当前架构已够（§1-8 的三阶段漏斗升级后）。

## 11. 团队版（新增形态）

```
单实例 共享 (raw/ + wiki/ 全 Agent 共用, 文件即 DB 不变)
  ├─ 多 Agent 各自画像: profiles/agents/{agent_id}/{profile,goals,history,prefs}.md
  ├─ registry.jsonl 全 Agent 注册 (补全 pi/qoder/claude/codex)
  ├─ inject.jsonl 按 agent_id 分组 (每 Agent 独立行为序列)
  ├─ 协同召回 (CF 1:1): 召回过 X 的 Agent 也召回 Y
  ├─ Agent 画像召回: 基于 Agent 历史 topic 分布 (偏好类目召回 1:1)
  ├─ 冷启动: 新 Agent 入团 (UCB topic 探索 + 热门兜底)
  └─ 权限/信任: 不同 Agent 可访问 scope (如 codex 只读 computing)
```

### 11.1 协同召回（Collaborative Recall）★ 团队版核心

推荐系统 CF（协同过滤）的 Agent 版：
- **ItemCF Agent 版**：当前 Agent 召回了页 X，找"也召回过 X 的其他 Agent 还召回过什么 Y"——从 inject.jsonl 跨 Agent 共现挖掘。这是多用户 CF 的 1:1 迁移。
- **UserCF Agent 版**：找"和当前 Agent 召回历史相似的 Agent"（行为序列重叠度高），推荐那个 Agent 召回过但本 Agent 没召回的页。
- **数据源**：`records/inject.jsonl` 按 agent_id 分组——每条记录 `{agent_id, slugs, used}`，跨 Agent 统计页共现。

这是个人版没有的召回路（个人版只有 FTS5 + topic + goal）。团队版的差异化价值所在。

### 11.2 Agent 画像召回（Preference Recall）

推荐系统"偏好类目召回"的 Agent 版：
- 每个 Agent 的历史 recall 统计 topic/area 分布 → 偏好域
- 如 pi 偏 computing/concepts，codex 偏 computing/strategies
- 召回时提升偏好域页的权重（对齐 goal boost，但是基于行为非显式 goal）

### 11.3 权限与信任（Permission & Trust）

个人版无此问题（单 Agent 拥有全部）。团队版要解决：
- **scope 可见性**：不同 Agent 可访问的 wiki 域（如 codex 只读 computing，pi 可写 drafts）
- **信任分级**：Agent 写的 drafts 待 human review（A3 Dreaming 不变），但 Agent 间可互评（mail 已有 trust 机制 P9）
- **实现**：profiles/agents/{agent_id}/profile.md 的 `scope` 字段 + recall 时按 scope 过滤

### 11.4 联邦（可选，Phase 远期）

多实例联邦：团队 A 的 KB + 团队 B 的 KB，共享部分 raw 但 wiki 各自维护。对应推荐系统的跨域推荐。这是远期，当前不实现。

## 12. 双形态路线图（合并 Phase 1-6）

| Phase | 内容 | 形态 | 优先级 |
|-------|------|------|--------|
| 1 ✅ | 架构文档（本）+ A8 宪法（待 P2 实现） | 共用 | 🔴 地基 |
| **2** | dispatch 重构：FTS5=召回→6+1=排序，fts5 接灵魂层 | 共用 | 🔴 还债 |
| 3 | 多路召回 + Snake Merge（FTS5+topic+goal+**协同**） | 协同=团队版 | 🟡 |
| 4 | 多样性重排（area/type 打散 + **跨 Agent 视角**） | 团队版扩展 | 🟡 |
| 5 | 冷启动（UCB topic + 热门 + **新 Agent 入团**） | 团队版扩展 | 🟢 |
| 6 | 生产级（延迟监控 + 索引重建 cron + **Agent 画像积累**） | 团队版扩展 | 🟢 |
| **7** | registry 补全 + profiles/agents/{id}/ 画像目录 | 团队版 | 🟡 |
| **8** | 协同召回（ItemCF/UserCF Agent 版，从 inject.jsonl） | 团队版核心 | 🟡 |
| 9 | 权限/scope 可见性 + recall 按 scope 过滤 | 团队版 | 🟢 |
| 10 | 联邦多实例（远期） | 团队版远期 | ⚪ |

**关键洞察**：Phase 2-6 是共用基础（个人版 + 团队版都受益），Phase 7-8 是团队版差异化（协同召回是团队版核心价值），Phase 9-10 是团队治理。**先做共用基础（P2-6），再做团队差异化（P7-8）**。

## 13. 个人版 vs 团队版的代码开关

```yaml
# settings/recall.yaml
mode: personal  # personal | team

team:
  collaborative_recall: true   # Phase 8: ItemCF/UserCF Agent 版
  agent_profile_recall: true    # Phase 7: 偏好域召回
  cross_agent_diversity: true   # Phase 4: 跨 Agent 视角打散
  scope_filter: true            # Phase 9: 按 Agent scope 过滤
```

`mode: personal`（默认）→ 个人版，跳过团队版召回路，零开销。
`mode: team` → 启用协同召回 + 画像 + 跨 Agent 多样性。向后兼容。

## 14. 团队版的本质约束（不破坏个人版）

1. **文件即 DB 不变**（P1）——团队版不引入数据库，多 Agent 画像仍是文件（profiles/agents/{id}/）
2. **API-free 不变**（P4）——协同召回的统计在 CLI core（读 inject.jsonl 算共现），不调外部 API
3. **向后兼容**——`mode: personal` 时团队版代码静默不生效，个人版用户无感知
4. **Agent 身份显式**——团队版要求 `OKS_AGENT_ID` 注入（mail 已有 P9），recall 按 agent_id 分组行为

---

## 参考（Part A + B）

- 蓝本：`raw/2026/08/31/fun-rec/docs/_sources/chapter_10_projects/`（architecture/offline/online_pipeline）
- OKS 现状：`cli/knowledge_studio/recall.py`（dispatch + 6+1 因子）+ `assets/settings/recall.yaml`（参数）
- 设计约束：`CONSTITUTION.md` A1-A7（P1 文件即DB / P4 API-free / A5 原子写 / A6 wiki 命名 / A7 mail 存储 / P9 trust 不可自产）
- 多用户推荐 1:1 映射：fun-rec `users` 表 → OKS `profiles/agents/{id}/`；CF → 协同召回
