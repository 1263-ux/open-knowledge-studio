---
title: Execution Traces
nav_order: 25
parent: 参考
---

# Execution Traces

执行轨迹按 `raw/executions/<run-id>/events.jsonl` 追加保存，`run.json` 记录状态。事件契约见 `_meta/trace-event.schema.json`。

轨迹是**溯源证据，不是可召回记忆**：`recall_episodic` 跳过 `raw/executions/`，轨迹只能通过 wiki 页面 frontmatter 的 evidence 链接到达。这是刻意的——否则 agent 自己写的 `ai_comment` 会被当作记忆加权喂回给它，压过人类收集的材料。

```bash
oks trace start memory-goal --run-id demo-001
oks trace append demo-001 --type retrieval --actor agent --payload '{"query":"memory"}'
oks trace judge demo-001 --outcome pass --comment "Evidence supports the result"
oks trace feedback demo-001 --outcome accepted --comment "Human accepted the result"
oks trace propose demo-001 --kind wiki --title "Recall lesson" --summary "..."
oks trace finish demo-001 --result '{"outcome":"success"}'
oks trace validate demo-001 --completed
```

`blocker` 事件必须同时写明原因和恢复条件，且只有 `human_action`、`human_comment`、`checkpoint` 事件能解除 blocked 状态——agent 无法通过追加评论自解锁。`propose` 只写入 `drafts/proposals/`，不会修改正式 wiki 或 skill；正式提升仍需人工操作。

轨迹的凭据防护是 **best-effort**，不是完整的数据防泄漏：

- 键名规则：拒绝 `token`、`api_key`、`authorization`、`cookie`、`password`、`secret` 等键，以及 `*_token`、`*_secret`、`*_password`、`*_cookie`、`*_api_key` 后缀。
- 值扫描：对字符串值匹配已知凭据形状（AWS `AKIA...`、GitHub `ghp_...`、OpenAI `sk-...`、Slack `xox*-...`、`Bearer ...`、PEM 私钥头），`evidence_refs` 同样受检。
- **不保证**捕获自定义格式的凭据。轨迹写入 git 跟踪的 `raw/executions/`，落盘即难以撤回——不要把未经审查的原始输出直接塞进 payload。
