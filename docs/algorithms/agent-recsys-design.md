# Agent Recall System — 复杂版设计（fun-rec 1:1 映射）

> 把生产级推荐系统**完整一比一**搬到 Agent 域。电影→文档，用户→Agent，评分→召回+使用。
> 复杂版：召回5路 + 排序3维 + 重排2策略 + 离线/在线 pipeline + 存储4层映射。
> 与 `agent-recall-architecture.md`（蓝图 Phase 路线图）互补：本文是**完整算法设计**。

---

## 0. 设计原则：一模一样，但面向 Agent

**fun-rec 的级联架构原样保留**——召回(候选千级)→排序(精排打分)→重排(全局优化) 三阶段漏斗。
**唯一改变的是域**：从"给用户推电影"变成"给 Agent 召回知识文档"。

| fun-rec 推荐系统 | OKS Agent Recall System | 说明 |
|-----------------|--------------------------|------|
| 物品=电影 | 文档=wiki 页 + raw 材料 | 被推荐的对象 |
| 用户 | Agent（pi/qoder/codex/claude） | 推荐的消费者 |
| 评分表 ratings | `records/inject.jsonl` | "Agent 召回过 doc X" = 一次正反馈 |
| users 表 | `profiles/agents/{agent_id}/` | Agent 画像目录 |
| movies 表 | `wiki/` + `raw/`（文档本身） | 物品元数据即 frontmatter |
| 用户-物品交互矩阵 | Agent-doc 注入矩阵 | 稀疏矩阵：行=Agent，列=doc slug，值=召回次数 |
| 观影行为序列 | Agent 的 inject slug 序列 | 时序的"最近召回过哪些 doc" |
| 物品向量 item_emb | 文档向量（FTS5 词向量 / BGE） | 文档的向量化表示 |
| genres 电影类型 | area / type / topic | 文档的类目特征 |
| 评分=显式反馈 | recall=隐式 + wiki use=显式 | Agent 召回=点击，wiki use=收藏 |
| PostgreSQL 业务库 | 文件即 DB（P1） | wiki/ + raw/ + profiles/ 就是库 |
| Redis 特征缓存 | `.oks/` 派生缓存 | FTS5 db + 共现矩阵 + 画像 jsonl |
| Elasticsearch 搜索 | FTS5 倒排索引 | 文档全文检索 |
| 共享目录模型文件 | `settings/recall.yaml` 参数 | P4 API-free：无模型，参数即"模型" |

**三处本质差异（不破坏 1:1 映射）**：
1. **P4 API-free**——不做 DeepFM/YoutubeDNN 模型训练，用 FTS5 + 6+1 因子打分（判别式，非学习式）。这是约束不是妥协：Agent 域数据稀疏（单 Agent 召回历史远少于电影评分），训不出好模型，判别式更稳。
2. **文件即 DB（P1）**——没有 Redis/PG/ES 三件套，用文件 + FTS5 派生。Redis 的"特征缓存"角色由 `.oks/*.jsonl` 派生文件承担，启动时重建。
3. **知识非消费**——文档召回后"用"（注入上下文被 Agent 引用），不是"看"（评分）。反馈信号是 inject（召回）+ wiki use（显式使用），比电影评分更稀疏但更可信。

---

## 1. 总体架构：三阶段漏斗

```
Agent query (自然语言)
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ 召回层（Retrieval）— 候选千→百                       │
│  5 路并行: CF / I2I / 双塔 / 序列 / 流式索引         │
│  Snake Merge 蛇形合并融合                            │
└─────────────────────────────────────────────────────┘
  │ 候选 ~200
  ▼
┌─────────────────────────────────────────────────────┐
│ 排序层（Ranking）— 精排打分                         │
│  3 维: 特征交叉(6+1因子) / 多目标 / 多场景          │
└─────────────────────────────────────────────────────┘
  │ top ~20
  ▼
┌─────────────────────────────────────────────────────┐
│ 重排层（Re-ranking）— 全局优化                      │
│  2 策略: 贪心 MMR / 个性化多样性                    │
└─────────────────────────────────────────────────────┘
  │ top-k 注入 Agent 上下文
  ▼
Agent 收到 <recalled-memory> + <recalled-mail>
```

