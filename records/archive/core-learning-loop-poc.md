# 自进化学习主 Loop：POC 任务清单与验收标准

> **历史快照** — 本文记录特定时间点的过程与决策，不代表当前口径。
> 现行设计以 [`CONSTITUTION.md`](../../CONSTITUTION.md) 为准；归档说明见 [归档索引](README.md)。

> 状态：当前唯一主任务
> 更新日期：2026-07-23
> 原则：先用一条真实内容跑完整闭环，再根据观察到的问题微调；不并行扩张插件、视觉模型和复杂知识图谱。

## 1. POC 目标

让用户在发现一条有价值内容后，以低摩擦方式完成：

```text
发现内容
  → Capture（保存来源和学习意图）
  → Raw（机械抽取和证据）
  → Candidate（用自己的理解重讲）
  → 人工审核
  → Wiki（持久知识）
  → 新任务召回并使用
  → 反馈
  → 改进 PR
```

POC 的成功单位不是“生成一个 Raw Bundle”，而是“一条真实内容从采集走到使用反馈，并产生可验证的系统改进或明确证明无需改进”。

## 2. 职责边界

| 层 | 负责 | 不负责 |
|---|---|---|
| 飞书 Base | POC 唯一主入口与验收控制面：提交、状态、审核、重试、结果 | 机械解析和自动判断知识价值 |
| Obsidian | POC 通过后的可选 Capture Adapter | 第一轮主流程与验收控制面 |
| `oks-connector` | 获取后解析、证据定位、质量和失败事实 | 摘要、纠错、Wiki 决策 |
| Studio | 编排、Candidate、审核、召回、反馈 | 绕过登录、反爬或平台限制 |
| Wiki | 经审核的个人理解、实践结论和关系 | 保存整份原文或未经审核的 AI 输出 |
| GitHub Pages | 展示经过审核的知识和方法 | 发布 Raw、凭据或整段转载内容 |

当前 Capture/Processing Run/Raw Bundle v0.2 的机器事实源位于 `oks-connector/schemas/`，Studio 文档不再复制另一套协议定义。

第一轮必须证明：用户不依赖终端中的隐式状态，通过飞书 Base 提交内容，并可在个人飞书消息中阅读 Agent 的总结、回答问题和给出明确审核动作；Agent 将交互结构化写回 Base。Base 不是要求用户维护机器字段的后台表单，而是本 POC 的状态机、审计事实源和可观察控制面。

## 3. 核心任务清单

### T0：冻结事实源并清理旧文档

- [x] 保留 Studio 长期架构文档。
- [x] 将 Raw 阶段成果压缩为一份简要历史报告。
- [x] 删除已被当前协议和 Worker 取代的实验报告、旧计划和重复标准。
- [x] 首页只导航到当前 Loop、阶段简报和长期架构。

验收：

- `docs/` 中不存在仍被导航引用的已删除页面；
- 当前任务只有本文件一条主线；
- 历史成果可以在 `phase-history-summary.md` 中一次读完；
- Raw 新协议只指向 connector 的机器可读 Schema。

### T1：选择一个种子样本

- [x] 从当前飞书 Base 已成功生成 Raw 的内容中选择一条公开文章作为第一条种子。
- [x] 写清“为什么保存”和“我想解决的问题”。
- [x] 固定该记录、Run 和 Raw Bundle，整个 POC 不更换样本。

Run 001 的 Obsidian Candidate 因价值低且偏离 Base 主线被人工拒绝，只保留为门控校准证据。正式 POC 种子已固定为 Run 002 的 OpenLineage Object Model，学习问题是“飞书 Base 控制面如何区分能力定义、单次运行、输入输出和人工审核门禁？”阶段证据统一见 `phase-history-summary.md`。

验收证据：Base record ID、Capture ID、Run ID、Raw Bundle 路径和一个学习问题。

通过条件：五个标识全部可回查，学习问题不是空泛的“总结一下”。

### T2：确认 Capture → Raw

- [x] 重新读取种子 Capture，不修改用户原始输入。
- [x] 运行对应的成熟解析能力。
- [x] 校验 Raw Bundle，记录 `complete/partial/failed` 和 warning。
- [x] 任一失败必须停在真实阶段，禁止用人工摘要伪装 Raw 成功。

验收证据：`capture-envelope.json`、`processing-run.json`、`bundle.json`、`content.md`、`evidence.jsonl` 和 `quality-report.json`。

通过条件：validator 返回 `valid=true`；每个引用的 evidence 和 asset 可定位；失败模态可见。

### T3：生成 Teach-back Candidate

- [x] 基于用户学习问题读取 Raw 和必要 evidence。
- [x] 生成一份 Candidate，不直接修改 Wiki。
- [x] 将来源事实、个人理解、推断和未知项分开。
- [x] 提出一个可以实际执行的小实验或行动。

Candidate 最小结构：

```markdown
# 我对它的理解

## 它解决什么问题
## 核心机制
## 我会怎样向别人解释
## 与已有知识的关系
## 来源事实与 Evidence
## 我的推断
## 尚未确认的内容
## 准备怎样实践
```

验收条件：

- 至少一个核心主张链接到 Raw evidence；
- 没有 evidence 的内容明确标为个人推断；
- Candidate 可以被 `accept/edit/reject/defer`；
- Candidate 不复制整篇来源正文。

### T4：人工审核并晋升 Wiki

- [x] Candidate 内容或可访问链接回填到当前 Base 记录。
- [x] 用户通过明确的飞书个人交互给出 `accept/edit/reject/defer`，Agent 将结果结构化写回 Base。
- [x] Base 持久记录审核时间、审核意见和修改类型。
- [x] 接受后生成一篇 Wiki 页面；拒绝时保留拒绝理由。
- [x] Wiki 保存 Raw/Capture 来源，不直接依赖临时文件路径。

