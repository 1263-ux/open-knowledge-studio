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

但审核视图中的操作没有实际保存：第一次读取完整审核投影时三个字段仍为空。Agent 根据用户在聊天中的明确指令，把同一结论回填到唯一待审记录，再读取完整记录确认落库。这个动作保留了真实人工决策，但没有满足“用户只在 Base 内推动门禁”的低摩擦目标，不能将其记为 Base UI 验收通过。

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

### P3：审核动作的 UI 保存没有形成可验证反馈

用户认为已完成审核，但 Base 实际字段为空，必须回到聊天由 Agent 代写。它直接破坏“Base 是唯一控制面”的目标，优先级高于召回算法优化。最小修复应让审核提交具有明确的已保存反馈，并让 Worker/视图只呈现可操作字段。

### P4：Wiki trace 含本机绝对路径

Wiki 能在本机回到 Raw，但远程或另一台机器无法解析该路径。应将可移植标识（Capture ID、Run ID、Raw Bundle URI/相对路径）作为正式 trace，本机绝对路径只保留在本地运行状态中。

T6 优先选择 P3；P4 作为紧随其后的来源可移植性问题保留。
