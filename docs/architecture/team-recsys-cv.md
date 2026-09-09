# Team 大型版 — fun-rec 架构 1:1 CV 设计（两部分 + 工业栈）

> OKS team 大型版 = **OKS CLI 本地**（不变，加 remote backend connector）+ **远程推荐系统服务**（独立部署，1:1 CV fun-rec，含 ES/PG/Redis 工业栈）。
> **本质不变**：CLI 本地 → hook → recall dispatch → backend（本地 fts5 或 remote 调远程）→ 注入。远程服务是召回层的一个 backend 选项，A8 三层不破。

---

## 0. 核心洞察：Hook 本质是召回，backend 可远程

OKS 的 `user-prompt-recall` hook 本质是**知识的 search**——触发 `oks recall`，就是召回。
召回层 backend 可插拔（`entry_points(group="oks_search_backend")`，已有 fts5/native/embedding connector）。
**加一个 `remote` backend**：调远程推荐系统服务 API。远程服务 = fun-rec 那套（online pipeline + ES/PG/Redis 工业栈）。

**本质没变**：CLI 本地触发 → recall dispatch → backend（本地 or 远程）→ 返回候选 → 注入层本地 Soul Boost → 注入。复杂召回在远程，注入在本地，A8 三层不变。

---

## 1. 两部分架构

### Part 1: OKS CLI 本地（不变，加 remote backend）

```
cli/knowledge_studio/                # OKS CLI (本地, P4 不破)
├── search/
│   ├── __init__.py                   # get_backend() + entry_points connector 扩展点
│   ├── fts5.py                       # Node-BM25 (本地默认)
│   ├── native.py                     # 6+1 (向后兼容)
│   ├── fusion.py                     # 实验
│   └── remote.py                     # ★新增: remote backend connector (调远程推荐系统 API)
├── recall.py                          # dispatch (三层 A8: 召回层 + 注入层 Soul Boost)
└── store.py                           # 衰减层 Memory Curve (本地)
```

**remote backend**（`search/remote.py`，~100 行）：
```python
class RemoteBackend:
    """Remote search backend — 调远程推荐系统服务 (fun-rec 1:1 CV).
    和 embedding connector 同构, 走 entry_points(group="oks_search_backend").
    config: search_backend: remote
            remote_url: http://recsys-service:8000
    """
    def search(self, query, agent_id, limit, scope, **kw) -> list[SearchHit]:
        # POST remote_url/recommendations {agent_id, query, limit, scope}
        # 返回 SearchHit[] (slug/title/score/abstract/backend="remote")
        ...
```

**OKS CLI 侧改动极小**——只加 `search/remote.py` + `recall.yaml` 配 `search_backend: remote` + `remote_url`。注入层 Soul Boost + 衰减层 Memory Curve 仍在本地（不远程化）。

### Part 2: 远程推荐系统服务（独立部署，1:1 CV fun-rec，工业栈）

```
oks-recsys-service/                   # 独立项目 (1:1 CV fun-rec web_project/backend)
├── online/                            # 在线服务 (1:1 CV fun-rec online/)
│   ├── pipeline.py                    #   在线流水线 (冷启动→召回→排序→重排)
│   ├── recall/                        #   base + node_bm25 + item_based + trending + youtubednn + service
│   ├── ranking/                        #   base + deepfm + resource_manager + service
│   ├── reranking/                     #   base + dispersion + service
│   └── cold_start/                   #   base + detector + popular + preferred_area + ucb_topic + service
├── offline/                           # 离线生产 (1:1 CV fun-rec offline/)
│   ├── pipeline.py                    #   --steps all/preprocess/train/ingest/deploy
│   ├── feature/                       #   preprocess_retrieval + preprocess_ranking
│   ├── training/                      #   train_retrieval + train_ranking
│   └── storage/                       #   local_deploy + redis_ingest
├── app/                               # Web 服务层 (1:1 CV fun-rec app/)
│   ├── api/v1/endpoints/recommendations.py  #   POST /recommendations (OKS remote backend 调这个)
│   ├── services/elasticsearch_service.py    #   ES 服务 (工业界需要)
│   ├── models.py                      #   ORM (agents/docs/inject)
│   └── database.py                    #   PG 连接
└── docker-compose.yml                 # PG + Redis + ES + 服务 (工业栈一键起)
```

