---
title: 托管你的移动审核
nav_order: 3
parent: 真实案例
---

# 托管你的移动审核

{: .warning }
> **类型：参考集成。** 飞书不随 `oks` CLI 分发，也不是 OKS 核心依赖。参考代码位于仓库的 `reference-implementations/oh-my-feishu/`。

## 结果摘要

| 项目 | 本案例说明的边界 |
| --- | --- |
| 场景 | 人不在电脑前时，仍要对 Candidate 做出可追溯的审核决定。 |
| 输入 | 手机提交的来源，以及人对通过、修改或拒绝的明确反馈。 |
| Agent 完成 | 机械采集、生成 Candidate、展示来源范围，并执行已经发生的人类决定。 |
| 人做的决定 | 审核、修改或拒绝 Candidate，并为修改和拒绝留下理由。 |
| 最终交付物 | 一条可追踪的审核记录；是否成为 Wiki 仍取决于人的决定。 |
| 仍未验证 | 当前机器上的飞书凭据、调度器和参考实现可用性。 |

这个案例解决的不是知识判断，而是“人不在电脑前时，如何继续提供审核反馈”：

```text
手机提交来源
→ worker 机械采集并产生 Raw
→ Agent 起草 Candidate
→ 飞书 IM 显示候选
→ 人类回复通过 / 修改 / 拒绝
→ worker 执行已经发生的人类决定
```

## 边界

- Worker 不判断内容是否真实或重要。
- Candidate 不会因为进入飞书而自动成为 Wiki。
- `edit` 与 `reject` 必须保留理由。
- 调度由外部 cron、launchd 或任务计划负责；OKS 不内置常驻调度器。
- 飞书凭据由用户环境管理，不能写入仓库或知识库。

不配置飞书时，Agent 仍然可以在本地完成来源收集、候选展示和人审后的知识保存。飞书只改变人提供反馈的位置，不改变知识审核规则。

代码和运行说明见 [reference-implementations/oh-my-feishu](https://github.com/open-agent-power/open-knowledge-studio/tree/main/reference-implementations/oh-my-feishu)。