**和 fun-rec 的对应**：召回=chapter_1_retrieval（5 路），排序=chapter_2_ranking（DeepFM/多目标/多场景），重排=chapter_3_rerank（贪心/个性化）。

---

## 2. 召回层（Retrieval）— 5 路

> 对应 fun-rec `chapter_1_retrieval`：CF / I2I / 双塔 / 序列 / 流式索引。
> 召回的目标：从全量 wiki（百→万页）筛出 ~200 候选，为排序提供高质量输入。

### 2.1 CF 协同过滤（Agent 版）

> 对应 `chapter_1_retrieval/1.cf`：ItemCF / UserCF / Swing

**核心思想**（fun-rec 原文）："用户的兴趣具有连贯性，喜欢某个物品的用户往往也会对相似的物品感兴趣"。
Agent 版：**召回过 doc X 的 Agent 也召回过 doc Y**。

#### 2.1.1 ItemCF Agent 版

fun-rec 公式：`w_ij = C[i][j] / sqrt(|N(i)| × |N(j)|)`，C[i][j] 是同时对 i、j 有行为的用户数。

Agent 版：
- `C[i][j]` = 同时召回过 doc i 和 doc j 的 **Agent 数**（从 inject.jsonl 跨 Agent 聚合）
- `|N(i)|` = 召回过 doc i 的 Agent 总数
- `w_ij` = 文档 i、j 的相似度（共现 Agent 数标准化，防热门 doc 刷屏）

线上召回流程（1:1）：
1. 取当前 Agent 最近召回的 N 个 doc 作种子（inject 序列尾部）
2. 每个种子 doc 找 Top-10 相似 doc（w_ij 排序）
3. 兴趣分数 `p(u,i) = Σ_{j∈N(u)} w_ij × r_uj`，r_uj=召回强度（次数/时间衰减）
4. Top-N 作为 ItemCF 通道候选

**OKS 实现**：`records/inject.jsonl` 按行 `{agent_id, slugs, ts}` 离线聚合共现矩阵 → `.oks/itemcf_matrix.jsonl`（派生，可重建）。在线查表。

**数据稀疏问题**：Agent 域单 Agent 召回历史可能 <100（远少于电影评分千级）。ItemCF 退化严重。缓解：
- 跨 Agent 聚合（团队版）——这正是团队版的核心价值（§agent-recall-architecture Part B §11.1）
- 降阈值：共现≥1 即纳入（电影要≥10 才稳，Agent 域≥1 即用）
- 时间窗：只看最近 30 天共现（Agent 兴趣漂移比用户快）

#### 2.1.2 UserCF Agent 版

fun-rec：找"和当前用户行为相似的用户"，推那些用户看过但当前用户没看的。

Agent 版：
- Agent 相似度 = inject slug 集合的 Jaccard/余弦
- `sim(a, b) = |N(a) ∩ N(b)| / |N(a) ∪ N(b)|`，N(a)=Agent a 召回过的 slug 集
- 找 Top-K 相似 Agent，取他们召回过但当前 Agent 没召回的 doc

**OKS 实现**：同 inject.jsonl 聚合。UserCF 和 ItemCF 共用一份共现数据，不同视角。

#### 2.1.3 Swing Agent 版

fun-rec Swing：对共现用户少的物品对加权（长尾物品更可靠）。

Agent 版：共现 Agent 少的 doc 对（如 2 个 Agent 都召回过 X 和 Y）比 100 个 Agent 都召回过的热门对更可信（热门共现可能是巧合）。Swing 公式降热门权重。

**适用场景**：OKS 团队版早期 Agent 少（4 个），Swing 比 ItemCF 更适合小数据。团队版默认 Swing 优于 ItemCF。

### 2.2 I2I 向量化物品相似（Agent 版）

> 对应 `chapter_1_retrieval/2.i2i`：word2vec / item2vec / EGES / Airbnb

fun-rec 思想：把用户行为序列当"句子"，物品当"词"，用 word2vec 学物品向量，相似物品向量近。

