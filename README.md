<div align="center">

<img src="docs/assets/oks-logo-readme.png" width="360" alt="Open Knowledge Studio">

# Open Knowledge Studio

把已经核实过的资料和判断，留给下一次任务。

[先看一个真实过程](https://1263-ux.github.io/open-knowledge-studio/oh-my/study.html) · [开始使用](https://1263-ux.github.io/open-knowledge-studio/start-here.html) · [完整文档](https://1263-ux.github.io/open-knowledge-studio/)

</div>

每次换一个任务，都要重新解释项目背景、找回资料、提醒 Agent 哪些结论才可信——这很耗人。OKS 把来源、你的审核决定和可复用知识留在项目外部，让下一次任务从已经确认的上下文继续。

它不是模型训练，也不会把 Agent 看过的内容自动变成“团队共识”。材料先被保留，Agent 可以提出 Candidate，是否留下仍由人决定。

## OKS Mail：跨 Session 的持续通信层

OKS Mail 是 Git-backed、独立于宿主的持久通信层：Human 和 Agent 可以在同一
个 durable Thread 中跨 Session、Agent、Host 和机器继续消息、回复、Receipt
事实和成果引用。Thread 是有主题边界的通信上下文，不是任务、工作流或执行状态。

Claude、Codex、DSH 以及未来的 Pi、桌面或 Web Host 都可以通过各自的 Adapter
使用同一份 Thread、Message 和 Session Receipt。DSH 只是当前的 Human/Work UI
Adapter；它调用 `oks mail` 提供可视化和人工操作，Mail Core 不依赖 DSH，也不把
通信消息混入 Wiki 或 Recall。

其中 `oks` CLI 是 Agent-native 的核心入口；Host 只是适配器。Agent 交接任务
优先使用 `oks mail delegate`，由 CLI 自动构造 handoff Thread；普通用户则由
当前 Agent 在后台调用它，不需要学习 `@agent-id`。

普通用户不需要学习 `thread_id` 或 `ack`。当前 DSH P0 仍要求选择收件 Agent，
但它默认把 Session、机器和协议 ID 收在来源详情中；用户应感受到的是同一段对话
可以继续，而不是一次次独立执行。自然语言路由和命名 Human 身份仍是后续需要单独
设计的能力。

## 先看它怎么工作

不必先读一堆文档。这里有一个真实记录：两段 Kimi 视频被保存为来源和 Raw，Agent 据此提出待审核的知识 Candidate。

[看「托管你的研究」这个案例 →](https://1263-ux.github.io/open-knowledge-studio/oh-my/study.html)

案例页面也会直接说明它**没有**证明什么：Candidate 尚未晋升为 Wiki，Kimi 的参数和能力结论仍需要官方资料或 benchmark 复核。这正是 OKS 想保留的边界。

## 想在自己的项目里试一次？

不需要打开终端或记命令。把下面这句话发给你正在使用的编码 Agent：

> 请按 [OKS 上游安装 Skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md) 为我安装 Open Knowledge Studio：把个人知识放进独立实例，不要写入源码仓库；完成后用自然语言告诉我实例位置、可用能力和所有未完成项。

安装后，先拿一份你熟悉的材料跑一遍：

1. 告诉 Agent 这份材料从哪里来，以及什么需要你亲自判断。
2. 让它展示 Candidate，逐条看来源支持了什么、还缺什么。
3. 换一个实际任务，确认它只使用已审核的内容，并能告诉你依据在哪里。

[第一次知识闭环的详细说明 →](https://1263-ux.github.io/open-knowledge-studio/first-knowledge-loop.html)

## 接下来从哪儿走

- 要把文章、文件、视频或对话留下来，从 [收集来源](https://1263-ux.github.io/open-knowledge-studio/usage/ingest.html) 开始。
- 要审 Agent 的提议，读 [审核候选](https://1263-ux.github.io/open-knowledge-studio/usage/review.html)。
- 要在新任务里用回已经确认的经验，读 [召回与注入](https://1263-ux.github.io/open-knowledge-studio/usage/recall.html)。
- 要把已审核的知识做成 Word、PDF、PPT 或 Excel，读 [Office 工作流](https://1263-ux.github.io/open-knowledge-studio/usage/office.html)。

更多原理、故障排除和维护者资料在 [文档站](https://1263-ux.github.io/open-knowledge-studio/)。如果你需要手动安装、CI 或 CLI，请从 [参考手册](docs/reference/cli.md) 进入。

## English

Open Knowledge Studio keeps sources, human review decisions, and reusable knowledge outside the model so a later task can start from confirmed context. See the [documented real-world example](https://1263-ux.github.io/open-knowledge-studio/oh-my/study.html), then ask your coding Agent to follow the [OKS setup skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md).

## License

MIT
