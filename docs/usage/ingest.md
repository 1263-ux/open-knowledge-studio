---
title: 收集来源
nav_order: 1
parent: 日常使用
---

# 收集来源

收集的目标是保存可以复核的 Evidence，而不是让 AI 尽快写出答案。

## 推荐入口

对支持 Skill 的 Agent 说：

```text
请使用 /ingest 收录这个来源。先 recall 同主题知识，保留原始证据，
告诉我使用了哪些 Provider、缺少什么，以及 Candidate 在哪里。
```

Agent 会按当前环境选择最小充分能力集。需要检查底层状态时使用：

```bash
oks capability status --json
oks ingest prepare <source>
oks raw-commit <manifest-dir>
```

不要手写 SourceEnvelope、EvidenceFragment 或 EvidenceManifest；确定性字段应由 CLI 生成。

## 状态必须保持原样

| 状态 | 含义 | 后续动作 |
|---|---|---|
| `complete` | Recipe 的完成条件由合法 Evidence 满足 | 可以提出 Candidate |
| `partial` | 保存了部分证据，但仍有关键缺口 | 把缺口写进 Candidate，谨慎继续 |
| `failed` | 执行失败，没有形成可用结果 | 保留错误，修复来源或能力 |
| `skipped` | 该步骤未执行 | 不得改写成成功 |

可选能力失败不一定阻塞；关键条件缺失时不能把结果包装成 complete。

## 证据边界

- Provider 原始输出先保存，再进行 Agent 解释。
- 机械提取和 Agent 观察使用不同 provenance 标签。
- ASR、OCR、字幕和网页作者主张都可能有错。
- Raw 可以帮助追溯，但不会因为被读取而变成已验证知识。
- 涉及远程处理时遵守 SourceEnvelope 的数据处理策略。

协议对象与 Provider 细节见[摄入协议](../reference/ingest.html)。