#### 2.2.1 word2vec Agent 版

Agent 版：
- "句子" = 每个 Agent 的 inject slug 序列（按时序）
- "词" = doc slug
- Skip-gram 学每个 doc 的向量
- 召回：当前 Agent 最近召回的 doc → 向量近的 doc

**OKS 实现**：离线训练（gensim Word2Vec）→ `.oks/doc_vectors.pkl`。在线 ANN 检索（小库直接暴力余弦，大库上 FAISS）。

**和 ItemCF 的区别**：ItemCF 靠共现统计（显式），word2vec 靠序列上下文（隐式，能抓"召回 A 后常召回 B"的时序关系）。Agent 序列短时 word2vec 学不动——要 fallback 到 ItemCF。

#### 2.2.2 item2vec / EGES Agent 版

EGES（fun-rec）：多 side info——物品除 ID 向量外，还有类目/价格等 side info 向量，加权融合。

Agent 版：doc 的 side info = `area` / `type` / `topic` / `importance`（frontmatter）。学 doc 向量时融合 side info，让"同 area 的 doc"向量更近。缓解新 doc 冷启动（新 doc 无 inject 历史，但有 area/type side info）。

#### 2.2.3 Airbnb Agent 版

Airbnb（fun-rec）：booked 作正样本，passed 作负样本，优化向量的"预订区分度"。

Agent 版：
- 正样本 = Agent **使用**过的 doc（`wiki use` 显式信号 + inject 后被引用）
- 负样本 = 召回了但没用的 doc（inject 但 wiki use=0）
- 训 doc 向量区分"会用的"和"召回但不用的"

**价值**：区分"召回即用"和"召回忽略"，提升召回的 use 转化率（不只召回相关，还要召回有用）。

### 2.3 双塔模型（Agent 版）

> 对应 `chapter_1_retrieval/3.two_tower`：FM / DSSM / YoutubeDNN

fun-rec：用户塔（画像+行为）+ 物品塔（特征），双塔向量匹配 U2I。

#### 2.3.1 FM Agent 版

fun-rec FM：二阶特征交叉因子分解机。

Agent 版（P4 退化版）：Agent 特征（scope/goals/历史 topic 分布）× 文档特征（area/type/importance）的二阶交叉——**这其实就是 6+1 因子里的 type boost + topic trace + goal boost**。FM 在 Agent 域退化为判别式打分（不训 FM 模型，直接用启发式交叉权重，P4 约束）。

#### 2.3.2 DSSM Agent 版

fun-rec DSSM：用户塔（行为序列 DNN）+ 物品塔（标题/描述 DSSM），双塔 cosine。

Agent 版：
- Agent 塔：inject 序列 + 画像 → Agent 向量
- 文档塔：标题 + 内容 → 文档向量
- 召回：Agent 向量 → 最近文档向量（ANN）

**OKS 实现**：文档向量用 BGE-small-zh（已验证可用但慢，默认关）。Agent 向量 = 最近召回文档向量的平均（session-based）。P4 约束下不训 DSSM，用预训练 embedding + 简单聚合。

#### 2.3.3 YoutubeDNN Agent 版

fun-rec：用户历史序列 → 预测下一个点击的物品。

Agent 版：Agent 最近召回的 N 个 doc → 预测下一个该召回的 doc。这是**序列预测的生成式召回**——和下篇生成式范式重叠（§生成式章节）。OKS 暂不实现（P4 无模型训练），但作为远期方向（embedding + 序列建模）。

### 2.4 序列召回（Agent 版）

> 对应 `chapter_1_retrieval/4.sequence`：MIND / SDM

fun-rec：用户行为序列建模，捕捉兴趣的多样性和动态变化。

#### 2.4.1 MIND Agent 版（multi-interest）

fun-rec MIND：一个用户序列 → 多个兴趣向量（胶囊网络），因为用户兴趣是多峰的。

Agent 版：Agent 一个 session 召回序列可能跨多个 topic（如 pi 同时召回 git + embedding + hook），MIND 拆成多个兴趣通道，每通道独立召回。这解决"Agent 一次问多个主题"的场景（用户 prompt 含多意图）。

