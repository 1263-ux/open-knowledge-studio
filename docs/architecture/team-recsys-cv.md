# Team 大型版 — fun-rec 架构 1:1 CV 设计

> 把 fun-rec 生产级推荐系统**架构原样复制**到 OKS，作为 team 大型版（cluster 规模）的在线服务。
> **唯一映射**：电影 → 文档（wiki + raw）。其余架构（pipeline / recall / ranking / reranking / cold_start / offline / storage）1:1 CV，不改动。
>
> 这是给实现者的**代码蓝图**——具体到目录/文件/接口。概念设计见 `agent-recsys-design.md` + `scale-spectrum.md`。

---

## 0. 映射原则：电影 → 文档，别的都不变

| fun-rec 概念 | OKS team 版映射 | 说明 |
|-------------|----------------|------|
| movie（电影） | doc（wiki 页 + raw episodic） | 被推荐的对象 |
| user（用户） | Agent（pi/qoder/codex/...） | 推荐的消费者 |
| rating（评分） | inject（召回）+ wiki use（显式使用） | 正反馈信号 |
| genres（类型） | area / type / topic | 文档类目 |
| preferred_genres | Agent scope / preferred_area | 偏好域 |
| users 表 | `profiles/agents/{id}/` | Agent 画像 |
| movies 表 | `wiki/` + `raw/` | 文档本体（P1 文件即 DB） |
| ratings 表 | `records/inject.jsonl` | 反馈日志 |
| 用户行为序列 | Agent inject slug 序列 | 时序召回源 |

**唯一不变量**：电影→文档这一个映射。其余架构（目录划分、接口设计、流水线步骤、单例服务、策略模式）**1:1 CV**。

---

## 1. 概念纠正（OKS 这边不对的，1:1 CV 时纠正）

> 1:1 CV fun-rec 时，发现 OKS 现有概念有两处和 fun-rec 不一致，需纠正：

### 1.1 A8 三层 vs fun-rec 三阶段 — 正交，不冲突

| | OKS A8 三层 | fun-rec 三阶段 |
|---|---|---|
| 性质 | 架构分层（召回/注入/衰减） | 在线流水线步骤（召回/排序/重排） |
| 召回 | 召回层（Node-BM25 + 多路 backend） | 召回阶段（多通道候选） |
| 排序 | **注入层**（Soul Boost） | 排序阶段（DeepFM） |
| 重排 | **注入层**（MMR/dispersion） | 重排阶段（dispersion 打散） |
| 衰减 | 衰减层（Memory Curve，独有） | **无**（电影不过期，知识会过时） |

**纠正**：1:1 CV 后，fun-rec 的"排序+重排"都落在 OKS 的**注入层**（A8 不变）。OKS team 大型版 = fun-rec 在线流水线（3 步）+ OKS 衰减层（1 步）= **4 阶段流水线**，但 A8 三层架构不变（注入层含排序+重排）。**不是四层**——衰减是独立后台，不在在线流水线串联里。

### 1.2 "6+1 因子"概念纠正

之前混淆：把 6+1 当排序。**纠正**：
- 6+1 是 `native` backend 的**召回算分**（v0.6.0 前默认，向后兼容）
- 当前默认召回是 `fts5`（Node-BM25）
- **排序是注入层 Soul Boost**（`_injection_boost`），不是 6+1
- 1:1 CV 后，排序层 = Soul Boost（= fun-rec DeepFM 的 P4 退化版）

---

## 2. 代码结构 1:1 CV

> fun-rec `web_project/backend/` → OKS `cli/knowledge_studio/team/`，1:1 目录映射。

