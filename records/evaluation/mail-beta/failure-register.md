# Mail Failure Register

状态：P3.3 baseline；只记录有真实证据的事件，不把模型自述当证据。

## Counting

- `counted=yes`：影响真实协作闭环，计入 P3.3 的 20--30 事件决策阈值。
- `counted=no`：操作拼写或测试流程摩擦，保留用于改进执行手册，但不推动协议设计。
- `core_confirmed=no`：截至本表，没有证据确认 Mail Core 的 canonical message、Thread
  或 receipt 持久化逻辑是根因。

## Baseline events

| ID | Task / evidence | Observed event | Primary tag | Counted | Resolution / current state |
| --- | --- | --- | --- | --- | --- |
| F-001 | BETA-01; batch-01 task card | Agent 进程未继承 `OKS_AGENT_ID`，首次 ack 失败 | `host_limitation` | yes | 显式设置 Agent identity 后完成 |
| F-002 | BETA-02; `claude-b02-debug.log` | Claude headless 的 `dontAsk` 模式阻断 Bash | `host_limitation` | yes | 允许命令重试；宿主限制仍保留 |
| F-003 | BETA-02; `claude-b02b-debug.log` | 外部显式 Session ID 与实际 Claude Session UUID 不一致，ack 找不到对应 receipt | `host_limitation` | yes | interactive runner 已解决；headless 仍需宿主对齐 |
| F-004 | BETA-02; same debug logs + receipt | Hook 已 presented/additionalContext，但模型未按 Mail 行动 | `agent_ignored_mail` | yes | 只计为 headless 观察；不归类为 delivery failure |
| F-005 | BETA-06; batch-01 task card | Agent 提示中手工写错 message ID，命令安全失败 | `operational_friction` | no | 使用 `wait` 返回的真实 ID 后完成 |
| F-006 | BETA-08 preliminary attempts; `oks-mail-p3-beta-20260906-b08-final3`/`final4` | Claude interactive 早期运行未加载正确的 OKS Mail 包实现 | `host_limitation` | yes | 增加 native runner/package-root 注入后修复 |
| F-007 | BETA-08 final5; `oks-mail-p3-beta-20260906-b08-final5` | Hook 能运行，但旧环境把消息投影到错误 root/identity | `host_limitation` | yes | final6 使用实际 Claude Session UUID 通过 |
| F-008 | BETA-09; task execution output | 旧 Codex CLI 不支持默认 `gpt-6-astra` | `host_limitation` | yes | 改用宿主可用模型，任务继续 |
| F-009 | BETA-09; task execution output | 旧 Codex CLI 不支持默认 `max` reasoning effort | `host_limitation` | yes | 显式改用 `xhigh`，任务继续 |
| F-010 | BETA-09; isolated Mail root | Agent 环境未继承 identity，默认 inbox 误落到 `@human` | `host_limitation` | yes | 一次性显式 `OKS_AGENT_ID=codex` 后完成 |
| F-011 | BETA-10 Session A; isolated root | A 首次 ack 被判定为 `@human` receipt，Agent identity 不匹配 | `host_limitation` | yes | 显式 identity 后 ack 成功 |
| F-012 | BETA-10 Session B; process output | Codex CLI 触发 ChatGPT/Codex quota，无法完成 Session B | `host_limitation` | yes | 改用受限的 Claude fallback；配额问题未由 Core 解决 |
| F-013 | BETA-10 fallback; isolated root | Claude fallback 错误执行 archive，提前关闭原 Thread | `host_limitation` | yes | 追加同一 Thread retry；最终无重复决策 |
| F-014 | BETA-10 retry; receipt inspection | 消息先被 `read`，再 ack 时尚未建立 Session receipt | `operational_friction` | no | 先 `wait` 建立 presented receipt 后 ack 成功 |
| F-015 | BETA-11 first probe; local bare mirror root | 发送端继承 Codex 环境，预期 human handoff 被写成 `from: codex` | `host_limitation` | yes | 显式 `OKS_AGENT_ID=human` 重跑并通过 |
| F-016 | BETA-12; `2026-09-06-b12.md` + isolated root | Claude 先用 `mail read`，未建立 Session receipt，直接 ack 被安全拒绝 | `operational_friction` | no | 回到 `wait → ack` 后 receipt 为 `acknowledged`，same-Thread reply 已存在 |
| F-017 | BETA-13; isolated `.claude/hooks/validate-wiki-write.sh` output | 写入 `results/beta13-review.md` 被 Hook 的 JSON 解析错误拦截 | `host_limitation` | yes | 只在隔离目录用 Bash fallback 写入；不修改生产 Hook |
| F-018 | BETA-13; final verification output | 宿主验证组合命令依赖 `jq`，但该环境未安装，返回 127 | `operational_friction` | no | 报告文件、receipt、ack/reply 由独立证据确认；不改 Mail Core |
| F-019 | BETA-14 Session A/B; Claude execution output | Agent 两次将 ack 参数写成 `--session`，CLI 拒绝后才改用 `--session-id` | `operational_friction` | no | CLI 错误信息足够完成自恢复；后续 handoff 明确给出精确命令 |
| F-020 | BETA-14 Session B; Claude execution output | 首次 reply 使用了不存在的 `--body-file`/位置参数组合，CLI 拒绝后改用 `--body` 完成发送 | `operational_friction` | no | Agent 根据 `oks mail send --help` 自恢复；不改 Mail Core |
| F-021 | BETA-15; Claude execution output | Agent 首次将 ack 参数写成 `--session`，CLI 拒绝后改用 `--session-id` | `operational_friction` | no | Agent 根据 CLI 错误自恢复；后续任务卡明确精确命令 |
| F-022 | BETA-15; Claude execution output | Agent 首次把 message ID 传给 `oks mail reply`，CLI 要求 Thread ID 后自恢复 | `operational_friction` | no | Agent 从错误输出取得 Thread ID 并完成 same-Thread reply |

## Baseline summary

| Class | Count | Meaning |
| --- | --- | --- |
| `host_limitation` | 13 | 宿主权限、identity、模型/配额、runner 或 Hook 环境问题 |
| `agent_ignored_mail` | 1 | Mail 已呈现但 headless 模型未消费/行动 |
| `operational_friction` | 8 | 错 ID、错误顺序、CLI 参数或缺少验证工具；保留但不推动协议决策 |
| Mail Core confirmed failure | 0 | 没有 canonical message、Thread 或 receipt 持久化根因 |

当前计入阈值 14/20；还需至少 6 个新的真实计入事件。BETA-12--BETA-15 已完成，
BETA-16 因重复 CLI 执行根因暂缓，先等待 RETHINK/Owner 决策；不为了达到数字而制造失败。
