# Loop Run 002：飞书 Base 控制面闭环

> 日期：2026-07-22
> 当前阶段：已晋升 Wiki；隔离召回命中；进入反馈改进
> 学习问题：飞书 Base 控制面如何区分能力定义、单次运行、输入输出和人工审核门禁？

## 运行标识

- Base record ID：`recvq6nZfwztXx`
- Capture ID：`feishu-recvq6nZfwztXx-792a52e5fb3d`
- Run ID：`run-20260722T195226-7db4031f`
- Candidate ID：`feishu-base-control-plane-object-model`
- Raw Bundle：`.oks/intake/feishu-recvq6nZfwztXx-792a52e5fb`
- 来源：`https://openlineage.io/docs/spec/object-model/`

## Capture → Raw 结果

- 能力：`web.trafilatura`
- 文本模态：`succeeded`
- Evidence：48 条
- Bundle validator：结构有效
- 总状态：`partial`
- 警告：页面未提取到明确作者、未提取到明确发布时间

正文、HTML 快照、evidence 数量和 HTTP response 的覆盖检查全部通过。`partial` 来自来源元数据缺失，不是正文解析失败；系统没有把缺失作者和时间伪装为已知值。

## Candidate 结果

Agent 基于学习问题和 Raw evidence 生成 `drafts/feishu-base-control-plane-object-model.md`，并通过 Worker 的 `publish-candidate` 接口回填同一条 Base 记录。

Candidate 发布后 Base 显示：

- `运行状态=候选待审`
- `Wiki状态=review_pending`
- `候选ID=feishu-base-control-plane-object-model`
- `候选内容`为完整 Teach-back 正文
- `审核动作/审核意见/修改类型/审核时间/Wiki路径`为空

## 本轮新增的确定性接口

- `publish-candidate`：只有本地 Raw Bundle 可验证时，才写 Candidate 和 `review_pending`；
- `review-once`：每次最多消费一个新的 `accept/edit/reject/defer`；
- Candidate 本地状态记录 revision、hash、Run、Raw 路径和审核历史；
- 同一审核指纹只处理一次，防止重复晋升；
- `accept` 使用 Base 中用户最终看到的正文晋升，并保留 trace 与 review；
- `reject` 保留拒绝 Candidate 和理由，不创建 Wiki；
- `edit` 回到需人工，`defer`保持待审。

## 真实运行暴露的问题

### P1：旧晋升逻辑错误复数化 strategy

原 `promote_draft` 会把 `strategy` 转成 `strategys`。本轮在真正准备 Base accept 分支时发现，已改为显式映射到 `strategies`，并增加回归测试。

### P2：AI 判断不应伪装成脚本能力

现有 Studio 明确把 Raw → Candidate 的 AI 蒸馏交给 Agent。Worker 只接受 Agent 已生成的、带 frontmatter 的 Candidate，再负责校验、回填和审核状态消费；没有增加模板摘要器冒充 Teach-back。

## 当前人工门禁

Base 已创建专用网格视图：

- 名称：`候选审核`
- View ID：`vewxJs3jUf`
- 筛选：`Wiki状态 intersects [review_pending]`
- 当前命中：Run 002 的待审记录

授权过程按 API 实际返回分两次增加最小 scope：`base:view:read` 与 `base:view:write_only`。设备流期间曾发生一次 `open.feishu.cn` DNS 查询失败，CLI 自动重试后授权成功。

视图的可见字段精简请求连续返回 `800070003 no operation produced`，读取后仍为 27 个字段。筛选已生效，因此不阻塞审核；该 no-op 作为 Base/lark-cli 视图配置问题保留，未宣称字段隐藏成功。

用户需要在 Base 的 `recvq6nZfwztXx` 记录中阅读 `候选内容`，填写：

1. `审核动作`：`accept/edit/reject/defer`；
2. `审核意见`；
3. `修改类型`。

`审核时间`由 Worker 在消费动作时自动回填，避免人工录入时间。

完成后运行 `review-once`。在 Base 出现明确动作前，不创建 Wiki。

## 人工审核与 Wiki 晋升结果

用户明确给出的审核结论是：

