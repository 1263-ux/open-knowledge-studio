---
title: 第一次学习循环
nav_order: 2
parent: 从这里开始
---

# 第一次学习循环

目标不是“导入很多资料”，而是验证一条知识能否沿着完整路径流动：

```text
Source → Evidence / Raw → Candidate → Human Review → Wiki → Recall
```

## 准备一条真实判断

在知识库外准备一个文本文件，例如 `first-source.md`：

```markdown
# 项目知识审核原则

所有准备长期复用的项目知识，在进入 Wiki 前必须人工审核。
原因是未经核验的错误会被后续任务反复召回，扩大影响范围。
```

使用你自己的真实材料更好，但第一次请保持内容短小、来源明确。

## 1. 让 Agent 收录来源

在支持 Skill 的 Agent 中说：

```text
请使用 /ingest 收录 first-source.md。保留来源，不要直接写入 Wiki；
完成后告诉我 Raw Bundle、Candidate 和仍需人工判断的内容。
```

Agent 会调用 OKS 的摄入能力，保存 Evidence 和 Raw Bundle，并提出 Candidate。文本来源的机械步骤也可以用下面的命令检查：

```bash
oks ingest prepare first-source.md
oks status
oks drafts list
```

成功信号：能定位来源和 Raw Bundle，并且新内容仍停留在 `drafts/`，没有自动进入 `wiki/`。

## 2. 人工审核 Candidate

先读内容，不要只看标题：

```bash
oks drafts list
oks drafts get <slug>
```

检查：

- 是否忠实表达来源；
- 是否把来源主张误写成事实；
- 是否保留来源路径；
- 是否与已有知识重复、补充或冲突；
- 是否值得长期召回。

确认后再执行：

```bash
oks drafts promote <slug>
```

不接受时使用 `/promote` Skill 走拒绝流程并填写理由。拒绝同样是一条有价值的人类反馈。

## 3. 在新问题中召回

```bash
oks recall "为什么知识进入 Wiki 前需要审核？" --explain
```

成功信号：结果命中刚审核的 Wiki 页面，并能解释来源和相关性。安装了 Hook 后，也可以在新会话直接提问，检查 `<recalled-memory>` 是否出现。

## 验收清单

- [ ] 原始来源可以定位。
- [ ] Candidate 没有绕过人工审核。
- [ ] Promote 后存在 `human_reviewed_at`。
- [ ] Recall 命中的是审核后的知识，而不是把 Raw 当作已验证结论。
- [ ] 召回结果不足时，Agent 会说明缺口而不是补写事实。

## 下一步

- [确认 OKS 正在工作](verify.html)
- [审核 Candidate](usage/review.html)
- [理解 Recall 与上下文注入](usage/recall.html)
- [查看 Oh My Study](oh-my/study.html)