**OKS 实现**：从 inject 序列聚类（topic 维度），每簇一个"兴趣"，各自召回后合并。

#### 2.4.2 SDM Agent 版（长短期）

fun-rec SDM：长期兴趣（历史全量）+ 短期兴趣（最近 session），LSTM 建模。

Agent 版：
- 短期 = 当前 session 的 inject（最近 3-5 个 doc）
- 长期 = 历史 inject 的 topic 分布（Agent 画像）
- 召回时短期加权更高（当前任务相关），长期作背景

**OKS 实现**：短期从 session-start 到现在的 inject slugs；长期从 `profiles/agents/{id}/profile.md` 的 topic 分布。加权融合。

### 2.5 流式索引（Agent 版）

> 对应 `chapter_1_retrieval/5.streaming_index`：Trinity / StreamingVQ

fun-rec：突破静态索引局限，实时更新。

#### 2.5.1 Trinity Agent 版

fun-rec Trinity：实时索引更新机制。

Agent 版：**OKS 天然就是流式的**——wiki/ 新增文件，FTS5 索引重建即"上线"（`oks recall` 重建或 cron）。无静态索引问题。但类比：新增 wiki 后**立即**可召回（不等 cron），靠 FTS5 增量插入。

#### 2.5.2 StreamingVQ Agent 版

fun-rec StreamingVQ：向量量化压缩，大库索引优化。

Agent 版：万页级时压缩文档向量索引（PQ 乘积量化）。OKS 小库（百页）不需要，万页级远期。

### 2.6 Snake Merge 蛇形合并

fun-rec 多路召回融合：各路 Top-N 蛇形交错（round-robin）合并，避免单路刷屏，保证多样性。

Agent 版：5 路（CF/I2I/双塔/序列/流式）各 Top-40，蛇形取 200 候选。如：
```
路1[1] 路2[1] 路3[1] 路4[1] 路5[1] 路1[2] 路2[2] ...
```

**OKS 实现**：`recall.py` dispatch 合并时按路轮转取，去重（slug 唯一）。

---

## 3. 排序层（Ranking）— 3 维

> 对应 fun-rec `chapter_2_ranking`：特征交叉 / 多目标 / 多场景。
> 召回的 200 候选精排到 20。

### 3.1 特征交叉（6+1 因子 = DeepFM Agent 版）

> 对应 `chapter_2_ranking/2.feature_crossing`（DeepFM）

fun-rec DeepFM：一阶特征 + 二阶交叉（FM）+ 高阶（DNN），学特征间交互。

Agent 版（P4 退化判别式）——**6+1 因子就是 DeepFM 的特征交叉启发式版**：

| DeepFM 特征 | OKS 6+1 因子 | 交叉含义 |
|------------|-------------|---------|
| query-doc 文本交叉 | ① token overlap | query 词 vs doc 词的命中 |
| 子串命中 | ② substring | query 作为 doc 子串出现 |
| 类目交叉 | ③ topic trace | query topic vs doc topic |
| 类型权重 | ④ type boost | doc type（concept/strategy）的先验 |
| 质量交叉 | ⑤ review bonus | human review 状态加权 |
| 时间交叉 | ⑥ memory curve | decay 时间衰减 |
| 目标交叉 | ⑦ goal boost（+1） | active goal vs doc topic |

**为什么不训 DeepFM**（P4）：Agent 域数据稀疏（单 Agent 召回历史 < 电影评分千级），训不出稳定的深度交叉模型；6+1 启发式交叉在小数据上更稳，且可解释（每因子可审计）。

**未来演进**：当 OKS 团队版 Agent 数 × 召回量 上千级，可训 DeepFM 替代 6+1（但违 P4，需 Agent host 侧做，不进 core）。

### 3.2 多目标（Agent 版）

> 对应 `chapter_2_ranking/4.multi_objective`：CTR/CVR/时长等多目标

fun-rec：不止预测点击，还预测转化、时长、分享等多目标，加权融合。

