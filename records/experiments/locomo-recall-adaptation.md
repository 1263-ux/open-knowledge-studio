# LoCoMo 召回适配方案 — 参考 OpenViking 评测数据集

> 状态：方案设计（数据集下载后可跑）。目的：用业界公开的 LoCoMo 长对话记忆数据集，给 OKS 召回一个跨项目可比的坐标。

## 背景：OpenViking 用 LoCoMo 评什么

OpenViking（volcengine/OpenViking）在 README `## Proof it works` 报告：

| 集成 | LoCoMo accuracy (native) | LoCoMo accuracy (with OpenViking) |
|------|--------------------------|-----------------------------------|
| OpenClaw | 24.20% | 82.08% |
| Hermes | 33.38% | 82.86% |
| Claude Code | 57.21% | 80.32% |

- tau2-bench task success：Retail 70.94%→77.81%（+6.87pp），Airline 54.38%→66.25%（+11.87pp）。
- 评测流程（`benchmark/locomo/openviking/`）：import 对话到 user space → 每 question 跑一次 retrieval → 可选 rerank → LLM answer → LLM judge → 统计 CSV。
- 数据集：`locomo10.json`，4 个类别（multi-hop / temporal / open-domain / single-hop，排除 adversarial）。

## OKS 能独立评什么

OKS 是召回引擎，不是 QA 引擎。OKS core API-free（CONSTITUTION P4），不在 core 调 LLM。所以：

- **能独立评**：召回命中——query = LoCoMo question，expected = 存该对话的 wiki 页 slug。这和 OKS 现有 `oks eval recall` 一致（query + expected slug）。
- **不能独立评**：QA accuracy（需要 LLM answer + LLM judge）——这步在 Agent host 做，不在 OKS core。

## 适配方案

### Step 1: 对话 → wiki

把 LoCoMo 的 10 段对话（`locomo10.json` 的 `sample_0`..`sample_9`，每段 4 session）存成 10 个 wiki 页：

```
wiki/conversations/locomo/
├── sample-0.md   # frontmatter: title/source/created; body = 对话全文
├── sample-1.md
└── ...
```

每段对话一个 wiki 页（一个 sample = 一个 user 的多 session 对话合集）。

### Step 2: question → eval dataset

把 `locomo_bad_case_questions.csv` 的 4 个类别问题转成 OKS eval YAML：

```yaml
# records/experiments/locomo-eval.yaml
- query: "What kind of painting did Caroline share with Melanie on October 13, 2023?"
  expected: ["sample-0"]          # 期望命中的对话 wiki slug
  topic_id: "locomo-multi-hop"     # category 作 topic
- query: "..."
  expected: ["sample-N"]
  ...
```

### Step 3: 跑召回对比

```bash
oks eval recall records/experiments/locomo-eval.yaml \
  --output records/experiments/runs/locomo-fts5.json \
  --search-backend fts5

oks eval recall records/experiments/locomo-eval.yaml \
  --output records/experiments/runs/locomo-native.json \
  --search-backend native
```

### Step 4: 和 OpenViking 对比

OKS 报 recall@k（召回命中），OpenViking 报 QA accuracy（answer 正确率）。两者不完全可比，但：

- **召回命中是 QA accuracy 的上界**——召回不到的对话，QA 一定答不对。
- 如果 OKS fts5 在 LoCoMo 上 recall@1 高，说明召回层强；QA accuracy 取决于 Agent host 的 answer 能力。
- 对比意义：**召回层** OKS fts5（Node-BM25，文件化）vs OpenViking retrieval（向量 + 目录递归）。

## 公平性说明

- OpenViking 的 LoCoMo 数字含 LLM answer + judge，OKS 的只到召回命中。**不是同一指标**，不直接比数字。
- OKS 的 50-case 是中文技术 wiki（术语重合高），LoCoMo 是英文长对话（同义词多）——**领域不同**，LoCoMo 更能体现 embedding 的价值（英文同义词鸿沟大）。
- 预期：LoCoMo 上 embedding backend 可能反超 fts5（英文同义词多，BM25 字面 miss 多）。这正好验证"embedding 的真正价值在大库 + 跨语言 + 同义词重"的判断。

## 下一步

1. 下载 `locomo10.json`（OpenViking README 指向 `./data/locomo10.json`，从 LoCoMo 原作者仓库取）。
2. 写转换脚本 `scripts/locomo_to_oks.py`（对话→wiki + question→eval yaml）。
3. 跑 `oks eval recall` 三 backend，归档 run JSON。
4. README 加 LoCoMo 对比节（召回层 OKS vs OpenViking retrieval）。

## 参考

- OpenViking benchmark：`benchmark/locomo/`（import / retrieval / judge 全流程）
- LoCoMo 原数据集：snap-research/locomo（长对话记忆评测）
- OKS eval：`oks eval recall <dataset.yaml> --output <run.json> --search-backend {fts5|native|fusion}`
