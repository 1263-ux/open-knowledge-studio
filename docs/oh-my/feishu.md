---
title: Oh My Feishu
nav_order: 3
parent: Oh My
---

# Oh My Feishu：把人工审核带到手机

{: .warning }
> **类型：参考集成。** 飞书不随 `oks` CLI 分发，也不是 OKS 核心依赖。参考代码位于仓库的 `reference-implementations/oh-my-feishu/`。

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

不配置飞书时，`/ingest`、`oks drafts list` 与 `oks drafts promote` 的本地路径仍然完整可用。

代码和运行说明见 [reference-implementations/oh-my-feishu](https://github.com/open-agent-power/open-knowledge-studio/tree/main/reference-implementations/oh-my-feishu)。
