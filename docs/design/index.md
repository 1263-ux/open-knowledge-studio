---
title: 设计蓝图
nav_order: 6
parent: 概念
has_children: true
---

# 设计蓝图

这一组是 OKS 召回与部署形态的演进设计文档：它们描述"下一步往哪走"，不是当前已交付的行为。当前已实现的行为以[召回引擎](../algorithms/recall-engine.html)和 [CLI 参考](../reference/cli.html)为准。

- [召回系统蓝图](../algorithms/agent-recall-architecture.html)：把推荐系统工程架构一比一迁移到"面向 Agent 的文档召回"的生产级路线图。
- [召回复杂版设计](../algorithms/agent-recsys-design.html)：在 Triple-Layer 三层不变的前提下，把每层规模放大的完整设计。
- [Team 大型版设计](../architecture/team-recsys-cv.html)：OKS CLI 本地 + 远程推荐系统服务的团队大型版形态。
- [规模光谱](../architecture/scale-spectrum.html)：同一三层架构在 mini → cluster 的连续缩放变形。

{: .note }
> 蓝图中的 Phase 与指标是设计目标，尚未全部落地。引用时请区分"已实现"与"设计中"。