```
cli/knowledge_studio/team/              # team 大型版 (1:1 CV fun-rec web_project/backend)
├── online/                               # 在线服务 (1:1 CV fun-rec online/)
│   ├── pipeline.py                       # 在线流水线 (冷启动检测→召回→排序→重排)
│   ├── recall/                           # 召回层 (1:1 CV fun-rec recall/)
│   │   ├── base.py                       #   RecallStrategy 抽象基类
│   │   ├── node_bm25.py                  #   Node-BM25 召回 (OKS 默认, = fts5 backend)
│   │   ├── item_based.py                #   ItemCF 召回 (doc 共现, 团队核心增量)
│   │   ├── trending.py                  #   热门召回 (hot tier + high importance)
│   │   ├── youtubednn.py                #   双塔召回 (Agent-doc, P4 退化=embedding connector)
│   │   ├── resource_manager.py          #   资源管理 (索引/共现矩阵加载)
│   │   └── service.py                   #   RecallService (单例, 多路协调 + Snake Merge)
│   ├── ranking/                          # 排序层 (1:1 CV fun-rec ranking/)
│   │   ├── base.py                       #   RankingStrategy 抽象
│   │   ├── soul_boost.py                 #   Soul Boost (OKS 注入层, = DeepFM P4 退化)
│   │   ├── resource_manager.py           #   模型资源 (P4: 无模型, 参数即权重)
│   │   └── service.py                   #   RankingService (单例, 模型不可用→fallback 召回分)
│   ├── reranking/                        # 重排层 (1:1 CV fun-rec reranking/)
│   │   ├── base.py                       #   RerankingStrategy 抽象
│   │   ├── dispersion.py                 #   连续打散 (area/type, max_consecutive)
│   │   └── service.py                   #   RerankingService
│   └── cold_start/                        # 冷启动 (1:1 CV fun-rec cold_start/)
│       ├── base.py                       #   ColdStartStrategy 抽象
│       ├── detector.py                   #   冷启动检测 (inject 次数 < N)
│       ├── popular.py                   #   热门兜底 (hot tier + high importance)
│       ├── preferred_area.py             #   偏好域 (Agent scope/preferred_area)
│       ├── ucb_topic.py                  #   UCB topic 探索 (多臂老虎子)
│       └── service.py                   #   ColdStartService (UCB→preferred→popular 优先级)
├── offline/                               # 离线生产 (1:1 CV fun-rec offline/)
│   ├── pipeline.py                       # 离线流水线 (--steps all/preprocess/train/ingest/deploy)
│   ├── config.py                         # 配置
│   ├── feature/                           # 特征工程 (1:1 CV fun-rec feature/)
│   │   ├── preprocess_retrieval.py       #   召回特征 (Agent-doc 矩阵 from inject.jsonl)
│   │   └── preprocess_ranking.py         #   排序特征 (injection_boost 特征提取)
│   ├── training/                          # 模型训练 (P4: 统计退化, 不训模型)
│   │   ├── train_retrieval.py            #   召回"训练" (共现矩阵统计, Word2Vec 远期)
│   │   └── train_ranking.py              #   排序"训练" (Soul Boost 权重调参 via oks eval)
│   └── storage/                           # 存储部署 (1:1 CV fun-rec storage/)
│       ├── local_deploy.py              #   派生部署 (.oks/ 写入: fts5.db + 共现矩阵)
│       └── redis_ingest.py              #   特征上线 (Agent 画像 + 共现 → .oks/ 缓存)
└── app/                                   # Web 服务层 (可选, P4 外, cluster 远程模式)
    ├── api/v1/endpoints/recommendations.py  # 推荐 API (远程模式入口)
    ├── services/fts5_service.py             # ES→FTS5 (1:1 CV elasticsearch_service)
    └── models.py                            # ORM→文件即 DB (1:1 CV, 但 P1 文件优先)
```

**1:1 CV 的"1"**：目录划分、文件命名、接口模式（策略模式 + 单例 service + resource_manager）、流水线步骤。**不 CV 的**：模型训练（P4 退化）、存储后端（PG/Redis/ES → 文件 + FTS5 + .oks/ 派生）。

---

## 3. 在线流水线 1:1 CV

> 1:1 CV fun-rec `online/pipeline.py` 的 `RecommendationService.recommend`。

```python
# team/online/pipeline.py — 1:1 CV fun-rec, 电影→文档
class TeamRecallPipeline:
    """Agent 知识推荐在线流水线 (1:1 CV fun-rec online/pipeline.py)

    1. 冷启动检测: inject 次数 < N 的 Agent → 冷启动路径
    2. 召回: 多通道候选检索 (Node-BM25 + ItemCF + 热门, 100-200 候选)
    3. 精排: Soul Boost 排序 (前 20-30)
    4. 重排: dispersion 打散 (area/type, max_consecutive)
    """

    async def recommend(self, agent_id, query, item_features_provider):
        # 1. 冷启动检测 (1:1 CV cold_start/detector)
        if self.cold_start_detector.is_cold(agent_id):  # inject < threshold
            return await self.cold_start_service.recommend(agent_id, ...)

        # 2. 召回 (1:1 CV recall/service, 多路 + Snake Merge)
        candidates = await self.recall_service.recall(agent_id, query, top_k=100)
        # 多路: Node-BM25 (fts5) + ItemCF (共现) + 热门 (hot tier)

        # 3. 精排 (1:1 CV ranking/service, Soul Boost = DeepFM 退化)
        ranked = await self.ranking_service.rank(candidates, agent_id, query, top_k=20)
        # Soul Boost: type×1.5/0.8/0.6 + review×1.2 + generic×0.5 + goal reorder + memory curve
        # P4: 不调 DeepFM 模型, 用启发式 boost; 模型不可用→fallback 召回分 (1:1 CV fallback 逻辑)

        # 4. 重排 (1:1 CV reranking/service, dispersion 打散)
        reranked = await self.reranking_service.rerank(ranked, max_consecutive=3)
        # 连续打散: 同 area/type 不超 max_consecutive 个连续

        return RecommendationResult(items=reranked, ...)
```

