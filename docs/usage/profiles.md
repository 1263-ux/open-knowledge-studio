---
title: Goal 与 Profile
nav_order: 6
parent: 指南
---

# Goal 与 Profile

知识越多，不代表 Agent 越懂你。Profile 说明稳定背景，Goal 说明当前方向；两者共同限制 Agent 应该关注什么。

## Profile 保存什么

- `profiles/team.md`：团队身份、职责和协作方式；
- `profiles/users/`：用户偏好与长期约束；
- `profiles/projects/`：项目背景和不随单次任务变化的事实；
- `profiles/recipes/`：重复工作的方法；
- `profiles/goals/`：当前目标和验收边界。
- `profiles/agents/<id>.md`：团队共享的 Agent 角色档案（职责、范围、输入输出约定）。
- `profiles/agents/registry.jsonl`：本机 Agent 与知识库的 binding/运行登记，不是团队成员名册，
  不应因为本机观察到 heartbeat 就改成“在线”。

不要把临时聊天、未经验证的推断或密钥放进 Profile。

## Goal 的作用

Goal 不是口号。Active Goal 会给匹配领域的 Wiki 页面增加召回相关性，但不会改变知识的审核状态。

一个有用的 Goal 至少包含：

```markdown
# 目标

要解决的问题：
完成标准：
范围内：
范围外：
必须由人类决定的动作：
```

## 团队初始化

把团队名称、知识库位置和负责人告诉 Agent，让它创建团队实例并展示团队资料与目标模板。团队成员确认之前，这些模板只是待填写结构，不能直接视为团队事实。

## 从 Mail 提交成员建档申请

Web 的「成员与来源」页可以填写负责 Agent、稳定 ID、显示名称、职责和工作范围，发送一条
`record_kind=handoff` 的建档申请。申请只是协作事实；负责 Agent 审核后再创建或更新
`profiles/agents/<id>.md`，随后通过同一 Thread 回复结果。这样成员档案进入 Git 共享的
知识库，机器本地的 binding 仍保持私有。