**1:1 CV 程度**：online/ + offline/ + app/ 目录、接口、策略模式、流水线步骤**原样 CV**。存储栈**全要**（工业界标配）。

---

## 2. 映射原则：电影 → 文档，别的都不变

| fun-rec 概念 | 远程服务映射 | 说明 |
|-------------|-------------|------|
| movie（电影） | doc（wiki 页 + raw episodic） | 被推荐的对象 |
| user（用户） | Agent（pi/qoder/codex/...） | 推荐的消费者 |
| rating（评分） | inject（召回）+ wiki use（显式使用） | 正反馈信号 |
| genres（类型） | area / type / topic | 文档类目 |
| preferred_genres | Agent scope / preferred_area | 偏好域 |
| users 表（PG） | `profiles/agents/{id}/` + PG agents 表 | Agent 画像（文件 + DB 双写） |
| movies 表（PG） | `wiki/` + `raw/` + PG docs 表 | 文档本体（P1 文件 + DB 索引） |
| ratings 表（PG） | `records/inject.jsonl` + PG inject 表 | 反馈日志（文件 + DB 双写） |

**唯一不变量**：电影→文档这一个映射。其余架构（pipeline/recall/ranking/reranking/cold_start/offline/storage/app）1:1 CV。

---

## 3. 存储栈：工业界标配全要（1:1 CV fun-rec）

> 用户明确：ES/PG/Redis 都要，工业界需要。全在远程服务侧，OKS CLI 侧不碰（P4/P1）。

| fun-rec 存储 | 远程服务实现 | 内容 | 工业界角色 |
|-------------|-------------|------|-----------|
| **PostgreSQL** | PG（agents/docs/inject 表） | 业务库：Agent 画像 + 文档元数据 + inject 日志 | 持久化业务数据 |
| **Redis** | Redis（agent profile + inject 序列 + item 向量索引） | 特征缓存：在线推理实时特征 | 低延迟特征读取 |
| **Elasticsearch** | ES（docs 倒排索引：title/area/tags/body） | 全文搜索：文档检索（工业界标配） | 倒排索引 + 分词 + 高级查询 |
| **共享目录** | 共享卷（model files: 召回/排序模型 + 向量矩阵） | 模型存储：离线产出，在线加载 | 模型版本管理 |

**和 OKS 本地的关系**：
- OKS CLI 本地仍用 `.oks/fts5.db`（FTS5，mini/standard 够）
- 远程服务用 ES（cluster 规模，工业界需要）——**两者并存**，`search_backend` 配置切换
- P1（文件即 DB）在 CLI 本地不破；远程服务侧是独立工业栈（PG/Redis/ES），不违反 P1（P1 管 OKS core，不管外部服务）

---

## 4. 在线流水线 1:1 CV（远程服务侧）

> 1:1 CV fun-rec `online/pipeline.py`。OKS CLI 的 remote backend 调这个。

```python
# oks-recsys-service/online/pipeline.py — 1:1 CV fun-rec
class RecommendationService:
    """Agent 知识推荐在线流水线 (1:1 CV fun-rec online/pipeline.py)

    1. 冷启动检测: inject 次数 < N 的 Agent → 冷启动路径
    2. 召回: 多通道候选 (Node-BM25 + ItemCF + 热门, 100-200)
    3. 精排: DeepFM CTR 预估 (前 20-30)
    4. 重排: dispersion 打散 (area/type, max_consecutive)
    """

    async def recommend(self, agent_id, query, item_features_provider):
        # 1. 冷启动 (1:1 CV cold_start/detector)
        if self.cold_start_detector.is_cold(agent_id):
            return await self.cold_start_service.recommend(agent_id, ...)

        # 2. 召回 (1:1 CV recall/service, 多路 + Snake Merge)
        candidates = await self.recall_service.recall(agent_id, query, top_k=100)

        # 3. 精排 (1:1 CV ranking/service, DeepFM — 远程服务可训模型, 不受 P4)
        ranked = await self.ranking_service.rank(candidates, agent_id, query, top_k=20)

        # 4. 重排 (1:1 CV reranking/service, dispersion 打散)
        reranked = await self.reranking_service.rerank(ranked, max_consecutive=3)

        return RecommendationResult(items=reranked, ...)
```