Agent 版——多目标 = "召回相关" + "会被使用" + "新鲜"：
- **相关性**（≈CTR）：6+1 因子总分
- **使用性**（≈CVR）：该 doc 历史被召回后被 `wiki use` 的概率（从 inject→use 转化率学，类似 Airbnb 正负样本）
- **新鲜度**（≈时长）：decay tier（hot/warm/cold），新或热的 doc 加权

多目标加权：`final = α·relevance + β·use_prob + γ·freshness`，α/β/γ 从 `recall.yaml` 配。

### 3.3 多场景（Agent 版）

> 对应 `chapter_2_ranking/5.multi_scenario`：跨场景建模

fun-rec：不同业务场景（首页/详情页/搜索）用不同模型或共享+场景 embedding。

Agent 版——多场景 = 不同 **scope**：
- computing scope：技术知识召回（默认）
- personal scope：个人画像召回（简历/goals）
- engineering scope：工程实践召回

场景由 `--scope` 参数或 Agent profile.scope 决定，不同场景 6+1 权重不同（如 personal scope 降 type boost，升 personal relevance）。

---

## 4. 重排层（Re-ranking）— 2 策略

> 对应 fun-rec `chapter_3_rerank`：贪心 / 个性化。

### 4.1 贪心重排 MMR（Agent 版）

> 对应 `chapter_3_rerank/1.greedy`

fun-rec 贪心：逐步选最大化"分数 - λ·与已选相似度"的物品，平衡相关性和多样性。

Agent 版——MMR（Maximal Marginal Relevance）：
```
选第1个: argmax score(d)
选第k个: argmax [score(d) - λ·max_{d'∈selected} sim(d, d')]
```
- `sim(d, d')` = doc 间相似（area 重合 + type 重合 + topic 重合）
- `λ` 从 `recall.yaml` 配（默认 0.5，均衡）

**效果**：避免 top-k 全是同一 area 的 doc（如 5 个 git 相关全占），打散到不同 area。

### 4.2 个性化多样性（Agent 版）

> 对应 `chapter_3_rerank/2.personalized`

fun-rec：按用户偏好的多样性策略（活跃用户多样新颖，新用户热门保底）。

Agent 版——按 Agent 画像的多样性：
- 活跃 Agent（inject 多）：高多样性（MMR λ 大），推长尾
- 新 Agent（冷启动）：低多样性（λ 小），热门 + goal 兜底
- Agent 偏好域：保留偏好域密度（如 pi 偏 concepts，打散时 concepts 保留 40%）

**OKS 实现**：`profiles/agents/{id}/profile.md` 的 `diversity_pref` 字段驱动 λ。

---

## 5. 离线流水线（Offline Pipeline）

> 对应 `chapter_10_projects/3.offline_pipeline`：特征工程→训练→部署→特征上线。

fun-rec 离线：处理全量历史，训模型，算向量/相似度，写共享存储。小时-天级。

Agent 版离线（P4 无模型训练，但有派生计算）：

```
oks decay                    # ① 特征工程：更新 memory curve（时间衰减特征）
oks recall --rebuild-index   # ② 召回索引：FTS5 重建（新 wiki 增量）
oks collab build              # ③ 协同矩阵：从 inject.jsonl 聚合 ItemCF/UserCF 共现（★新增）
oks agent-profile build       # ④ 画像上线：profiles/agents/{id}/ topic 分布 + 偏好域
```

**产物**（写 `.oks/` 派生，可重建）：
- `.oks/fts5.db` — FTS5 倒排索引（对应 ES）
- `.oks/itemcf_matrix.jsonl` — 文档共现矩阵（对应 item 相似度矩阵）
- `.oks/agent_profiles/{id}.jsonl` — Agent 画像缓存（对应 Redis user profile）
- `.oks/doc_vectors.pkl` — 文档向量（可选，embedding 慢默认关）

**频率**：decay 每日 cron，索引重建每周或 wiki 变更触发，协同矩阵每日（inject 增量）。

---

## 6. 在线服务（Online Pipeline）

> 对应 `chapter_10_projects/4.online_pipeline`：实时请求→召回→排序→重排→返回。

fun-rec 在线：百毫秒级响应，依赖离线产物。