**数据流**（1:1 CV fun-rec）：
```
agent query → [cold_start 检测]
  ├─ 冷启动 → UCB topic 探索 / preferred_area / 热门兜底
  └─ 正常 → [recall 多路 100-200] → Snake Merge
              → [ranking Soul Boost 20-30] → [reranking dispersion 打散]
              → 注入 Agent 上下文
```

---

## 4. 离线流水线 1:1 CV

> 1:1 CV fun-rec `offline/pipeline.py`，`--steps all/preprocess/train/ingest/deploy`。

```bash
# team/offline/pipeline.py — 1:1 CV fun-rec offline steps (Phase T6 设想命令, 未实现)
team offline --steps all                          # 全流程
team offline --steps preprocess                   # 特征工程
team offline --steps train                        # "模型训练" (P4 退化)
team offline --steps ingest                        # 特征上线
team offline --steps deploy                        # 派生部署
```

**步骤 1:1 CV**：
1. `preprocess_retrieval` — 召回特征：从 `records/inject.jsonl` 聚合 Agent-doc 矩阵（1:1 CV fun-rec 从 ratings 提特征）
2. `preprocess_ranking` — 排序特征：提取 injection_boost 特征（type/review/generic/goal/memory）
3. `train_retrieval` — 召回"训练"：**P4 退化**——统计共现矩阵（ItemCF），不训 YoutubeDNN；Word2Vec 远期 connector
4. `train_ranking` — 排序"训练"：**P4 退化**——Soul Boost 权重调参（via `oks eval`，不训 DeepFM）
5. `ingest` — 特征上线：Agent 画像 + 共现矩阵 → `.oks/` 派生缓存（1:1 CV fun-rec 写 Redis）
6. `deploy` — 派生部署：FTS5 索引 + 共现矩阵 + 画像 → `.oks/` 写入（1:1 CV fun-rec 写共享目录）

---

## 5. 存储映射 1:1 CV

> fun-rec 四件套 → OKS 文件优先（P1）+ .oks 派生。

| fun-rec 存储 | OKS team 版 | 内容 | 1:1 CV 程度 |
|-------------|-------------|------|------------|
| PostgreSQL（users/movies/ratings） | 文件即 DB（profiles/agents/ + wiki/ + records/inject.jsonl） | 业务数据本体 | P1 不变，git migration |
| Redis（user profile/history） | `.oks/agent_profiles/{id}.jsonl` | 画像 + 行为序列缓存 | 1:1 CV 角色，文件实现 |
| Redis（item embedding index） | `.oks/doc_vectors.pkl`（可选，embedding 慢默认关） | 文档向量索引 | 1:1 CV 角色，默认关 |
| Elasticsearch（movies 搜索） | `.oks/fts5.db`（FTS5 倒排） | 全文搜索 | 1:1 CV 角色，FTS5 实现 |
| 共享目录（model files） | `settings/recall.yaml`（参数，P4 无模型） | "模型"= 参数 | 1:1 CV 角色，参数代模型 |

**1:1 CV 的"不 CV"**：存储后端不 CV（PG/Redis/ES → 文件 + FTS5 + .oks），因为 P1（文件即 DB）+ P4（API-free）是 OKS 红线。

---

## 6. P4 退化（1:1 CV 但不训模型）

> fun-rec 训模型（DeepFM/YoutubeDNN），OKS P4 不训。1:1 CV 架构，但训练步骤退化。

| fun-rec 模型 | OKS team 版 | 退化方式 |
|-------------|-------------|---------|
| YoutubeDNN（召回双塔） | `youtubednn.py` → embedding connector | 不训双塔，用 BGE 预训练（connector 扩展，慢默认关） |
| DeepFM（精排） | `soul_boost.py` | 不训 DeepFM，用启发式 boost（type/review/generic/goal/memory），= DeepFM 小数据退化 |
| Word2Vec（I2I doc 向量） | `train_retrieval.py` 远期 | 不训（P4），远期 connector 扩展 |
| ALS（协同矩阵分解） | `train_retrieval.py` 统计退化 | 不训 ALS，直接统计共现（ItemCF），大群体远期上 ALS |

