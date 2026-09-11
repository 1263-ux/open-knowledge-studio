---
title: 算法引擎
nav_order: 5
parent: 概念
grand_parent: 概念
has_children: true
---

# 算法引擎

这一组解释 OKS 当前已实现的召回三层（Node-BM25 检索 / Soul Boost 注入 / Memory Curve 衰减）的行为与依据。

- [召回引擎](recall-engine.html)：Triple-Layer Recall 的分层结构与默认后端。
- [衰减系统](decay-system.html)：记忆曲线、类型化 λ 与 tier 分类。
- [召回评估](recall-evaluation.html)：评估方法论、消融实验与历史基准。

设计中的演进（多路召回、团队大型版、规模缩放）见[设计蓝图](../design/index.html)。
