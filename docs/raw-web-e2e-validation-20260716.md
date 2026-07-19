# 公开网页 Raw Inbox 端到端验证（2026-07-16）

> 历史报告（superseded）：本文保留 Trafilatura 与浏览器渲染对照数据，但旧共享 Base、`91403` 和实验脚本未产品化的结论已过期。当前 Base Worker 位于 `scripts/feishu_base_worker.py`，Capture/Run/Raw v0.2 协议以 `oks-connector/schemas/` 为准。

## 1. 测试目标

验证真实公开网页能否沿下面的路径进入 Open Knowledge Studio：

```text
飞书 Raw Inbox 链接记录
  → 公开 HTTP 获取
  → 正文提取
  → 必要时浏览器渲染回退
  → Web Raw Bundle
  → validate
  → 隔离知识库 recall
```

Raw 仍只保存提取内容、来源、证据和失败，不生成摘要、概念或 Wiki。

## 2. 测试对象

- 页面：Anthropic《Building effective agents》
- URL：`https://www.anthropic.com/engineering/building-effective-agents`
- 发布时间：2024-12-19
- 飞书 Base：`Open Knowledge Studio 每日链接入料`
- 表：`每日链接与思考`
- 表单：`每日知识采集`
- 测试记录 ID：`rec27NHELNbDVK`
- Raw 输出：`.oks/intake/web-anthropic-building-effective-agents-rendered`

该文章是公开技术文章，包含长正文、层级标题、链接和多张 Agent 工作流示意图，适合验证“正文能取得”与“结构和图片是否完整”之间的差异。

## 3. 飞书入口验证

通过真实表单提交：

- 内容：`[Raw Web E2E 2026-07-16] <URL>`
- 思考：验证公开网页从飞书 Raw Inbox 进入 HTTP/浏览器渲染路由，生成可追溯 Raw Markdown 并被知识库召回；
- 评级：B；
- 知识域：`computing`、`engineering`。

提交成功后，通过 Base 的“内容”字段关键词检索反查到唯一测试记录 `rec27NHELNbDVK`。Raw 的 `metadata.json` 已保存 Base token、table ID、record ID 和 form share token，`raw.md` 也包含飞书记录 ID。

结果回写仍被 Base 资源权限拒绝，错误为 `91403`。因此记录已创建，但“状态”和“总结”未能由 CLI 自动写回。这与前一轮附件测试一致，已经确认是 Base 内部资源角色问题，而不是 OAuth scope 缺失。

## 4. 两级获取路线对比

### 4.1 公开 HTTP + Trafilatura

网页 HTTP 状态为 200，Trafilatura 2.1.0 能取得主要正文。

| 指标 | 结果 |
|---|---:|
| 正文字符 | 约 18,500 |
| evidence | 68 |
| Markdown 标题 | 2 |
| 图片引用 | 0 |
| newsletter 噪声 | 1 段 |

正文包含 workflows、agents、prompt chaining、routing、parallelization 等核心内容，能够被召回。但标题层级和工作流示意图大面积丢失，说明“正文非空”不能作为网页提取完整的充分条件。

### 4.2 浏览器渲染 DOM 回退

浏览器渲染后的真实 `<article>` 中观察到：

- 20 个 H1/H2/H3 标题；
- 9 张文章区域图片；
- 可见文本约 19,859 字符；
- article HTML 约 33,164 字符；
- 全页截图约 2.04 MB。

将渲染后的 article HTML 包装为完整 HTML 文档，再交给 Trafilatura，得到：

| 指标 | 结果 |
|---|---:|
| Raw 正文字符 | 约 20,459 |
| evidence | 91 |
| Markdown 标题 | 19 |
| 远程图片引用 | 8 |
| newsletter 噪声 | 0 |

第一次直接把独立 `<article>` 片段交给 Trafilatura时返回空正文；将片段包装为 `<html><body>...</body></html>` 后成功。这是本次实验实际发现的适配边界。

最终路线为：

```text
http
  → browser-rendered-dom
  → trafilatura
  → markdown
  → html-snapshot
```

## 5. Web Raw 产物

最终 Bundle 包含：

```text
raw.md
content.md
metadata.json
evidence.jsonl
quality-report.json
assets/
  page.html
  rendered-article.html
  rendered-structure.json
  page-rendered.png
```