Agent 版在线——`oks recall <query>`：

```
query → [召回5路] → Snake Merge 200 → [排序6+1精排] → 20 → [重排MMR] → top-k → 注入
```

**延迟预算**（小库百页）：
- FTS5 召回：<5ms
- 6+1 排序 200 候选：<10ms
- MMR 重排 20：<5ms
- 总计 <20ms（远低于 fun-rec 百毫秒，因无模型推理）

**团队版增量**：协同召回路（ItemCF/UserCF）查 `.oks/itemcf_matrix.jsonl`，<5ms。

**hook 注入**（`user-prompt-recall`）：UserPromptSubmit 触发 recall → 注入 `<recalled-memory>` + `<recalled-mail>`。这是"在线服务"的入口。

---

## 7. 存储层映射

> 对应 fun-rec 存储四件套：PG / Redis / 共享目录 / ES。

| fun-rec 存储 | OKS 映射 | 内容 | 重建 |
|-------------|---------|------|------|
| PostgreSQL（业务库） | 文件即 DB（P1）：`wiki/` + `raw/` + `profiles/` | 业务数据本体 | Git 是 migration |
| Redis（特征缓存） | `.oks/*.jsonl` 派生缓存 | 画像/共现矩阵/inject 序列 | 从 wiki + inject.jsonl 重建 |
| 共享目录（模型文件） | `settings/recall.yaml` 参数 | 无模型，参数即"模型"权重 | 配置文件 |
| Elasticsearch（搜索） | `.oks/fts5.db` FTS5 倒排 | 全文倒排索引 | `oks recall --rebuild-index` |

**关键洞察**：OKS 的"派生状态"（`.oks/` + fts5.db + 共现矩阵）= fun-rec 的 Redis+ES+模型文件。全可从 wiki + inject.jsonl 重建，不入 git（P1 派生状态原则）。

---

## 8. 冷启动

> 对应推荐系统冷启动：新用户 / 新物品 / 新场景。

### 8.1 新 Agent 冷启动（= 新用户）

Agent 无 inject 历史 → ItemCF/UserCF/序列召回全失效。策略：
- **UCB topic 探索**：遍历 topic 域，每 topic 召回一次，学偏好（多臂老虎机，exploitation/exploration 平衡）
- **goal 兜底**：Agent profile 的 active goals 驱动召回（⑦ goal boost）
- **热门兜底**：高 importance + hot tier 的 doc 兜底
- **画像冷启动**：首次 inject 后即建画像，下次起 UserCF 可用

### 8.2 新文档冷启动（= 新物品）

新 wiki 页无 inject 反馈 → CF/I2I 无数据。策略：
- **内容召回**：FTS5 靠内容匹配（无依赖 inject 历史）
- **side info 召回**：area/type 向量（EGES 思路，新 doc 有 frontmatter）
- **新鲜度 boost**：新 doc decay tier=hot，短期加权
- **注入即数据**：第一次被召回后进入共现矩阵，CF 逐步生效

### 8.3 新场景冷启动（= 新 scope）

新 area 域无历史 → 多场景模型无数据。策略：fallback 到全局 6+1，scope 权重默认。

---

## 9. 团队版差异化（复杂版的核心增量）

> 单 Agent 版只需 FTS5 + 6+1（个人版够）。复杂版的价值在**多 Agent 协同**——这把推荐系统多用户能力完整发挥。

### 9.1 协同召回（CF 路的完整实现）

个人版无 CF（单 Agent 无共现）。团队版 CF 是核心增量：
- **ItemCF**：跨 Agent 文档共现 → "召回 X 的 Agent 也召回 Y"
- **UserCF**：Agent 行为相似 → "和当前 Agent 像的 Agent 召回过什么"
- **Swing**：小团队（4 Agent）的稳健 CF

### 9.2 Agent 画像召回（偏好类目路）

Agent 历史 topic 分布 → 偏好域召回（个人版无意义，单 Agent 偏好=全局）。

### 9.3 跨 Agent 多样性（重排增量）

团队版重排考虑"跨 Agent 视角"——避免同一 Agent 视角刷屏，让不同 Agent 的召回都能曝光。

