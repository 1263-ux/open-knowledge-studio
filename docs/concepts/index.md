---
title: 概念
nav_order: 5
has_children: true
---

# 概念

这些页面解释 OKS 为什么这样工作。你不需要先读懂它们才能完成第一次学习循环。

## 概念

- [知识即模型](philosophy.html)：人类反馈如何塑造 Agent 使用的外部心智模型。
- [架构总览](architecture.html)：摄入、文件桶、Recall、只读 VFS 与可选集成的关系。
- [文件即记忆](file-system-paradigm.html)：为什么是可审核的文件系统，而不是黑盒向量库。
- [记忆模型](memory-model.html)：六类记忆的存储、召回、作用域与衰减。

## 算法引擎（已实现行为）

- [召回引擎](../algorithms/recall-engine.html)：Triple-Layer Recall 的分层结构与默认后端。
- [衰减系统](../algorithms/decay-system.html)：记忆曲线、类型化 λ 与 tier 分类。
- [召回评估](../algorithms/recall-evaluation.html)：评估方法论与历史基准。

## 设计蓝图（演进方向）

- [召回系统蓝图](../algorithms/agent-recall-architecture.html)、[召回复杂版设计](../algorithms/agent-recsys-design.html)、[Team 大型版设计](../architecture/team-recsys-cv.html)、[规模光谱](../architecture/scale-spectrum.html)：描述"下一步往哪走"，以[设计蓝图](../design/)为入口。

命令参数和协议字段属于[参考手册](../reference/)，文档写作契约与宪法属于[维护者](../maintainers/)。
