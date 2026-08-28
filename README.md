<div align="center">

<img src="docs/assets/oks-logo-readme.png" width="360" alt="Open Knowledge Studio">

# Open Knowledge Studio

把已经核实过的资料和判断，留给下一次任务。

[先看一个真实过程](https://open-agent-power.github.io/open-knowledge-studio/oh-my/study.html) · [开始使用](https://open-agent-power.github.io/open-knowledge-studio/start-here.html) · [完整文档](https://open-agent-power.github.io/open-knowledge-studio/)

</div>

每次换一个任务，都要重新解释项目背景、找回资料、提醒 Agent 哪些结论才可信——这很耗人。OKS 把来源、你的审核决定和可复用知识留在项目外部，让下一次任务从已经确认的上下文继续。

它不是模型训练，也不会把 Agent 看过的内容自动变成“团队共识”。材料先被保留，Agent 可以提出 Candidate，是否留下仍由人决定。

## 先看它怎么工作

不必先读一堆文档。这里有一个真实记录：两段 Kimi 视频被保存为来源和 Raw，Agent 据此提出待审核的知识 Candidate。

[看「托管你的学习」这个案例 →](https://open-agent-power.github.io/open-knowledge-studio/oh-my/study.html)

案例页面也会直接说明它**没有**证明什么：Candidate 尚未晋升为 Wiki，Kimi 的参数和能力结论仍需要官方资料或 benchmark 复核。这正是 OKS 想保留的边界。

## 想在自己的项目里试一次？

不需要打开终端或记命令。把下面这句话发给你正在使用的编码 Agent：

> 请按 [OKS 上游安装 Skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md) 为我安装 Open Knowledge Studio：把个人知识放进独立实例，不要写入源码仓库；完成后用自然语言告诉我实例位置、可用能力和所有未完成项。

安装后，先拿一份你熟悉的材料跑一遍：

1. 告诉 Agent 这份材料从哪里来，以及什么需要你亲自判断。
2. 让它展示 Candidate，逐条看来源支持了什么、还缺什么。
3. 换一个实际任务，确认它只使用已审核的内容，并能告诉你依据在哪里。

[第一次知识闭环的详细说明 →](https://open-agent-power.github.io/open-knowledge-studio/first-knowledge-loop.html)

## 接下来从哪儿走

- 要把文章、文件、视频或对话留下来，从 [收集来源](https://open-agent-power.github.io/open-knowledge-studio/usage/ingest.html) 开始。
- 要审 Agent 的提议，读 [审核候选](https://open-agent-power.github.io/open-knowledge-studio/usage/review.html)。
- 要在新任务里用回已经确认的经验，读 [召回与注入](https://open-agent-power.github.io/open-knowledge-studio/usage/recall.html)。
- 要把已审核的知识做成 Word、PDF、PPT 或 Excel，读 [Office 工作流](https://open-agent-power.github.io/open-knowledge-studio/usage/office.html)。

更多原理、故障排除和维护者资料在 [文档站](https://open-agent-power.github.io/open-knowledge-studio/)。如果你需要手动安装、CI 或 CLI，请从 [参考手册](docs/reference/cli.md) 进入。

## English

Open Knowledge Studio keeps sources, human review decisions, and reusable knowledge outside the model so a later task can start from confirmed context. See the [documented real-world example](https://open-agent-power.github.io/open-knowledge-studio/oh-my/study.html), then ask your coding Agent to follow the [OKS setup skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md).

## License

MIT
