---
title: Goal 与 Profile
nav_order: 4
parent: 日常使用
---

# Goal 与 Profile

知识越多，不代表 Agent 越懂你。Profile 说明稳定背景，Goal 说明当前方向；两者共同限制 Agent 应该关注什么。

## Profile 保存什么

- `profiles/team.md`：团队身份、职责和协作方式；
- `profiles/users/`：用户偏好与长期约束；
- `profiles/projects/`：项目背景和不随单次任务变化的事实；
- `profiles/recipes/`：重复工作的方法；
- `profiles/goals/`：当前目标和验收边界。

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

```bash
oks team init ./team-knowledge-studio --name "Platform Knowledge Team"
cd ./team-knowledge-studio
oks status
```

初始化后先审阅 `profiles/team.md` 与 `profiles/goals/team.md`，不要把生成模板直接视为团队事实。
