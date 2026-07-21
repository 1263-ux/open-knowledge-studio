# 阶段历史简报

> 截止日期：2026-07-21
> 目的：用一份短报告保留项目过去阶段做过什么、证明了什么、还没有证明什么。旧实验报告已从当前文档集中移除；详细实现历史仍可通过 Git 提交和测试产物追溯。

## 1. Studio 基础阶段

项目原有能力包括：

- `profiles/raw/drafts/wiki/settings` 五桶结构；
- Raw → Draft → 人工审核 → Wiki 的 Dreaming 思路；
- 基于 Markdown/YAML 和 Git 的知识管理；
- CLI search/recall、Wiki 生命周期、衰减和人工晋升约束。

长期保留的不变量是：Raw 与知识分离，AI 可以提出 Candidate，但不能未经人工审核直接晋升 Wiki。

## 2. 多模态 Raw 原型阶段

项目复用了成熟工具，没有重写解析器：

| 输入 | 能力 | 真实结果快照 |
|---|---|---|
| DOCX | MarkItDown | 真实项目计划生成文档级 evidence；定位粒度有限 |
| 15 页 PPTX | MarkItDown | 15 条幻灯片 evidence，内嵌媒体保留 |
| 7 页数字 PDF | MinerU | 299 条 evidence |
| 13 页扫描 PDF | MinerU | 322 条 evidence |
| 公式图片 | RapidOCR | 154 条 evidence，其中 153 个 OCR 块 |
| 正常语速音频 | faster-whisper | 60 条时间戳 ASR |
| 困难高速音频 | faster-whisper | 0 条，诚实标为 failed |
| 本地技术视频 | Watch + OCR + ASR | 376 条 evidence：12 帧、37 ASR、327 OCR |
| 飞书视频附件 | Watch + OCR | 339 条 evidence：12 帧、0 ASR、327 OCR |

这些结果证明“已经取得的本地文件可以形成可定位 Raw”，不证明任意互联网链接都可以取得。OCR、ASR、公式和版面结果未经人工校对，因此成功产物通常是 `partial`。

## 3. Connector 迁移与协议阶段

多模态能力被迁移到独立 `oks-connector`，Studio 保留编排职责。形成了：

- Capability Manifest；
- Capture Envelope；
- Fetch Receipt；
- Processing Run；
- Raw Bundle v0.2；
- 明确的逐模态状态、错误、来源快照和简化 PROV 血缘；
- `validate`/`validate-v2` 机械完整性检查。

当前机器事实源：

- `oks-connector/schemas/`
- `oks-connector/capabilities/`
- `oks-connector/docs/protocols-v0.1.md`

2026-07-19 检查点：connector 33 项测试、Studio 69 项测试通过；两个开发分支均已推送远程备份。

## 4. 飞书 Base POC 阶段

当前账号建立了 `Open Knowledge Studio Raw Pipeline Test`，作为采集和运行控制面。2026-07-19 的全表快照共 7 条：

- 5 条 `Raw就绪`：公开静态 HTML、TXT 附件、PDF 附件、直接 PDF URL、公开浏览器 JS 快照；
- 1 条 `需授权`：微信公众号 Challenge，未生成 Raw；
- 1 条 `可重试失败`：Bilibili URL 返回 HTTP 412，未生成 Raw。

Worker 已实现：

- 领取记录、Run ID 和内容哈希；
- 本机跨进程 lease、超时回收和正常释放；
- 附件下载与哈希；
- 公开 HTTP、直接文件、浏览器快照和平台提取器路由；
- 成功、部分成功、需授权和可重试失败的诚实回写。

本机 lease 不是多主机分布式锁；飞书记录更新 API 没有被宣称为 CAS。

## 5. 已经成立的能力边界

可以诚实声称：

```text
已取得的 HTML / PDF / Office / 图片 / 音频 / MP4
  → 成熟解析器
  → content.md + evidence.jsonl + assets + quality report
  → 可验证 Raw
```

尚不能声称：

- 任意 URL 都能自动取得；
- 能绕过登录、CAPTCHA、付费墙或平台风控；
- Bilibili/YouTube 平台 URL 已成功形成 Raw；
- Raw 的机器文本等于人工校对后的正确内容；
- 当前新 Base 已经完成 Raw → Candidate → Wiki → 新任务召回闭环；
- 当前 recall 的 token overlap 等于真正的语义检索。

## 6. 历史阶段留下的关键经验

1. “工具已安装”不等于 URL 获取成功；资源获取层是当前主要缺口。
2. `valid=true` 只表示结构和证据一致，不表示 OCR/ASR/公式百分之百正确。
3. Raw 必须保存错误和失败，不能由 AI 补写看似合理的内容。
4. 平台媒体未长期保存时，只能记录来源引用，不能伪造媒体内容哈希。
5. 浏览器和飞书是入口，不能把 Cookie、Token 或完整登录态写入 Raw。
6. Wiki 设计必须通过真实使用迭代，不能先构建复杂本体。
7. 下一阶段的唯一主线是 `Capture → Raw → Candidate → Review → Wiki → Recall → Feedback → PR`。

## 7. 当前起点

后续执行统一以[自进化学习主 Loop](core-learning-loop-poc.md)为准。先用一条已成功生成 Raw 的公开文章跑完整闭环；完成验收后，再扩展到平台视频、群聊内容和 Obsidian 入口。