**关键差异（远程服务 vs OKS CLI）**：
- 远程服务**可训模型**（DeepFM/YoutubeDNN）——不受 P4（P4 管 OKS core，不管外部服务）
- OKS CLI 注入层仍用 Soul Boost（启发式，P4 合规）——远程返回候选，本地注入

**数据流**：
```
OKS CLI hook → oks recall → remote backend
  → POST remote_url/recommendations {agent_id, query}
  → 远程服务: 冷启动检测→召回多路→DeepFM 精排→dispersion 重排
  → 返回 SearchHit[] (slug/title/score/abstract)
→ OKS CLI 注入层 Soul Boost (本地, goal reorder + memory curve)
→ 注入会话
```

---

## 5. 离线流水线 1:1 CV（远程服务侧）

> 1:1 CV fun-rec `offline/pipeline.py`，`--steps all/preprocess/train/ingest/deploy`。

```bash
# oks-recsys-service/offline/pipeline.py — 1:1 CV fun-rec (设想命令, Phase T6)
offline --steps all                          # 全流程
offline --steps preprocess                   # 特征工程 (从 PG inject 表 + ES docs 提特征)
offline --steps train                        # 模型训练 (DeepFM + YoutubeDNN, 远程服务可训)
offline --steps ingest                        # 特征上线 (写 Redis: agent profile + inject 序列)
offline --steps deploy                        # 模型部署 (写共享卷: model files + 向量矩阵)
```

**步骤 1:1 CV**：
1. `preprocess_retrieval` — 召回特征：从 PG inject 表聚合 Agent-doc 矩阵
2. `preprocess_ranking` — 排序特征：提取 DeepFM 特征（Agent 画像 + doc 元数据 + 行为序列）
3. `train_retrieval` — 召回训练：**训 YoutubeDNN**（远程服务可训，不 P4）
4. `train_ranking` — 排序训练：**训 DeepFM**（远程服务可训）
5. `ingest` — 特征上线：Agent 画像 + 行为序列 → Redis
6. `deploy` — 模型部署：model files + 向量矩阵 → 共享卷

---

## 6. 冷启动 1:1 CV（远程服务侧）

| fun-rec 冷启动 | 远程服务 | 实现 |
|---------------|---------|------|
| `detector.py`（交互 < N） | `detector.py`（inject < N） | 从 PG inject 表统计 |
| `ucb_genre.py`（UCB 类型探索） | `ucb_topic.py`（UCB topic 探索） | 多臂老虎子 |
| `preferred_genre.py`（偏好类型） | `preferred_area.py`（偏好域） | Agent scope |
| `popular.py`（热门兜底） | `popular.py`（热门兜底） | hot tier + high importance |

**优先级 1:1 CV**：UCB topic → preferred_area → popular。

---

## 7. 概念纠正（1:1 CV 时纠正 OKS 这边的）

### 7.1 A8 三层 vs fun-rec 三阶段 — 正交，不冲突

- OKS A8 三层（召回/注入/衰减）是**架构分层**
- fun-rec 三阶段（召回/排序/重排）是**在线流水线步骤**
- 1:1 CV 后：远程服务跑 fun-rec 三阶段（召回→排序→重排），OKS CLI 仍三层（召回层=remote backend 调远程 / 注入层 Soul Boost 本地 / 衰减层 Memory Curve 本地）
- **本质不变**：远程服务的排序+重排 = OKS 召回层 backend 内部的事；OKS 注入层仍本地 Soul Boost

### 7.2 "6+1 因子"纠正

- 6+1 是 `native` backend 召回算分（v0.6.0 前默认，向后兼容）
- 当前默认召回是 `fts5`（Node-BM25）
- 排序是注入层 Soul Boost（不是 6+1）
- team 大型版：CLI 本地排序仍 Soul Boost（P4）；远程服务排序 DeepFM（可训，不 P4）

### 7.3 P4 边界（关键）

