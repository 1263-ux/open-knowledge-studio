# 示例 Goal：学透一本书的核心章节

> 这个文件的作用：告诉 OKS「我现在在学什么」。之后你问它问题，它会优先把和这个目标相关的知识找出来。

## ① 先看一个填好的例子

下面是一个已经填好的 Goal。照着它，你就知道每个字段是干嘛的了。

```markdown
---
title: 学透《深入理解 AI Agent》第 3 章
type: goal
owner: example          # 改成你的名字或昵称
period: ongoing         # 计划周期：ongoing（持续）/ 一个日期
status: active          # active 表示"正在学"
domains:
  - computing           # 知识域：computing / product / business...
keywords:
  - AI Agent
  - 记忆
  - 知识库
---

# 我的学习目标

读完这本书的第 3 章，能用自己的话讲清楚"AI Agent 的记忆和知识库是怎么设计的"。
```

**每个字段是什么意思：**

| 字段 | 作用 | 例子 |
|---|---|---|
| `title` | 这个目标的标题 | 学透《深入理解 AI Agent》第 3 章 |
| `type` | 固定写 `goal` | goal |
| `owner` | 这个目标属于谁 | example |
| `period` | 计划周期 | ongoing 或一个日期 |
| `status` | 是否在学 | active（在学）/ draft（草稿） |
| `domains` | 属于哪个知识域 | computing |
| `keywords` | 和这个目标相关的关键词 | AI Agent、记忆、知识库 |

> 关键词很重要：之后问 OKS 问题时，它靠这些词把相关目标下的知识优先找出来。

## ② 复制下面的空模板，改成你的

```markdown
---
title: （你想学什么）
type: goal
owner: （你的名字）
period: ongoing
status: active
domains:
  - （知识域）
keywords:
  - （关键词1）
  - （关键词2）
---

# 我的学习目标

（用一两句话说清楚：你想学会什么、能讲清楚什么。）
```

## ③ 这个 Goal 放哪

放到你的知识库的 `profiles/goals/` 目录下，文件名随意（建议用目标的关键词，比如 `learn-ai-agent.md`）。

## ④ 之后怎么用

学完写了几条笔记后，直接问 OKS：

> AI Agent 的记忆体系是怎么设计的？

它会优先把和这个目标相关的笔记找出来——这就是"目标让知识优先浮现"。