- `审核动作=accept`
- `审核意见=文章有价值`
- `修改类型=[无修改]`

用户通过对话给出明确审核结论，而不是自行维护 Base 的机器字段。第一次读取审核投影时字段为空符合这一交互事实；Agent 将用户的明确结论结构化回填到唯一待审记录，再读取完整记录确认落库。这里此前被错误记录成“Base UI 操作没有保存”，现已纠正。目标职责是 Agent 负责总结、提问和结构化落账，用户只负责判断。

第一次运行 `review-once` 的真实结果：

- `processed=true`
- `运行状态=已晋升`
- `Wiki状态=promoted`
- `Wiki路径=wiki/computing/strategies/20260722-base.md`
- `审核时间=2026-07-22 20:22:41`

紧接着第二次运行返回 `processed=false, reason=no_pending_reviews`。Wiki 目录中只有一份 `20260722-base.md`，因此同一审核动作没有重复晋升。

Wiki 的 frontmatter 保留了 Run ID、Base record ID 和 review，但 Run trace 仍写入本机绝对 Raw Bundle 路径。这证明来源可回查，却不满足跨机器可移植和远程备份要求。

## 隔离召回与实际使用

从独立的 `oks-connector` 项目目录提出原学习问题，通过 `OKS_ROOT` 指向 Studio，未把 Wiki 正文粘贴进上下文：

```powershell
oks recall "飞书 Base 控制面如何区分能力定义、单次运行、输入输出和人工审核门禁？" --limit 5
```

目标 Wiki `20260722-base` 在 Semantic Memory 中排名第 1，`relevance=2.51`，因此 Top 5 验收通过。召回结果真正改变了本轮判断：

1. Capability Manifest 应保持类似 Job 的稳定能力定义；
2. Processing Run 是每次实际执行，不得被 Base 当前状态覆盖；
3. Capture、Raw Bundle 和 Wiki 是不同阶段的 Dataset/Entity；
4. Base 是控制面投影，机器运行状态与人工 Wiki 门禁必须分离；
5. 根据第 4 条，实际执行了一次 `accept` 后重复消费的实验，第二次没有生成 Wiki。

来源事实可回查到 `trafilatura-block-0020/0022`（Job）、`0029/0030`（Run）和 `0037/0038`（Dataset）。

## 下一轮最小改进候选

### P3：个人飞书审核交互已完成真实闭环

本轮已验证“Agent 总结和提问 → 用户明确判断 → Agent 写回 Base → Worker 晋升”的人工流程，但个人飞书消息/卡片尚未自动关联 Candidate 和 Worker。最小修复应向用户个人发送包含摘要、证据和关键问题的审核消息；只接受明确 `accept/edit/reject/defer`，并将 Candidate revision、审核内容和时间结构化写回 Base。Base 继续作为审计事实源，不要求用户填写机器字段。

发送端已在上游集成分支完成首版：`publish-candidate` 会在配置 `OKS_FEISHU_REVIEW_USER_ID` 后立即向该个人发送 Agent 提供的 `review_summary`、最多三个 `review_questions` 和四种审核动作；同一 Candidate revision 使用稳定幂等键。未配置收件人时明确记录 `skipped`，发送失败时保留 `failed`，不会伪装成已通知。

回程链路现已实现为 `listen-reviews`：使用 bot 身份订阅 `im.message.receive_v1`，只接收指定用户的个人消息，并要求消息通过 `reply_to/root_id` 精确指向当前 Candidate revision 的审核通知。解析器只接受显式且不冲突的 `accept/edit/reject/defer`；`edit/reject` 必须附理由。命中后先把审核动作、原始意见和时间写回 Base，再复用既有 `review_candidate` 门禁执行状态转换或晋升；消息 ID 会写入本地 Candidate state，重复投递不会二次处理。普通私聊、群消息、其他人的回复和未引用审核通知的消息都不会猜测归属。

真实 Candidate 回程已于 Run 003 完成，证据见下节。常驻监听器仍未部署，因此“进程在线时自动消费”与“进程离线后的严格历史回补”是两个不同能力，不能混写为一个验收项。