重要属性：

- 原始 URL与最终 URL均保留；
- HTTP 状态、Content-Type、采集时间、发布时间、网页内容哈希均保留；
- 原始 HTTP HTML与浏览器渲染 article HTML同时保留；
- 保留全页截图作为视觉证据；
- 91 条正文证据具有 URL、标题上下文、段落序号和 HTML 资产定位；
- 网页内容明确标记为不可信输入，其中的任何指令都不得执行；
- Raw 状态为 `partial`，没有将缺少作者和远程图片未本地化隐藏掉。

`validate` 结果：

- `valid: true`
- `schema_version: raw-multimodal/v0.1`
- `processing_status: partial`
- `evidence_count: 91`
- `errors: []`

警告：

1. 页面未提取到明确作者；
2. 8 个远程图片只保留 URL，尚未逐个下载为本地资产。

## 6. 召回验证

最终 Raw 被复制到隔离知识库：

`.oks/e2e-kb/web-rec27NHELNbDVK`

Wiki 为空，只包含这一条网页 Raw。以下查询均命中 `raw/misc/building-effective-agents/content.md`：

1. `workflows agents predefined code paths`
2. `orchestrator workers evaluator optimizer`
3. `memory tools retrieval augmented LLM`

因此网页正文已经进入现有 episodic recall，而不是只生成了孤立 Markdown 文件。

同时发现召回展示的 snippet 总是取文档开头约 200 字，而不是围绕命中词生成上下文。检索本身命中正确，但展示体验不够好；这属于 recall 展示层问题，不应由 Raw 修改正文来规避。

## 7. 本轮证明的能力

已经真实证明：

1. 用户可以把网页链接作为飞书表单记录提交；
2. 系统可以通过公开 HTTP 获取现代 Next.js/Cloudflare 页面；
3. 成熟正文提取器可以快速得到可检索正文；
4. 仅检查“正文非空”会误判质量，标题和图片覆盖同样重要；
5. 浏览器渲染 DOM可以补回绝大多数标题和视觉引用；
6. 原始 HTML、渲染 HTML、截图、正文与 evidence 可以组成可追溯 Web Raw；
7. Web Raw 能通过现有 Bundle 校验并被 OKS 召回；
8. 页面内容可以被当作不可信数据处理，而不是 Agent 指令。

## 8. 仍未完成的部分

### 8.1 这还是实验 Adapter

当前入口脚本为 `scripts/experiments/web_raw_probe.py`，Trafilatura 已安装在本地 `.venv`，但尚未成为项目正式依赖，也没有接入 `raw_ingest.py` 路由。它证明组合可行，还不是生产接口。

### 8.2 浏览器回退触发标准需要固化

本轮可用的轻量判据是：

- 正文为空；
- 标题数量明显异常；
- 原网页存在图片但 Markdown 图片为零；
- 正文混入明显导航或 newsletter；
- 核心 article 容器未被提取。

命中任一条件时，再进入浏览器渲染，而不是所有网页默认启动浏览器。

### 8.3 图片仍是远程引用

全页截图已经本地保存，但 8 张流程图尚未逐个下载并重写为本地路径。生产化前应下载文章正文内图片、计算哈希，并在下载失败时保留原 URL和失败原因。

### 8.4 飞书回写权限

表单创建、记录读取和关键词反查均成功；状态/总结回写仍被 `91403` 拒绝。需要在 Base 高级权限或角色配置中为当前用户/应用开放记录更新权限。

## 9. 下一步建议

不继续调研更多网页框架，先把本轮组合提升为正式 `Web Adapter`：

1. `raw_ingest.py` 增加 `web` 路由；
2. Trafilatura 作为轻量默认提取器；
3. 增加标题、正文、图片和噪声探测；
4. 不合格时调用浏览器渲染回退；
5. 下载正文图片并重写本地引用；
6. 保存飞书记录 provenance；
7. 修复 Base 角色权限后回写处理状态；
8. 改善 recall snippet，使其围绕命中位置展示。

最终判断：

> 公开网页已经能从飞书 Raw Inbox 进入可追溯 Raw Markdown 并被知识库召回；两级路由是必要的，单一 HTTP 正文提取不足以保留现实网页的完整结构和视觉信息。