**退化原则**：架构 1:1 CV（目录/接口/流水线），模型训练退化（统计/启发式/connector）。**core 永远不训模型**（P4），复杂模型是 connector 扩展。

---

## 7. 冷启动 1:1 CV

> 1:1 CV fun-rec `online/cold_start/`，电影→文档。

| fun-rec 冷启动 | OKS team 版 | 实现 |
|---------------|-------------|------|
| `detector.py`（交互 < N） | `detector.py`（inject 次数 < N） | 从 inject.jsonl 统计 |
| `ucb_genre.py`（UCB 类型探索） | `ucb_topic.py`（UCB topic 探索） | 多臂老虎子，遍历 topic 域学偏好 |
| `preferred_genre.py`（偏好类型） | `preferred_area.py`（偏好域） | Agent scope/preferred_area |
| `popular.py`（热门兜底） | `popular.py`（热门兜底） | hot tier + high importance |

**优先级 1:1 CV**：UCB topic → preferred_area → popular（fun-rec: UCB → preferred → popular）。

---

## 8. 和现有三份文档的关系

| 文档 | 角色 |
|------|------|
| `CONSTITUTION.md` A8 | 三层架构不变量（召回/注入/衰减解耦） |
| `agent-recall-architecture.md` | 蓝图 + Phase 路线图（Part A 三阶段漏斗 + Part B 个人/团队） |
| `agent-recsys-design.md` | 召回算法复杂版（多路召回 = 召回层 backend 扩展，不增层） |
| `scale-spectrum.md` | 规模光谱（三层在 mini→cluster 的部署变形，层数永远三） |
| **本文（team-recsys-cv.md）** | **1:1 CV 代码蓝图**（fun-rec 架构原样搬，电影→文档，给实现者） |

**本文是代码实现蓝图**——前三份是概念设计，本文具体到目录/文件/接口，是 Phase 3+ 实现的起点。

---

## 9. 路线图（1:1 CV 实现 Phase）

| Phase | 内容 | 1:1 CV 来源 | 优先 |
|-------|------|------------|------|
| **T1** | `team/online/recall/` 骨架（base + node_bm25 + service 单例） | fun-rec recall/ | 🔴 |
| **T2** | `team/online/ranking/soul_boost.py`（= 现有 _injection_boost 重构） | fun-rec ranking/ | 🔴 |
| **T3** | `team/online/reranking/dispersion.py`（area/type 打散） | fun-rec reranking/ | 🟡 |
| **T4** | `team/online/pipeline.py`（串联 4 阶段） | fun-rec online/pipeline.py | 🟡 |
| **T5** | `team/online/cold_start/`（detector + ucb_topic + popular） | fun-rec cold_start/ | 🟡 |
| **T6** | `team/offline/`（preprocess + train 退化 + ingest + deploy） | fun-rec offline/ | 🟡 |
| **T7** | `team/online/recall/item_based.py`（ItemCF，团队协同核心） | fun-rec item_based | 🟡 |
| **T8** | `team/app/`（Web 服务，cluster 远程模式，P4 外） | fun-rec app/ | 🟪 |
| **T9** | youtubednn/embedding connector（远期） | fun-rec youtubednn | ⚪ |

**执行顺序**：T1-T2（召回+排序骨架，复用现有 fts5 + _injection_boost）→ T3-T4（重排+流水线串联）→ T5-T6（冷启动+离线）→ T7（ItemCF 协同核心）→ T8（远程模式）。

---

## 10. 参考

- 蓝本代码：`raw/2026/08/31/fun-rec/web_project/backend/`（online/ + offline/ + app/）
- 架构文档：`raw/2026/08/31/fun-rec/docs/_sources/chapter_10_projects/`（architecture/offline/online）
- 宪法：`CONSTITUTION.md` A8（三层不变量）+ P1（文件即DB）+ P4（API-free）
- 概念设计：`docs/algorithms/agent-recsys-design.md` + `docs/architecture/scale-spectrum.md`
- 现有实现：`recall.py::dispatch`（召回层）/ `recall.py::_injection_boost`（注入层，= T2 重构基础）/ `store.py::apply_decay`（衰减层）