## Run 003：个人消息 → Base → Wiki 的真实闭环

- Base record ID：`recvq6Yr6qZGiX`
- Capture ID：`feishu-recvq6Yr6qZGiX-7536284fcbfe`
- Run ID：`run-20260722T222212-284bc2c7`
- Candidate ID：`feishu-review-return-provenance`
- 来源：`https://www.w3.org/TR/prov-o/`
- Raw Bundle：`.oks/intake/feishu-recvq6Yr6qZGiX-7536284fcb`

W3C PROV-O 页面由 `web.trafilatura` 完成正文抽取，文本模态 `succeeded`，产生 421 条 evidence；其他模态按来源类型 `skipped`，总状态为 `partial`。第一次使用的 GitHub raw commit URL 返回真实 `404`，未伪装成解析成功，随后同一测试记录改用 W3C 官方来源重新运行。

Worker 发布 revision 1 后，机器人向当前用户的个人会话发送绑定 Candidate 的审核通知：

- prompt message ID：`om_x100b6939687b70a0ddb95f9639613dc`
- 用户 reply message ID：`om_x100b6939194320a0c006851420c128e`
- 用户原文：`accept，有研究价值`

监听进程在用户回复前已经按五分钟上限退出，因此事件流没有回放这条历史消息。进一步通过飞书官方消息详情 API 检查发现，这次个人会话 UI 中的“回复”没有向 OpenAPI 暴露 `parent_id/root_id`。系统没有假称存在原生引用关系，而是新增受限的 `p2p_sequence_fallback`：仅当同一私聊、配置的审核人、会话中恰好一个待审 Candidate、回复紧邻通知且文本只有一个明确动作时，才允许恢复；否则拒绝关联。原生 `parent_id/root_id` 仍是优先路径。

回补后 Base 持久结果：

- `审核动作=accept`
- `审核意见=有研究价值`
- `修改类型=[无修改]`
- `审核时间=2026-07-22 22:36:41`
- `运行状态=已晋升`
- `Wiki状态=promoted`
- `Wiki路径=wiki/computing/strategies/20260722-feishu-review-return-provenance.md`

Wiki frontmatter 保留了 Run、Capture、Bundle、Base record、`outcome=success`、`decision_correct=true` 和 `lesson=有研究价值`。execution trace 使用仓库相对 Raw 路径，不再包含本机绝对路径。历史回复重复回放返回 `review_message_already_processed`，不会二次晋升。

这次真实运行还暴露了飞书 Base 的短暂写后读旧快照：审核字段已写入，但紧接着第一次读取仍看不到 `审核动作`，第一次晋升返回 `no_review_action`；稍后同一记录读取已出现完整字段，`review-once` 成功晋升。Worker 现对审核写入后的读取做 0.25/0.5/1 秒有限重试，超时则明确失败并保留 Base 动作供后续恢复，不以旧快照继续错误决策。

中文标题的 Wiki slug 已改为优先使用稳定 Candidate ID；现有页面也完成文件、指纹索引、Candidate state 与 Base 路径的同步迁移。尚存的非阻塞问题是监听器不是常驻服务。

### P4：Wiki trace 已移除本机绝对路径

Wiki execution trace 现保存 Capture ID、Run ID、Bundle ID 和仓库相对 Raw 路径；本机绝对路径只保留在被忽略的本地 Candidate/运行状态中。另一台机器恢复相同的 Raw 相对目录后即可解析，不再把原机器盘符当成知识协议。

P3 的审核回程与 P4 的来源可移植性均已用 Run 003 的真实记录验证。

## 资源获取策略补充：AgentKey

`agentkey.app` 已确认是统一 MCP/Skill 数据接口，而不是共享用户浏览器登录态的工具。它通过 `discover → describe → execute` 暴露搜索、网页抓取、社交、金融与链上等能力，使用统一订阅积分并提供供应商故障转移。它适合作为公开数据获取的付费后置兜底，也可作为 Capability Manifest 动态发现层的设计参考；不能替代用户明确授权标签页的登录态访问。当前只完成公开官网与文档核验，没有安装插件、创建账号、购买套餐或发送任何项目数据。
