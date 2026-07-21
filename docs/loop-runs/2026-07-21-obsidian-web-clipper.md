# Loop Run 001：Obsidian Web Clipper Capture Adapter

> 日期：2026-07-21
> 当前阶段：Candidate 已被人工拒绝
> 学习问题：如何复用官方 Clipper 做低摩擦 Capture Adapter，而不是重新开发插件？

## 运行标识

成功样本：

- Base record ID：`recvq1fpIyaVS9`
- Capture ID：`feishu-recvq1fpIyaVS9-be0fbb2ef464`
- Run ID：`run-20260721T224656-c88cddfa`
- Raw Bundle：`.oks/intake/feishu-recvq1fpIyaVS9-be0fbb2ef4`
- 来源：`https://github.com/obsidianmd/obsidian-clipper`
- 解析能力：`web.trafilatura`
- 结果：`complete`，22 条 evidence，validator `valid=true`

失败对照：

- Base record ID：`recvq1f8Gumb62`
- Capture ID：`feishu-recvq1f8Gumb62-b857b0290b96`
- Run ID：`run-20260721T224553-ac8639ea`
- 来源：`https://raw.githubusercontent.com/obsidianmd/obsidian-clipper/main/README.md`
- 结果：`failed`
- 错误：`DNS_FAILED` / `[Errno 11004] getaddrinfo failed`

## 本轮完成

- T1：固定一条公开官方来源、学习问题和五类可回查标识；
- T2：成功生成并验证 Raw Bundle v0.2；失败尝试停在真实失败状态；
- T3：生成 `drafts/obsidian-web-clipper-as-capture-adapter.md`，未写入 Wiki。

## 人工审核结果

- 决定：`reject`
- 原因：知识帮助不大，且样本方向偏离“以飞书多维表格跑通循环验收”的主目标。
- 结论：不晋升 Wiki。本 Run 证明 Candidate 门控有效，但不计为完整 POC 种子闭环。

审核结果已回填原 Base 记录。为让后续审核不依赖聊天或本地文件，当前表新增六个控制面字段：`候选内容`、`审核动作`、`审核意见`、`修改类型`、`审核时间`、`Wiki路径`。本记录已填写 `reject`、`方向偏离`、审核意见和审核时间，`Wiki路径` 保持为空。

## 遇到的问题

### P1：同一来源的 Raw 域名被本机 DNS 解析为不可用地址

`raw.githubusercontent.com` 的 A 记录在当前机器解析为 `0.0.0.0`，导致直接获取 README 失败；`github.com` 可正常解析并返回 HTTP 200。

影响：这是获取层问题，不是 Trafilatura 解析失败。系统正确保留了失败 Run，没有用浏览器看到的内容伪装成 Raw 成功。

当前处理：保留失败记录作为对照，使用同一官方仓库的 GitHub HTML 页面完成本轮。后续应给获取层增加域名诊断与合法 fallback 策略，但本轮不扩大实现范围。

### P2：HTML → Markdown 机械抽取丢失部分结构语义

成功 Raw 的正文存在空格粘连；GitHub README 的标题层级没有保留；roadmap 的 Markdown 复选框状态被剥离。

影响：文本主旨和链接仍可引用，但不能从抽取结果判断 roadmap 项的完成状态，也不适合直接发布为 Wiki。

当前处理：Candidate 只引用不受这些缺陷影响的事实，并把结构缺失列为未知项。后续可用同一样本比较 GitHub HTML、README 原始 Markdown和仓库 API 获取路径。

## 下一门禁

回到飞书 Base 主线：用户应能在 Base 内完成提交、状态观察、Candidate 查看、接受/编辑/拒绝、重试和最终验收；后台 Worker 根据 Base 状态继续处理。下一轮不以 Obsidian 集成为目标。
