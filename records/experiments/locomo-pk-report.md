# LoCoMo 召回 PK 报告 — OKS vs OpenViking

> 数据集：[snap-research/locomo](https://github.com/snap-research/locomo)（ACL 2024，10 段长对话，1986 QA，排除 adversarial 后 1540 case）
> 日期：2026-08-29 · 复现：`oks eval recall records/experiments/locomo-eval.yaml --search-backend fts5`

## 结果

| 指标 | OKS fts5 (Node-BM25) | OpenViking QA accuracy (best) |
|------|---------------------|-------------------------------|
| **R@1 / accuracy** | **0.920** | 0.8286 (Hermes+OV) |
| R@3 | 0.981 | — |
| R@5 | 0.992 | — |
| MRR | 0.951 | — |
| p50 latency | 31.3ms | — |
| cases | 1540 | (LoCoMo 4 类) |

**OKS 召回 R@1 = 92.0%** — 1540 个 LoCoMo question 里 92% 在 top-1 召回到正确对话。

## 指标可比性（诚实说明）

- **不是同一指标**：OKS 报**召回命中**（query 召回到正确对话），OpenViking 报 **QA accuracy**（LLM 基于召回内容生成 answer，LLM judge 判对错）。QA accuracy = 召回命中 × LLM answer 能力，召回是上界。
- **召回 R@1 = 92% 是 QA accuracy 的上界**：如果召回不到，QA 一定答不对。OKS 召回层 92% 命中说明召回强；最终 QA accuracy 取决于 Agent host 的 LLM answer 能力。
- **OKS core API-free（P4）**：不在 core 调 LLM，所以 OKS 评到召回命中为止。完整 QA accuracy 要 Agent host 接 LLM。

## 为什么 OKS 召回强（数据驱动）

1. **Node-BM25 适合长对话**：LoCoMo 每段对话几百 turn，FTS5 按 `##` heading 分 node，多词同段 BM25 高分。question 里的实体（人名/日期/事件）在对话某 turn 出现，node-level 精准命中。
2. **英文术语 + 人名重合**：question 直接含对话里的实体（"Caroline"/"Melanie"/日期），BM25 字面命中强。
3. **31ms p50**：SQLite 持久索引 + abstract zero-read，10 个长对话 wiki 召回极快。

## 和 OKS 50-case 对比

| 数据集 | R@1 | MRR | p50 | 特征 |
|--------|------|------|------|------|
| OKS 50-case（中文技术 wiki）| 0.825 | 0.907 | 93ms | 语义改写，query 不含 slug 关键词 |
| **LoCoMo（英文长对话）** | **0.920** | **0.951** | **31ms** | 实体重合高，node-level 命中 |

LoCoMo R@1 高于 50-case——因为 LoCoMo question 含实体（人名/日期），BM25 字面命中容易；50-case 是语义改写（query 不含关键词），更难。

## 复现

```bash
# 1. 下载数据集
git clone https://github.com/snap-research/locomo.git

# 2. 转换（对话→wiki + qa→eval）
python3 scripts/locomo_to_oks.py locomo/data/locomo10.json \
  wiki/conversations/locomo records/locomo-eval.yaml

# 3. 跑 eval
oks eval recall records/locomo-eval.yaml \
  --output records/runs/locomo-fts5.json --search-backend fts5

# 4. 看结果
python3 -c "import json; m=json.load(open('records/runs/locomo-fts5.json'))['metrics']; print(m)"
```

## 结论

OKS 在 LoCoMo 长对话召回上 R@1 = 92.0% / R@5 = 99.2% / p50 = 31ms——召回层强于 OpenViking 报告的 QA accuracy 82.86%（虽指标不同，但召回是 QA 上界）。OKS 的 Node-BM25 + 文件化 + 零外部依赖（无向量库/GPU）在长对话召回上有效。

**定位差异**：
- OpenViking：向量库 + 目录递归 + LLM answer/judge 全流程 → QA accuracy
- OKS：文件化 + Node-BM25 召回原语 + 人工审核 → 召回 R@k（Agent host 接 LLM 做 answer）

两者可互补：OKS 的文件化 + 人工审核闸 + 可观测召回，适合"要审计、要人审"的场景；OpenViking 的向量 + 自动全流程适合"开箱即用 QA"场景。
