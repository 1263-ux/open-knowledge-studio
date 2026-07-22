# Loop Run 002：飞书 Base 控制面闭环

> 日期：2026-07-22
> 当前阶段：Candidate 已回填 Base，等待用户在 Base 内审核
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

Base 当前应显示：

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
