---
title: Execution Traces
nav_order: 25
parent: 参考
---

# Execution Traces

执行轨迹按 `raw/executions/<run-id>/events.jsonl` 追加保存，`run.json` 记录状态。事件契约见 `_meta/trace-event.schema.json`。

```bash
oks trace start memory-goal --run-id demo-001
oks trace append demo-001 --type retrieval --actor agent --payload '{"query":"memory"}'
oks trace judge demo-001 --outcome pass --comment "Evidence supports the result"
oks trace feedback demo-001 --outcome accepted --comment "Human accepted the result"
oks trace propose demo-001 --kind wiki --title "Recall lesson" --summary "..."
oks trace finish demo-001 --result '{"outcome":"success"}'
oks trace validate demo-001 --completed
```

`blocker` 事件必须同时写明原因和恢复条件。`propose` 只写入 `drafts/proposals/`，不会修改正式 wiki 或 skill；正式提升仍需人工操作。Trace 拒绝 `token`、`api_key`、`authorization`、`cookie`、`password`、`secret` 等敏感字段。
