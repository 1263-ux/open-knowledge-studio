---
title: 架构总览
nav_order: 2
parent: 理解 OKS
---

# 架构总览

OKS 不是一个单独的“记忆插件”。它是一套让 **用户、Agent、文件化知识、收录能力和交付能力**各自做对的事的工作架构。

<picture>
  <source media="(max-width: 50rem)" srcset="../assets/architecture/oks-overview-mobile.svg">
  <img src="../assets/architecture/oks-overview.svg" alt="OKS 完整架构：用户和 Agent 在上方发起任务；profiles、raw、drafts、wiki、mail 构成文件化知识工作区；右侧是 API-free CLI、能力目录、安全契约与 Office 交付；人审门控制 Candidate 进入 Wiki，召回将资料带回下一次任务。">
</picture>

## 怎样读这张图

先看上方：用户提出任务、提供来源、设定目标，并决定审核与交付；Agent 是编排器，它调用能力、解释依据、提出 Candidate，但不拥有最终决定权。

中间左侧是实例里的五个桶：

- `profiles/` 放稳定的用户、项目、Recipe 和 Goal；
- `raw/` 放原始来源与机械提取结果；
- `drafts/` 放 Agent 的 Candidate；
- `wiki/` 只放人审后的可复用知识；
- `mail/` 与 Trace 留下协作和执行证据，但不冒充长期知识。

右侧是运行时：`oks` CLI 负责文件操作、召回和状态，不在核心中调用模型 API；Agent 根据 Recipe、Provider 和 Capability 选择网页、PDF、Office、图片、音视频等处理能力。明确要交付文件时，Office 工作流才会接手 Word、PDF、PPT 或 Excel。飞书的 Base、表单与 IM 审核则是一个**可选参考实现**：它可以承担采集和移动审核入口，但不属于 CLI 核心，也不会绕开人审门。

最后回到上方：新任务由 `profiles/`、已审核 `wiki/` 和必要的 `raw/` 召回支持。相关性只能影响排序，不能把材料升级为事实。

## 需要深入时

这张图把系统层级和实际能力放在一起，但没有展开协议字段与评分公式。需要进一步实现或排障时：

- 想收集不同类型的材料，阅读[收集来源](../usage/ingest.html)。
- 想理解审核和晋升，阅读[审核候选](../usage/review.html)。
- 想了解召回如何选择知识，阅读[召回与注入](../usage/recall.html)。
- 维护者需要完整文件桶、只读 VFS、Hooks 与可选飞书集成时，阅读[宪法（A1-A5）](constitution.html)和[参考手册](../reference/)。

## 架构边界

- **Raw 不等于 Wiki**：Raw 保留材料和机械提取；Wiki 是经人审核、能在后续任务中复用的知识。
- **VFS 不是新知识桶**：`oks://` 只提供受限的只读访问视图，不会绕开文件治理。
- **Hooks 和飞书是可选入口**：它们可以改变收集或反馈的位置，但不会取消人工审核。
- **信任来自证据和审核**：`[verified]` 只应来自 Trace 证据或 `human_reviewed_at`，而不是使用次数。
