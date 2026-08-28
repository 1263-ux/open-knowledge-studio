<div align="center">

<img src="docs/assets/oks-logo-readme.png" width="360" alt="Open Knowledge Studio">

# Open Knowledge Studio

### 让 Agent 记住团队已经确认的判断

保存来源、人工审核和可复用知识，让下一次任务直接沿用已经确认的经验，而不是重新解释背景。

[开始使用](https://open-agent-power.github.io/open-knowledge-studio/start-here.html) · [真实案例](https://open-agent-power.github.io/open-knowledge-studio/oh-my/) · [Office 工作流](https://open-agent-power.github.io/open-knowledge-studio/usage/office.html) · [完整文档](https://open-agent-power.github.io/open-knowledge-studio/)

</div>

## OKS 是什么

OKS 是面向 Agent 的可审核外部知识库。Agent 可以收集材料、提出知识候选并在后续任务中召回；人负责判断哪些内容可信、值得长期保留，以及哪些结论还不能下。

它不训练模型权重，也不会把“收集到的资料”自动写成团队知识。

## 安装：只要交给 Agent 一句话

不需要打开终端或记住命令。把下面这句话交给你正在使用的编码 Agent：

> 请按 [OKS 上游安装 Skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md) 为我安装 Open Knowledge Studio：把个人知识放进独立实例，不要写入源码仓库；完成后用自然语言告诉我实例位置、可用能力和所有未完成项。

Agent 会检查环境、创建独立实例，并如实报告失败或限制。团队使用时，再补充团队名称和成员必须确认的边界。

## 第一次使用，只跑一条小闭环

1. 给 Agent 一份真实材料，并说明什么证据可信、什么必须由你决定。
2. 审核它提出的 Candidate：来源支持什么、还缺什么、是否值得复用。
3. 换一个任务，确认 Agent 只使用已审核知识，并能说清它从哪里来。

[查看第一次知识闭环 →](https://open-agent-power.github.io/open-knowledge-studio/first-knowledge-loop.html)

## 你会得到什么

- **有来源**：原始材料和机械提取结果可以回到具体来源。
- **有人审**：Agent 可以提出 Candidate，但不能自行批准它成为长期知识。
- **可复用**：后续任务召回已审核知识，同时说明证据缺口和可能过时的部分。

## 常见任务

| 你想做什么 | 从哪里开始 |
| --- | --- |
| 把文章、文件、视频或对话变成可追溯材料 | [收集来源](https://open-agent-power.github.io/open-knowledge-studio/usage/ingest.html) |
| 审核 Agent 的知识提议 | [审核候选](https://open-agent-power.github.io/open-knowledge-studio/usage/review.html) |
| 让新任务使用已确认的经验 | [召回与注入](https://open-agent-power.github.io/open-knowledge-studio/usage/recall.html) |
| 从已审核知识交付 Word、PDF、PPT 或 Excel | [Office 工作流](https://open-agent-power.github.io/open-knowledge-studio/usage/office.html) |
| 看完整的人机边界与结果 | [真实案例](https://open-agent-power.github.io/open-knowledge-studio/oh-my/) |

## OKS 不会替你越过的边界

- 保存来源不等于证实其中的主张。
- Agent 的总结不会自动成为长期知识。
- 证据不足时，正确结果是说明缺口，而不是补出确定答案。
- 发布、合并、删除和外部发送等高风险动作仍需要人的明确授权。

## 想深入时

- [理解 OKS](https://open-agent-power.github.io/open-knowledge-studio/concepts/)
- [参考手册与故障排除](https://open-agent-power.github.io/open-knowledge-studio/reference/)
- [维护者文档](https://open-agent-power.github.io/open-knowledge-studio/maintainers/)
- [手动安装、CI 与 CLI](docs/reference/cli.md)

## English

Open Knowledge Studio is a reviewable external knowledge base for Agents. It preserves sources, human review decisions, and reusable knowledge so later work can build on confirmed context rather than start from scratch.

Give your coding Agent this request instead of following terminal commands:

> Follow the [OKS setup skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md) to install Open Knowledge Studio for me: create a separate knowledge-base instance, never write my personal knowledge into the source repository, then report the instance location, available capabilities, and every incomplete step in plain language.

Start with [one useful learning loop](https://open-agent-power.github.io/open-knowledge-studio/first-knowledge-loop.html), then explore the [documentation](https://open-agent-power.github.io/open-knowledge-studio/).

## License

MIT
