# Mail Host Compatibility Matrix

这张表只记录已观察到的行为。`not-tested` 不等于不支持，`unsupported` 需要宿主或
Adapter 的明确证据。`agent_ack`/`agent_reply` 记录 Agent 是否实际通过支持路径完成
操作，不把 Host 自动代办能力混入 Mail Core 契约。

| Host | receive | presented | agent_ack | agent_reply | manual_reply | wake | Evidence / note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude interactive | pass | pass | pass | pass | pass | unsupported | BETA-08 final6: native Windows runner presented to the actual Claude Session UUID; Claude acked and replied in the same Thread |
| Claude headless | pass | pass | fail | pass | pass | unsupported | BETA-02: Hook created `presented`; `dontAsk` blocked Bash, bypass run replied but did not ack the Hook Session |
| Codex CLI | pass | pass | pass | pass | pass | unsupported | Isolated G4 completed receive → presented → ack → same-Thread reply |
| DSH human panel | pass | n/a | n/a | n/a | pass | unsupported | Observation-first control surface; human send/reply/read/archive |

## Field meanings

- `receive`: target can obtain the Mail through Hook or `oks mail wait`.
- `presented`: a Session-visible presentation and receipt exists.
- `agent_ack`: the Agent explicitly called `oks mail ack` for its presented Session receipt and the receipt became `acknowledged`.
- `agent_reply`: the Agent explicitly used `oks mail reply` or `oks mail send --thread` and created a meaningful same-Thread result.
- `manual_reply`: a user or Agent can intentionally reply through the supported path.
- `wake`: a host actually wakes an inactive Session and reports the result.

## Batch update rule

只在有任务卡和原始证据时更新状态；不要用一次回归测试替代真实宿主行为。BETA-01--BETA-06
的证据与临时根路径记录在 batch-01 中，BETA-07--BETA-11 记录在 batch-02 中，
BETA-12--BETA-15 记录在各自任务卡中。