Run 002 验证了 Agent 代用户结构化回填 Base 的门禁；Run 003 进一步完成真实个人飞书消息闭环。机器人发送绑定 Candidate revision 的审核通知，用户回复 `accept，有研究价值`，Worker 将动作、意见、修改类型和时间写回 Base，并晋升 `wiki/computing/strategies/20260722-feishu-review-return-provenance.md`。飞书 OpenAPI 未返回这次 P2P UI 回复的 `parent_id/root_id`，系统使用严格的单待审、同会话、指定审核人、相邻消息回补，并以 `p2p_sequence_fallback` 明确留痕；详情见 Run 002/003 运行记录。Wiki trace 现保存 Capture ID、Bundle ID、Run ID 和仓库相对 Raw 路径，不再依赖本机绝对路径。

验收条件：

- 存在明确审核动作和时间；
- 仅查看 Base 就能知道 Candidate 内容、当前门禁和下一步动作；
- Wiki 页面能回到 Capture、Raw 和 evidence；
- 未审核 Candidate 不会进入正式 Wiki；
- Git diff 只包含本次批准的知识变化。

### T5：在新任务中召回并使用

- [x] 在不预先粘贴 Wiki 正文的新会话或隔离项目中提出原学习问题。
- [x] 运行 Studio search/recall。
- [x] 记录是否命中、排名、引用和答案是否真正使用该知识。
- [x] 执行 Candidate 中提出的小实践。

隔离召回从 `oks-connector` 项目目录发起，通过 `OKS_ROOT` 指向 Studio；没有预先粘贴 Wiki 正文。目标页面 `20260722-base` 在 Semantic Memory 中排名第 1，`relevance=2.51`。召回知识被用于核对当前实现：Capability Manifest 保持稳定定义、Processing Run 每次执行独立、Raw/Wiki 作为产物、Base 只做控制面投影，并实际完成一次 `accept` 后重复消费不二次晋升的小实验。该次实际使用已形成一次 access 记录；后续 recall/search 保持只读，只有 Agent 确实采用知识后才执行显式 `oks wiki use`。详细证据见 Run 002 记录。

验收条件：

- 目标 Wiki 进入 Top 5，或记录未命中的真实原因；
- 回答包含可回查来源；
- 用户能指出知识如何改变了本次判断或行动；
- “搜到了但没有用”不计为闭环成功。

### T6：反馈并形成一次 Loop 改进

- [x] 将本轮问题归为入口、获取、解析、Candidate、Wiki、召回或展示问题。
- [x] 只选择影响最大的一项做最小修复。
- [x] 用同一条真实审核消息复跑修复前后对照。
- [ ] 成功改进通过测试、PR 和 Merge；无收益则撤销并记录结论。

本轮最大问题归为“人工审核回程”：监听器离线错过事件后，P2P 消息详情又未暴露 `parent_id/root_id`，真实决定无法进入 Base 状态机。修复前，同一 reply message 无法安全关联；修复后，严格 `p2p_sequence_fallback` 完成 Base 写回和 Wiki 晋升，并保留关联方法。非相邻消息会被拒绝，重复消息不会二次处理。飞书写后读旧快照也以有限重试修复。自动化测试和真实复跑已通过，待提交远程分支并形成 PR/Merge 后关闭最后一项。

验收条件：

- 有修复前证据、修改内容和修复后证据；
- 自动化测试通过；
- PR 说明真实收益与边界；
- 只有同样本复跑成立的变化才能称为 Loop 改进。

### T7：发布一页经过审核的学习成果

- [ ] 从已晋升 Wiki 生成 GitHub Pages 页面。
- [ ] 页面包含“问题、我的理解、证据、实践、限制、变更记录”。
- [ ] 先用 Mermaid 生成可 diff 的结构图；确需手绘表达时，再用 Excalidraw 微调并导出 SVG。

验收条件：

- 页面不包含凭据、私有路径和无权转载的全文；
- 图形源文件可继续编辑，网站使用 SVG/PNG；
- 本地或 Pages 构建无断链；
- 页面内容与审核后的 Wiki 一致。

## 4. POC 总验收门

以下条件必须全部满足，才允许扩展到第二条内容：

- [ ] 一条真实内容完成 T1–T7；
- [ ] Capture、Raw、Candidate、Wiki、Recall、Feedback 六段均有持久证据；
- [ ] 至少一次人工审核；
- [ ] 至少一次新任务召回与实际使用；
- [ ] 至少一个问题推动了可验证改进，或形成明确的“不改”实验结论；
- [ ] 改进已提交并远程备份；
- [ ] 用户能在不读实现代码的情况下解释这条 Loop。

## 5. 第一轮不做

- 不开发新的 Obsidian 插件，先复用官方 Web Clipper 或飞书入口；
- 不建设共享 Blob Store；
- 不自动晋升 Wiki；
- 不引入 ColPali 或大视觉模型；
- 不一次处理大量来源；
- 不以“生成文件数量”代替学习效果。

## 6. POC 通过后的扩展顺序

1. 用同一流程增加一条平台视频或人工字幕快照；
2. 增加一条群聊/飞书附件；
3. 比较三类入口的采集成本和失败点；
4. 再制作 Obsidian Web Clipper 模板和 Inbox Adapter；
5. 累计 10 条真实内容后复盘 Wiki 结构；
6. 只有出现明确重复存储数据后，才评估 Blob Store；
7. 只有 OCR 文本召回持续无法回答高价值问题后，才恢复视觉理解实验。
