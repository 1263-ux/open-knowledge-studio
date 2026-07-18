# Raw Inbox 真实闭环验证报告（2026-07-16）

## 1. 验证目标

本轮不继续扩大 Raw 架构，而是按“先跑通、再真实试用”的要求，验证下面这条链路是否真的成立：

```text
飞书多维表格表单
  → 用户提交文字与附件
  → 读取记录并下载附件
  → 视频/图片多模态提取
  → Raw Markdown 与证据包
  → validate
  → Open Knowledge Studio recall
```

Raw 的边界保持不变：只保存来源、机器提取结果、定位信息、原始资产和失败事实；不做摘要、知识判断、自动纠错或 Wiki 生成。

## 2. 测试环境与素材

- 代码仓库：`D:\XiangMuLuoDi\Clone\1263-ux\claude-code-knowledge-studios`
- 飞书 Base：`Open Knowledge Studio 每日链接入料`
- 数据表：`每日链接与思考`
- 表单：`每日知识采集`
- 测试记录 ID：`rec27NGqTrWEmV`
- 视频：147.70 秒、448×960、H.264、有音频；内容为手机录屏中的 3 倍速 Agent 技术口播
- 图片：大学物理期末公式长图
- 提取环境健康检查：Watch、RapidOCR、faster-whisper、yt-dlp、MarkItDown、MinerU、PaddleOCR、ffmpeg 均可用

测试记录只用于本轮验证，没有修改 Base 中原有记录。

## 3. 实际执行结果

### 3.1 飞书入口与附件往返

已完成：

1. 通过真实表单创建一条记录；
2. 上传视频与公式图片到附件字段；
3. 以用户身份读取该条记录；
4. 从 Base 下载两个附件到本地 inbox；
5. 对原文件与下载文件计算 SHA-256。

哈希核验结果：

| 素材 | 大小 | SHA-256 往返一致 |
|---|---:|---|
| 公式图片 | 299,685 B | 是 |
| 口播视频 | 11,351,986 B | 是 |

因此，飞书表单可以作为真实移动端 Raw Inbox，附件上传和下载没有发生字节损坏。

### 3.2 公式图片 Raw

输出目录：`.oks/intake/feishu-rec27NGqTrWEmV-formula-image`

- 状态：`partial`
- `validate`：通过
- 证据：154 条 OCR evidence
- 资产：保留原图
- 产物：`metadata.json`、`content.md`、`visual.md`、`evidence.jsonl`、`quality-report.json` 等
- 召回验证：查询“角动量 转动惯量”能够命中该 Raw

真实质量结论：普通中文和部分符号可检索，但密集公式存在字符误识别、公式拆散、阅读顺序混乱等问题。当前结果适合作为“可定位的机器证据”，不能当作可直接引用的正确公式文本。

### 3.3 3 倍速口播视频 Raw

原始输出目录：`.oks/intake/feishu-rec27NGqTrWEmV-speech-video`

首轮结果：

- 原始 Whisper ASR：0 段；
- 关键帧与画面 OCR：247 条 evidence；
- 系统明确写入“没有取得字幕或 ASR 逐字稿”，没有伪造语音内容；
- `validate` 通过，状态为 `partial`。

失败原因不是文件损坏，而是素材本身为 3 倍速录屏，语速超出当前 ASR 路线的可靠工作区间。

恢复实验一：将前 30 秒音频放慢 3 倍后，faster-whisper 恢复出 52 段，但技术词和中文错误较多，不能视为可靠逐字稿。

恢复实验二：针对画面底部烧录字幕，以 0.5 秒间隔进行 ROI OCR：

- 视频时长：147.67 秒；
- 耗时：472.37 秒；
- OCR observations：294；
- 合并后候选字幕：272 段；
- 能恢复 `agent`、`workflow`、`自主性`、`memory`、`tools`、`agent loop` 等核心词；
- 仍存在漏字、错字、相邻字幕拼接和短字幕漏采。

2 秒采样仅得到 74 段，明显漏掉高速字幕，说明固定低频采样不适合该类素材。

恢复后的派生 Raw 位于：`.oks/intake/feishu-rec27NGqTrWEmV-speech-video-recovered`

- 状态：`partial`
- `validate`：通过
- evidence：519 条（272 条字幕候选 + 8 帧 + 239 条画面 OCR）
- 原始 ASR 失败被保留，没有被候选字幕静默覆盖；
- 召回验证：查询“workflow agent 自主性”能够命中该 Raw。

