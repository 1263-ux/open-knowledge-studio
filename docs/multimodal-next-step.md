# 多模态 Raw 下一阶段计划

> 更新日期：2026-07-14  
> 原则：Raw 只负责快速、诚实、可追溯地提取，不承担知识优化。

## 1. 已经成立的能力

第一阶段已经完成以下闭环：

```text
真实素材
  → 成熟提取器
  → Raw Markdown + 原子证据 + 必要资产
  → 基础校验
  → Open Knowledge Studio召回
```

已在本地视频、公开B站URL、音频、图片、扫描PDF、PPT、Word和HTML上完成真实验证。

当前边界：

- Raw记录机器实际提取出的内容，不总结、不润色、不做概念抽取；
- ASR、OCR和公式错误属于提取器输出，Raw不自动修正；
- Raw保留来源、时间戳、页码、bbox、原始资产和已知失败；
- 内容筛选、纠错、组织和知识进化交给后续Draft/Wiki流程。

## 2. 下一阶段只做三件事

### 2.1 让现有流程可复现

目标：换一台机器后，开发者可以按照文档安装依赖并跑出相同结构的Raw包。

任务：

- 固定并记录Watch Skill、ffmpeg、yt-dlp、faster-whisper、RapidOCR、MinerU和MarkItDown版本；
- 整理最小安装文档和运行命令；
- 增加轻量`doctor`检查，只报告依赖是否存在和版本是否可用；
- 为视频、图片、PDF和PPT各保留一个可公开提交的小型测试样本或fixture；
- 在Windows新环境完成一次从安装到召回的复现；
- 不建设任务队列、分布式服务或完整部署平台。

完成标准：

```text
新环境安装
  → doctor通过
  → 执行一个命令
  → 生成Raw包
  → validate通过
  → recall可找到
```

### 2.2 规范化Adapter接口

目标：以后接入新的成熟提取器时，不修改Raw核心协议。

只定义最小接口：

```text
输入：来源、输出目录、少量提取参数
输出：提取器原始结果、可读正文、原子证据、资产、警告
```

Adapter负责：

- 调用成熟提取器；
- 将结果映射到现有Raw v0.1结构；
- 保留提取器名称、版本和参数；
- 如实记录失败和缺失；
- 不评价内容价值；
- 不修正ASR、OCR或公式；
- 不决定是否进入Wiki。

第一批只整理已经真实运行的四个Adapter：

- Watch视频Adapter；
- RapidOCR图片Adapter；
- MinerU PDF Adapter；
- MarkItDown Office Adapter。

音频、Word和HTML已复用现有Watch与MarkItDown路线接入；没有为三种格式另造提取器。每次接入只证明“一条命令能够生成Raw并被基础校验”，不建设额外质量管理系统。

## 2.4 2026-07-14反馈闭环快照

| 能力 | 固定真实样本 | 当前结论 | 保留的真实限制 |
|---|---|---|---|
| PPT图片映射 | 15页省赛答辩PPT | 17/17引用映射，校验通过 | 版式语义仍以原PPT为准 |
| B站字幕路由 | 3个公开B站样本 + 本地Java视频 | `platform_caption/asr/none`路线已显式记录 | 现有公开样本无字幕，且在线请求遇到HTTP 412，真实平台字幕仍阻塞 |
| OCR阅读顺序 | 会议截图 | 85个OCR块按bbox行序输出，未改写文字 | 多栏、复杂排版仍只保留bbox供回查 |
| 音频ASR | Java课程60秒音频 | Watch/Whisper输出61段时间戳证据，校验通过 | ASR未人工纠错 |
| Word正文与图片 | 影海拾光项目计划书DOCX | 正文生成Markdown，6/6内嵌图片映射，校验通过 | 定位仅到文档级，分页版式以原Word为准 |
| HTML正文 | Open Knowledge Studio官网快照 | UTF-8中文、标题、列表、链接与代码块进入Markdown，校验通过 | 当前保存的是页面快照，不执行JavaScript、不抓取动态渲染结果 |

这里的“通过”只表示能力实际存在、产物完整且没有静默失败，不表示内容质量评级。

### 2.3 保住基础校验底线

保留现有`validate`，只检查机械完整性：

- 必需文件存在；
- JSON/JSONL可以解析；
- evidence具有kind、method和locator；
- Markdown和evidence引用的资产存在；
- 提取器交付数量与Raw打包数量一致；
- 空正文和完全失败不会被静默标记为成功；
- warning和失败原因能够被用户看到。

基础校验不做：

- ASR准确率评分；
- OCR内容评级；
- A/B/C/D质量等级；
- 自动切换更“聪明”的提取路线；
- 自动修正和自动摘要；
- 人工审核工作流。

## 3. 明确推迟的内容

在真实痛点出现前不做：

- 完整任务系统、状态机、幂等、重试和取消；
- Review Queue；
- Raw Schema v0.2；
- 动态质量路由；
- 多维质量评分；
- `verified.md`修正层；
- 服务端部署和SaaS；
- 飞书机器人和浏览器扩展；
- 自动Draft、Wiki和知识图谱；
- 为没有真实样本的格式提前写Adapter。

这些功能如果未来出现明确需求，应放在解析运行时、产品入口或Draft/Wiki层讨论，不应改变Raw“傻但诚实”的职责。

## 4. 下一步执行顺序

1. 建立开发反馈循环：真实样本 → 记录具体缺口 → 修复 → 同样本复跑；
2. 修复PPT图片关系映射；
3. 完善B站人工字幕、自动字幕和ASR回退路线；
4. 根据bbox恢复OCR行与阅读顺序，但不修正OCR文字；
5. 整理当前四个成熟提取器的环境和版本；
6. 实现`doctor`依赖检查；
7. 将当前统一脚本按四个Adapter做最小拆分；
8. 依次接入音频、Word和HTML；
9. 在固定真实样本上执行`Raw → validate → recall`；
10. 记录能力是否存在、实际输出和真实失败，不做等级评分。

## 5. Loop Engineering反馈机制

反馈日志只服务开发迭代，保存在被Git忽略的`.oks/feedback/`，不进入Raw Schema。

每个循环只记录：

- `cycle`：本轮要修复的具体能力；
- `sample`：保持不变的真实样本；
- `capability`：希望确认存在的能力；
- `status`：`gap`、`fix`、`verified`或`blocked`；
- `observation`：实际观察；
- `evidence`：命令、产物或错误位置；
- `next_action`：下一次最小修改。

示例：

```powershell
python scripts/multimodal_feedback.py record `
  --cycle ppt-image-map `
  --sample "影海拾光-省赛答辩终版-v2.pptx" `
  --capability "PPT图片关系映射" `
  --status gap `
  --observation "17个MarkItDown图片占位符无法映射"

python scripts/multimodal_feedback.py report
```

只有使用同一样本复跑并取得对应产物，才能记录为`verified`。

## 6. 下一阶段完成定义

以下条件全部满足即可结束，不增加额外平台建设：

- 当前四条提取路线可按文档安装和运行；
- 提取器缺失时能明确告诉用户缺什么；
- 每条路线至少有一个固定真实回归样本；
- 输出继续遵循Raw v0.1；
- 提取结果保持不可改写、可追溯；
- 断链、空结果和打包缺失不会静默通过；
- OKS可以召回可读Raw，并在需要时回到原子证据；
- Raw层没有新增知识判断、质量评级或审核职责。

一句话总结：

> 下一阶段不是让Raw变聪明，而是让已经做出来的多模态提取能力在新环境中也能稳定复现。
