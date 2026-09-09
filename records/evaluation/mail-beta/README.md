# OKS Mail Beta Evaluation

状态：P3.1 首批已完成（6 个样本）；P3.2 长任务 Beta 已完成（5 个样本）；P3.3
  失败积累已开始，协议保持冻结。

## 目标

验证 Mail 是否真正减少 Agent 接手任务时的协作摩擦，而不只是验证消息
文件能够送达。核心假设是：

> Agent B 能在几乎不重新询问背景的情况下，继续 Agent A 交接的真实工作。

本目录只保存可复现的、去除个人内容的评估定义和结果摘要。真实 Mail、Session
receipt、Claude/Codex 日志放在独立临时实例中，不写入个人知识库。

## 范围与非目标

- 范围：Claude interactive/headless、Codex CLI、DSH 人工控制面的接收、呈现、
  ack、回复、跨 Session 继续、冲突与文件协作观察。
- 第一批：5--10 个真实但有边界的长任务，覆盖 Claude → Codex、Codex → Claude、
  Human → Agent。
- 非目标：新增 Mail 字段或生命周期、daemon、heartbeat、自动 wake、任务 claim、
  WebSocket/Redis/MQ、跨机器产品化。
- `SIMULATED`、`REPLAYED` 只能作为协议回归证据，不能计入真实 Beta 成功率。

## 评估单位

一个评估单位是一个有明确工作结果的 Thread handoff，不是一次 API 调用。每个
任务必须有一个可检查的结果，例如审查意见、测试报告、研究摘要、文件修改或
冲突决策。任务卡见 [task-card-template.md](task-card-template.md)。

每个任务至少记录：

```text
task_id, date, task_kind, route, sender_host, receiver_host
thread_id, handoff_message_id, receiver_session_id
handoff_at, first_action_at, result_at
outcome, metrics, failure_tags, evidence, notes
```

## 指标定义

| 指标 | 计数规则 | 目标解释 |
| --- | --- | --- |
| `handoff_success_rate` | 有效任务中，接收方按验收条件完成工作的比例 | Mail 是否完成协作闭环 |
| `context_reask_count` | 接收方重新询问发送方已在 Thread/关联文件中给出的背景次数 | 核心摩擦指标，越低越好 |
| `human_intervention_count` | 人为补充背景、重发、纠正收件人或手动唤醒的次数 | 自动协作依赖度 |
| `duplicate_work_count` | 同一结果被重复执行或重复产出的次数 | Thread/Session 清晰度 |
| `handoff_to_action_latency` | `first_action_at - handoff_at` | 接手速度；注明是否人工唤醒 |
| `unresolved_thread_count` | 任务结束时仍无结果、拒绝或明确关闭语义的 Thread 数 | 遗留协作量 |

计数口径必须写在任务卡中；无法从日志证明的指标写 `unknown`，不能猜测为零。

## 失败分类

一次失败可以有多个标签，但必须选择一个主因：

| 标签 | 含义 |
| --- | --- |
| `delivery_failure` | 消息未进入目标 Agent 的可见输入或 wait 结果 |
| `context_insufficient` | Mail 已呈现，但不足以让接收方开始工作 |
| `wrong_recipient` | 地址、Agent、Session 或 Thread 选错 |
| `stale_message` | 接收方看到的不是当前有效状态 |
| `duplicate_handoff` | 同一工作被重复交接或重复执行 |
| `agent_ignored_mail` | Mail 已呈现，接收方仍未按约定处理且无宿主限制证据 |
| `thread_confusion` | 回复未回到同一 Thread，或 Thread 语义无法判断 |
| `file_conflict` | 协作结果因工作区/提交冲突无法合并 |
| `host_limitation` | 宿主不支持或阻断了已定义的 Mail 行为 |

## 判定规则

1. 先保存消息、receipt、命令输出或宿主日志，再判定结果。
2. `presented` 只证明进入某个 Session 的可见输入；`acknowledged` 只证明明确确认，
   两者都不代表工作完成。
3. Thread 回复、文件差异、测试结果或人工明确结论才是工作结果证据。
4. Claude headless 若 Hook 已解析并提供 `additionalContext`，但模型没有消费或行动，
   分别记录 `presented=pass` 与 `agent_ignored_mail`/`host_limitation`，不要把它写成
   `delivery_failure`。
5. 连续 2 次同类逻辑失败回到 PLAN/RETHINK；不要为孤例扩展协议。

## 执行顺序

1. 以 [host-compatibility-matrix.md](host-compatibility-matrix.md) 记录现有基线。
2. 建立临时 OKS 实例，给每个 Agent 和 Session 使用独立 ID。
3. 按任务卡执行 handoff → present/wait → ack → same-Thread action/reply → archive。
4. 每个任务结束立即填写指标和失败标签，不等到批次结束再回忆。
5. 批次结束只输出聚合结论；只有累计 20--30 个真实失败事件后，才决定是否增加
   新能力。

## 当前批次

- `pilot-00`：既有 G4 协议验收基线，属于真实 CLI 集成证据，不计入 P3 长任务样本。
- `batch-01`：本轮执行的首批 6 个真实、边界清晰的协作任务，结果记录在
  [2026-09-06-batch-01.md](2026-09-06-batch-01.md) 中；它们证明了第一轮接手闭环，
  作为后续长任务 Beta 的基线。
- `batch-02`：5 个长任务，覆盖文件修改、Claude interactive、研究/审查、Session
  A/B 冲突接手和本地 Git mirror；结果记录在
  [2026-09-06-batch-02.md](2026-09-06-batch-02.md) 中。最终结果均有证据，且
  `context_reask_count=0`；宿主配额、身份继承和提示执行偏差单独保留为失败分类。
- `P3.3`：失败登记与决策门禁见 [2026-09-06-p3-3-plan.md](2026-09-06-p3-3-plan.md)、
  [failure-register.md](failure-register.md) 和
  [2026-09-06-p3-3-aggregate-20.md](2026-09-06-p3-3-aggregate-20.md)。当前基线为
  14 个计入阈值的真实宿主/Agent 事件、8 个不计入协议决策的操作摩擦；
  BETA-12--BETA-15 已完成，BETA-16 因重复 CLI 执行根因暂缓，尚未确认 Mail Core
  逻辑失败。