### 9.4 Agent 身份贯穿

所有多 Agent 路都需 `OKS_AGENT_ID`：
- CF 共现按 agent_id 分组
- 画像按 agent_id 隔离
- 读态 per-agent（D1 修复，`mail/.read/{agent_id}.jsonl`）
- mail 按 to: 过滤（D2 修复）

---

## 10. 路线图（完整版，合并 architecture Phase）

| Phase | 内容 | 对应 fun-rec | 形态 | 优先 |
|-------|------|-------------|------|------|
| 1 ✅ | 架构文档（本 + architecture）+ A8 宪法待 P2 | 设计 | 共用 | 🔴 |
| **2** | dispatch 重构：FTS5=召回→6+1=排序 | 召回+排序 | 共用 | 🔴 |
| 3 | Snake Merge 多路融合 | 召回融合 | 共用 | 🟡 |
| 4 | MMR 重排（贪心） | 重排 | 共用 | 🟡 |
| **7** | registry 补全 + Agent 画像目录 | users 表 | 团队 | 🟡 |
| **8** | ItemCF/UserCF/Swing 协同召回 | CF 召回 | 团队核心 | 🟡 |
| 9 | 多目标（use 转化率 + freshness） | 多目标排序 | 共用 | 🟢 |
| 10 | word2vec doc 向量 + I2I | I2I 召回 | 共用 | 🟢 |
| 11 | MIND 多兴趣 + SDM 长短期 | 序列召回 | 共用 | 🟢 |
| 12 | 冷启动 UCB + 热门兜底 | 冷启动 | 共用 | 🟢 |
| 13 | scope 权限过滤 | 多场景 | 团队 | 🟪 |
| 14 | 离线 pipeline cron（decay+索引+共现） | 离线 | 共用 | 🟪 |
| 15 | 个性化多样性（Agent 偏好 λ） | 个性化重排 | 团队 | ⚪ |
| 16 | 流式索引（增量 FTS5） | 流式 | 共用 | ⚪ |
| 17 | 联邦多实例（远期） | 跨域 | 团队远期 | ⚪ |

**执行顺序**：P2（dispatch 还债）→ P7-8（团队基础+协同召回，复杂版核心）→ P3-4（融合+重排）→ P9-12（精排+冷启动）→ P13-16（治理+生产化）。

---

## 11. P4 约束下的诚实边界

**不做的**（违 P4 或数据不足）：
- ❌ DeepFM/DSSM/YoutubeDNN 模型训练（P4 API-free，core 不训模型）
- ❌ 在线模型推理（core 不调模型服务）
- ❌ Redis/PG/ES 三件套（P1 文件即 DB）

**替代**：
- ✅ 6+1 因子启发式交叉 = DeepFM 的小数据退化版
- ✅ FTS5 + BGE 预训练 = DSSM 双塔的退化版（不训，用预训练）
- ✅ 共现矩阵统计 = CF 的判别式版（不训矩阵分解，直接统计）
- ✅ 文件 + `.oks/` 派生 = Redis+ES+PG 的退化版

**演进路径**（不进 core，Agent host 侧）：
- 团队版 Agent 数上千 → 可在 host 侧训 DeepFM 替代 6+1
- 大库万页 → 可在 host 侧上 FAISS 替代暴力检索
- core 永远保持 API-free + 文件优先，复杂模型是 host 扩展

---

## 12. 参考

- 蓝本：`raw/2026/08/31/fun-rec/docs/_sources/`（chapter_1_retrieval / chapter_2_ranking / chapter_3_rerank / chapter_10_projects）
- OKS 现状：`cli/knowledge_studio/recall.py`（dispatch + 6+1）+ `assets/settings/recall.yaml`
- 蓝图：`docs/algorithms/agent-recall-architecture.md`（Phase 路线图 + 个人版/团队版）
- 设计约束：`CONSTITUTION.md` A1-A7 + P1（文件即DB）/ P4（API-free）/ P6（ships match docs）
- 多用户 1:1 映射：fun-rec `users`→OKS `profiles/agents/{id}/`；CF→协同召回；genres→area/type
