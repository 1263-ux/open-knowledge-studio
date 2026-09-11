---
title: 记忆模型
nav_order: 3
parent: 概念
---

# 记忆模型：六类记忆与注入次序

OKS 把"Agent 该记住什么"拆成六类记忆，各自有独立的存储位置、召回方式、作用域和衰减策略。这一页是[宪法 A2](constitution.html) 的用户版摘要。

## 六类记忆

| 类型 | 存储位置 | 召回方式 | 衰减 | 作用域 |
|---|---|---|---|---|
| 用户记忆 | `profiles/users/{id}.md` | 直接读取 | 无 | `user_id` |
| 项目记忆 | `profiles/projects/{slug}.md` | 直接读取 | 无 | `project_slug` |
| 情景记忆 | `raw/{YYYY}/{MM}/{DD}/{source}/` | 关键词 + 新鲜度 | 无 | 来源、日期 |
| 语义记忆 | `wiki/{domain}/{type}/{slug}.md` | Triple-Layer Recall | 类型化 λ | 领域 |
| 程序记忆 | `.claude/skills/{slug}/` | 关键词触发 | 无 | — |
| 草稿记忆 | `drafts/{slug}.md` | 不召回（待人审） | 无 | — |

两类容易误读的地方：

- `mail/` 是协调与评审证据，**不是记忆类型**；它不参与召回，也不衰减。
- `raw/executions/` 是 provenance（执行轨迹），被召回显式排除，只能通过证据链接到达。

## 语义记忆的三层处理

`wiki/` 页面的召回走 Triple-Layer（[召回引擎](../algorithms/recall-engine.html)）：

1. **Node-BM25（检索层）**：SQLite FTS5 按 `##` 标题节点索引，决定"哪些页命中"。
2. **Soul Boost（注入层）**：type boost、review bonus、generic demotion 决定"哪些命中真正到达 Agent"——失败教训排在泛化概念前面。
3. **Memory Curve（衰减层）**：`importance × e^(-λ×days) + ln(1+access)` 决定"多旧的知识还值得出现"。

关键设计约束：**使用次数只是排序输入**。一个页面被召回很多次说明它常被需要，但不能由此提高它的置信度或状态——那是 P9 不变量。

## 注入次序与来源标签

注入上下文时按"稳定优先"排列以保护 KV Cache：profiles → 已审核 wiki → 必要的 raw 摘录 → mail 未读。每段注入都带来源标签（哪个文件、是否人审），Agent 引用时能说出依据在哪。

## 目标如何影响召回

`profiles/goals/` 中的活跃 Goal 会给匹配其领域/关键词的 wiki 页一个相关性加成（`--goal` 可显式指定或关闭）。没有 Goal 时该项是无操作——不会引入别的偏差。

## 延伸

- 目录即信任边界：[文件即记忆](file-system-paradigm.html)
- 完整不变量文本：仓库根目录 [CONSTITUTION.md](https://github.com/1263-ux/open-knowledge-studio/blob/main/CONSTITUTION.md)
