---
title: 召回引擎
nav_order: 1
parent: 算法
---
# 召回引擎（6+1 因子评分）

`oks recall` 是唯一召回入口。默认合并 Raw episodic 与 Wiki knowledge；`--knowledge-only` 只查 Wiki。`raw/executions/` 和 `raw/.logs/` 是 provenance，不参与召回。

## 难题背景

知识库随时间增长，`wiki/` 累积成百上千页。用户或 Agent 提一个 query，如何找到最相关知识并排序？

两条路：

- **语义召回**（embedding 相似度）——效果好，但 CLI 核心不调 AI API（P4），本地跑 embedding 模型成本高。
- **关键词召回**（字面匹配）——轻量，但跨表述召回差（搜"design patterns"命中不了只写"architectural approaches"的页）。

OKS 选了第二条，但用多因子评分把"关键词匹配"做到比纯计数更聪明：融合词项、子串、话题关联、知识类型、失败教训、记忆曲线、目标加成——7 个信号一次评分。

## 技术设计

双路召回：

| 路径 | 来源 | 评分 |
|------|------|------|
| Episodic | `raw/` + `profiles/` | 关键词 + 新鲜度（`0.95^days_old`） |
| Knowledge | `wiki/` | 6+1 因子相关性 + 记忆曲线 |

评分公式：

```
base  = token_overlap_count × 0.3 + substring_bonus + topic_trace_bonus
total = base × type_boost
        + review_bonus
        + memory_score × 0.5
        + goal_boost      # 可选第 7 因子，无 active goal 时为 0
```

`base == 0` 直接出局；review 与 memory 是**加法项不是乘数**——没有字面命中的页靠记忆热度上不来。

## 原理（七因子）

1. **词项重叠 ×0.3** — jieba 分词，统计 query token 在标题+正文+标签的命中数。词项层，逐 token 字面。当前是无权计数：无 IDF（罕见词与常见词等权）、无长度归一化（长页天然多命中）——已知简化，需标注数据集才能量化改进。
2. **子串匹配 +1.0/+0.5** — 标题含 query 串 +1.0，正文含 +0.5，可叠加（都含 +1.5）。关键词层，精确短语。
3. **话题关联 +2.0** — 页面带 discuss trace 且 topic_id 匹配查询的 topic_id，+2.0。图谱层，把 memory 关联回产生它的对话。
4. **类型乘数 ×1.5/×0.8/×0.6** — anti-pattern ×1.5（错误最该召回，防重蹈覆辙）、strategy ×0.8、concept ×0.6。乘法因子。
5. **失败加成 +2.0/+1.0** — `decision_correct=false` +2.0，`outcome=failure` +1.0。反直觉但合理：最有价值的知识常是"我们试了 X 没用"。
6. **记忆曲线 ×0.5** — 页面 memory_score（[衰减系统](decay-system.md) 算）×0.5 加法进入。Active ×1.2，archived=0。
7. **目标加成 +0.8/+0.4（可选）** — 页面 `area` ∈ active goal 的 `domains` +0.8，命中 goal keyword +0.4。只作用于 `relevance>0` 的页（不凭空顶无关页上来）。

## 指标

当前无标注数据集做召回率/精确率量化（已知阻塞）。能给的"指标"是可解释输出——`oks recall "<q>" --explain` 给每个 hit 的逐项分数 + reasons + goal_matches + rank。

总分可由下面字段精确重建：

```
final_score = typed_base
            + review_decision
            + review_failure
            + memory_score
            + goal_area
            + goal_keyword
```

JSON 响应版本 `recall-response/v1`，单条 `recall-hit/v1`。

## 实验

`oks eval recall <dataset.yaml> --output <run.json>` 支持离线评测——但需要标注数据集（query + 期望命中页）。现状无官方数据集，社区可自建。

- `--goal none` — 无偏基线
- `--goal <slug>` — 固定单一 goal，可复现实验
- `--goal active` — 默认，合并全部 active goal，适合交互使用

## 结论

6+1 是无 embedding 下的折中方案，适合本地小到中知识库（百到千页）。优点：轻量、可解释、不调 AI、类型/失败/目标感知。局限：无语义召回（跨表述差）、无 IDF/长度归一化。语义召回需 embedding（大改，需模型+索引+标注量化），暂不做。

召回是只读：查询不算使用，不推 `access_count`。`oks wiki use <slug>` 才 +1 驱动记忆曲线——记忆热度反映"真被用上"而非"被搜过几次"。
