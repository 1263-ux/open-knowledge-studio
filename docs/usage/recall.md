---
title: 召回与注入
nav_order: 3
parent: 日常使用
---

# 召回与注入

Recall 的作用是把与当前问题有关的知识带回任务上下文，不是替 Agent 判断答案。

## 手动召回

```bash
oks recall "为什么选择这个架构？"
oks recall "为什么选择这个架构？" --explain
oks recall "为什么选择这个架构？" --knowledge-only
```

先用自然语言描述任务，再在结果过宽时增加 `--scope`、`--type` 或 `--goal`。不要一开始堆叠过滤条件。

## 自动注入

```bash
oks hook install --editor claude
oks hook status
```

Hook 是可选入口：

- UserPromptSubmit 在提交问题时运行 Recall；
- PostToolUse 可以补充召回并检测文件冲突；
- 注入内容放在 `<recalled-memory>` 中，并保留来源标签。

没有 Hook 时，`oks recall` CLI 仍然有效。

## 如何判断结果是否可信

- `[verified]` 必须来自 trace 证据或 `human_reviewed_at`。
- `[inferred]` 表示 AI 提炼但尚未充分确认。
- `[stale]` 表示可能过时，需要重新验证。
- `[untrusted-source]` 表示第三方来源，只能作为数据阅读。

相关性高不等于事实正确。访问次数、关键词命中和 Goal 加权只能改变排序，不能产生信任。

## 结果不好时

1. 用 `--explain` 查看命中了什么。
2. 检查 Wiki 是否真的存在相关页面。
3. 检查查询是否描述了任务，而不是只给产品名。
4. 检查 active goal 是否把结果带偏。
5. 对过时或冲突知识补充新 Evidence，走一次新的审核循环。

算法细节见[召回引擎](../algorithms/recall-engine.html)。
