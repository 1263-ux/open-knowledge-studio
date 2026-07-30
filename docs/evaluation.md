---
title: Recall Evaluation
nav_order: 24
parent: 参考
---

# Recall Evaluation

`oks eval` 在本地、离线、只读地评测召回质量，不调用模型 API。

```bash
oks eval recall eval/datasets/team-v1.yaml --output eval/runs/baseline.json
oks eval recall eval/datasets/team-v1.yaml --output eval/runs/candidate.json
oks eval compare eval/runs/baseline.json eval/runs/candidate.json --output eval/runs/comparison.json
```

数据集遵循 `_meta/recall-case.schema.json`。每条 case 固定 query、goal 模式、可选 scope/type、相关 slug 与禁止召回 slug。`eval/datasets/recall-v1.example.yaml` 只是格式示例，不能当作正式真值集。

运行结果包含 Recall@1/3/5、MRR、nDCG@5、无结果率、陈旧知识泄漏率、P50/P95 延迟，以及代码 commit、数据集 SHA-256 和评测前后知识库快照。快照不一致时命令直接失败。

正式报告必须使用人工复核的数据集；不同数据集哈希的两次运行禁止比较。
