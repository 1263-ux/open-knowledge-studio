# Mail Host Compatibility Matrix

这张表只记录已观察到的行为。`not-tested` 不等于不支持，`unsupported` 需要宿主或
Adapter 的明确证据。`agent_ack`/`agent_reply` 记录 Agent 是否实际通过支持路径完成
操作，不把 Host 自动代办能力混入 Mail Core 契约。

| Host | receive | presented | agent_ack | agent_reply | manual_reply | wake | Evidence / note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude interactive | pass | pass | pass | pass | pass | unsupported | BETA-08 final6: native Windows runner presented to the actual Claude Session UUID; Claude acked and replied in the same Thread |
| Claude headless (historical observation) | pass | pass | fail | pass | pass | unsupported | BETA-02: Hook created `presented`; `dontAsk` blocked Bash, bypass run replied but did not ack the Hook Session; not formal support |
| Codex CLI contract (isolated) | pass | pass | pass | pass | pass | unsupported | Isolated G4 completed receive → presented → ack → same-Thread reply; this does not prove process-internal Codex Host integration |
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

2026-09-10 的 `.agent/RESULT-mail-independent.md` 另有一次隔离 Claude headless
闭环观察（使用 `--dangerously-skip-permissions`）；由于原始 transcript 与临时
目录未版本化保存，本矩阵不把它提升为可复现的 `pass`，也不覆盖 BETA-02 的
权限受限基线。后续应以版本化任务卡和原始证据重新验证。