- **OKS CLI core**（`oks recall`）永远 API-free（P4）——remote backend 是 connector 扩展，调远程 API，不破 P4
- **远程推荐系统服务**不是 OKS core——独立项目，可训模型（DeepFM/YoutubeDNN）、用 ES/PG/Redis 工业栈，不受 P4
- P4 管 OKS core，不管外部 connector 和远程服务

---

## 8. 代码归属（两部分清晰）

| 归属 | 代码 | 角色 |
|------|------|------|
| **OKS CLI 本地**（进 `cli/knowledge_studio/`） | `search/remote.py`（~100 行 connector） | remote backend，调远程 API |
| **OKS CLI 本地**（已有，不改） | `recall.py`（dispatch + Soul Boost）/ `store.py`（Memory Curve）/ `search/fts5.py` | 本地三层（A8） |
| **远程推荐系统服务**（独立项目 `oks-recsys-service/`） | `online/` + `offline/` + `app/`（1:1 CV fun-rec） | 完整推荐系统 + 工业栈 |
| **部署**（远程服务侧） | `docker-compose.yml`（PG + Redis + ES + 服务） | 工业栈一键起 |

**OKS CLI 改动极小**（+1 个 remote backend connector），远程服务是独立完整项目。

---

## 9. 路线图（1:1 CV 实现 Phase）

| Phase | 归属 | 内容 | 1:1 CV | 优先 |
|-------|------|------|--------|------|
| **T1** | OKS CLI | `search/remote.py` backend connector + `recall.yaml` 配 remote | 新增（非 CV） | 🔴 |
| **T2** | 远程服务 | `online/recall/` 骨架（base + node_bm25 + service 单例） | fun-rec recall/ | 🔴 |
| **T3** | 远程服务 | `online/ranking/deepfm.py` + service | fun-rec ranking/ | 🟡 |
| **T4** | 远程服务 | `online/reranking/dispersion.py` + service | fun-rec reranking/ | 🟡 |
| **T5** | 远程服务 | `online/pipeline.py` 串联 + `app/api/recommendations.py` | fun-rec pipeline + app | 🟡 |
| **T6** | 远程服务 | `online/cold_start/`（detector + ucb_topic + popular） | fun-rec cold_start/ | 🟡 |
| **T7** | 远程服务 | `offline/`（preprocess + train + ingest + deploy） | fun-rec offline/ | 🟡 |
| **T8** | 远程服务 | `docker-compose.yml`（PG + Redis + ES 工业栈） | fun-rec 存储 | 🟡 |
| **T9** | 远程服务 | `online/recall/item_based.py`（ItemCF 协同核心） | fun-rec item_based | 🟡 |
| **T10** | 远程服务 | youtubednn/embedding（远期） | fun-rec youtubednn | ⚪ |

**执行顺序**：T1（OKS remote backend，打通接入）→ T2-T5（远程服务在线流水线骨架）→ T6-T8（冷启动 + 离线 + 工业栈）→ T9（ItemCF 协同核心）。

---

## 10. 和现有文档的关系

| 文档 | 角色 |
|------|------|
| `CONSTITUTION.md` A8 | 三层架构不变量（OKS CLI 侧不破） |
| `agent-recall-architecture.md` | 蓝图 + Phase 路线图 |
| `agent-recsys-design.md` | 召回算法复杂版（多路 backend 扩展） |
| `scale-spectrum.md` | 规模光谱（mini→cluster 三层部署变形） |
| **本文（team-recsys-cv.md）** | **两部分 1:1 CV 蓝图**（OKS remote backend + 远程服务独立部署 + 工业栈） |

---

## 11. 参考

- 蓝本代码：`raw/2026/08/31/fun-rec/web_project/backend/`（online/ + offline/ + app/ + ES/PG/Redis）
- 架构文档：`raw/2026/08/31/fun-rec/docs/_sources/chapter_10_projects/`
- 宪法：`CONSTITUTION.md` A8（三层不变量）+ P1（文件即DB, CLI 侧）+ P4（API-free, CLI core）
- OKS connector 机制：`cli/knowledge_studio/search/__init__.py`（`entry_points(group="oks_search_backend")`，remote backend 同构 embedding connector）
