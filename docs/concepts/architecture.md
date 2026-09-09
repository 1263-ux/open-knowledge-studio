---
title: 架构总览
nav_order: 2
parent: 理解 OKS
---

# 架构总览

OKS 不是一个单独的“记忆插件”。它是一套让 **用户、Agent、文件化知识、收录能力和交付能力**各自做对的事的工作架构。

## OKS Mail 的产品定位

OKS Mail 是 OKS 的跨 Host 持久协作协议，不是 DSH 的附属功能，也不是
一个只能在面板里查看的知识桶。它把 Message、Thread、Agent 状态和
Session Receipt 保存在文件中，供不同 Agent 与 Session 继续同一项工作；
Mail 不因此变成 Wiki，也不承诺唤醒进程或保证任务执行。

### Agent-native 的两层使用模型

Mail 的底层协议面向 Agent，用户层面向任务意图。`@claude`、`@codex` 等是
内部稳定地址；普通用户不应被要求记住它们或手动维护 Thread/Session。

```text
普通用户：描述任务 → 选择/接受推荐 Agent → 查看结果
                         │
Host / Agent Adapter：自动创建 Thread、路由、呈现和回复
                         │
协议层：@agent-id + Message + Thread + Session Receipt
```

这不是两套 Mail，也不是 DSH 取代 Agent。Agent 是协作的主要操作者，DSH 是
人类观察与介入的工作面；`thread_id`、`session_id`、`ack` 和底层 `@` 地址
应在高级详情或 Agent CLI 中保留，而不是成为普通用户的日常心智负担。

```text
                         OKS Mail Protocol
                 ┌──────────────┼──────────────┐
                 ▼              ▼              ▼
          Claude Adapter   Codex Adapter   DSH Adapter
            Hook / CLI       Hook / CLI      RPC / UI
                 │              │              │
                 └──────────────┴──────────────┘
                                │
                        Future Host Adapters
                         Pi / Desktop / Web / TUI
```

Claude、Codex、DSH 以及未来的 Pi、桌面或 Web Host 都是同一 Mail Core 的
适配器。DSH 是当前的 Human/Work UI Adapter，负责把协议投影为可观察、可
操作的工作面；它通过 `oks mail` 访问 Core，Core 不依赖 DSH，也不要求
所有 Host 都有 UI。

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
- **协议细节不等于用户界面**：Mail Core 保留确定性的 Agent 路由键；Host 应将其封装为自然语言任务和友好 Agent 选择。
