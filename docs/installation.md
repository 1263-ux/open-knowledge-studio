---
title: 从零上手
nav_order: 1
parent: 开始使用
---

# 从零上手

OKS 是 Agent 的知识工作空间，不应该先变成用户需要背诵的一组命令。把安装任务直接交给你正在使用的编码 Agent：

> 请按 [OKS 上游安装 Skill](https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md) 为我安装 Open Knowledge Studio：把个人知识放进独立实例，不要写入源码仓库；完成后用自然语言告诉我实例位置、可用能力和所有未完成项。

## Agent 应该完成什么

1. 检查本机环境是否满足当前版本要求。
2. 安装或更新 OKS，并创建独立知识库实例。
3. 确认 Agent 能找到这个实例，而不是误用源码仓库。
4. 检查收集、候选审核和召回能力是否可用。
5. 把失败、缺失和降级状态如实告诉你。

如果是团队使用，再补充团队名称、成员边界和负责人。Agent 可以创建团队资料模板，但模板内容必须由团队成员确认后才能视为事实。

## 安装完成后你应该看到什么

Agent 的报告至少应包括：

- 知识库实例保存在哪里；
- 当前是否存在待审核知识；
- 哪些来源类型可以处理，哪些能力尚未安装；
- 自动召回是否启用；
- 下一步如何完成第一条知识闭环。

需要手工安装、CI 配置或排错时，再查看[命令参考](reference/cli.html)和[故障排除](reference/troubleshooting.html)。普通使用不从命令行开始。

下一步：[完成第一次学习循环](first-knowledge-loop.html)。