## 4. 召回联调

为了避免仓库中其他 Raw 干扰判断，本轮建立隔离知识库：

`.oks/e2e-kb/rec27NGqTrWEmV`

其中只放入上述两个测试 Raw，Wiki 保持为空。

| 查询 | 结果 |
|---|---|
| `workflow agent 自主性` | 命中 `raw/misc/agent-speech-video/content.md` |
| `角动量 转动惯量` | 命中 `raw/misc/physics-formula-image/content.md` |

这证明提取结果不只是生成了文件，而是已经进入现有 OKS 的 episodic recall 路径。

回归中还发现 Windows GBK 终端无法显示公式下标 `₀`，导致 Rich 输出 `UnicodeEncodeError`。本轮已在 CLI 启动时为 Windows 输出流配置 UTF-8，并增加回归测试；修复后公式 Raw 可正常显示。

## 5. 本轮证明了什么

已经真实证明：

1. 飞书表单可以接收用户文字、思考、知识域、评级和多模态附件；
2. Base 附件可以完整下载，文件内容与原件一致；
3. 图片和视频可以被现有提取器转成符合 `raw-multimodal/v0.1` 的 Raw Bundle；
4. ASR 完全失败时，Raw 会诚实暴露失败，而不是输出虚假正文；
5. 烧录字幕 OCR 可以作为特殊视频的候选恢复路线；
6. 两类 Raw 都能通过结构校验并被现有 recall 找到；
7. Windows 中文环境下的 Unicode 召回输出已补齐。

当前核心阶段目标“多模态信息处理并抽取为 Raw Markdown”已经从本地样例推进到真实飞书入口的端到端原型。

## 6. 仍然存在的真实缺口

### 6.1 Feishu Adapter 尚未产品化

当前是人工编排：读取记录、下载附件、调用提取命令、复制到隔离知识库。尚未形成一条 `raw-inbox ingest` 命令，也没有轮询或事件触发。

另外，附件下载后被现有 extractor 当作 `platform=local`，Raw 元数据没有保留 Base、table、record、附件 token、用户思考等飞书来源链。下一个最小工程增量应是 Feishu Adapter，而不是继续增加新的底层提取器。

### 6.2 Base 回写权限不足

读取、表单提交、附件上传和下载均成功，但回写测试记录的“状态/总结”字段被资源权限拒绝（飞书错误 `91403`）。当前测试记录仍未自动标记为已处理。这是飞书资源权限/角色配置缺口，不是 Raw 提取失败。

### 6.3 高速视频恢复成本高

147.67 秒视频的 0.5 秒字幕 OCR 耗时 472.37 秒，约为视频时长的 3.2 倍。该路线只能作为条件触发的 fallback：`ASR 为空 + 检测到烧录字幕`。不应默认对所有视频启用。

### 6.4 准确性仍受提取器上限约束

- 公式：OCR 只能支持检索与定位，不能保证数学语义正确；
- 高速字幕：可恢复核心信息，但仍需人工核对；
- 当前未接入 Qwen/Gemini 等视觉模型，因此没有验证“大模型恢复是否显著优于 OCR”。

## 7. 下一步建议：先试用，不继续扩架构

建议进行 3–7 天 dogfood：每天通过这张飞书表单提交 1–3 条真实素材，覆盖口播、截图、普通文档和至少一条困难素材。每条只记录四件事：

1. 是否成功进入 Raw；
2. 是否保留来源和定位；
3. 第二天能否通过自然语言召回；
4. 哪一步真的需要人工介入。

试用期间只做两个工程增量：

1. `Feishu Inbox Adapter`：把记录上下文与附件交给现有 Raw Pipeline，并保留飞书 provenance；
2. 条件恢复接口：ASR 为空时允许显式选择烧录字幕 OCR 或外部多模态模型，候选结果必须与原始失败并存。

Word、HTML、登录态视频平台、自动 Wiki、复杂质量评分和完整任务系统暂不进入本轮。先观察真实使用中最频繁、最痛的失败，再决定下一条开发路线。

## 8. 最终判断

结论不是“已经生产可用”，也不是“只做了一个演示”。更准确的判断是：

> 真实世界的信息已经能够从飞书入口进入 Raw Markdown，并被现有知识库召回；系统在失败时保持诚实，但入口自动化、来源链和困难素材准确性仍需下一轮真实试用验证。

