---
title: 文件即记忆
nav_order: 5
parent: 工作原理
---

# 文件即记忆：文件系统范式

OKS 不把知识放进一个黑盒向量库，而是把记忆做成**人可读、git 可版本化、Agent 可确定性定位的文件系统**。这是 OKS 一切行为的前提：检索可解释、审核有落点、迁移靠 git。

## 为什么是文件，不是黑盒

- **可审核**。每一次知识晋升（Candidate → Wiki）都对应一个人类可以打开阅读的 diff。审核的对象不是一条Embedding，而是一页带来源的 Markdown。
- **可解释**。`oks recall "<q>" --explain` 能指出每个候选为什么入选（哪个节点、哪个因子得分）。向量库给不了这个。
- **可迁移**。"Git IS the migration"——没有数据库、没有 schema 迁移脚本；目录结构的变化通过 `_meta/` 的版本化 schema 约束。
- **对 Agent 友好**。Agent 本来就会用 `ls`、`cat`、`grep` 思考。`oks fs tree`、`oks wiki list` 把这套本能变成受治理的访问，而不是让 Agent 猜目录。

## 信任边界：不同目录不同待遇

| 目录 | 谁写入 | 信任含义 |
|---|---|---|
| `raw/` | 人收集或工具机械提取 | 原始证据，**不是结论** |
| `drafts/` | Agent 提议 | 待审候选，**不是知识** |
| `wiki/` | 人审批准后生效 | 长期记忆，可衰减、可追溯 |
| `mail/` | Agent 与人协作产生 | 协调证据，**不是可召回知识** |
| `profiles/` | 人维护 | 稳定上下文，直接读取 |
| `settings/`、`_meta/` | 配置与 schema | 基础设施，不是记忆 |

这条边界是 OKS 的核心纪律：**一个 Agent 可以写出 Candidate，但不能批准自己的 Candidate**。使用次数只能证明"常被需要"，不能证明"正确"（见[知识即模型](philosophy.html)与[宪法](constitution.html)）。

## 与向量库路线的分工

OKS 的默认检索是 SQLite FTS5 上的 Node-BM25（见[召回引擎](../algorithms/recall-engine.html)）——零外部依赖、毫秒级、可解释。Embedding 是 fts5 未命中时的**后备**，不是替代：在实体型查询上，字面命中比语义泛化更精确。这也让 OKS 核心保持 API-free：不依赖向量库服务、Embedding 模型或 GPU。

## 延伸

- 目录结构与记忆生命周期：[宪法 A1](constitution.html)
- 六类记忆分别存在哪：[记忆模型](memory-model.html)
- Agent 如何只读浏览这套文件：`oks fs` 命令，[CLI 参考](../reference/cli.html)
