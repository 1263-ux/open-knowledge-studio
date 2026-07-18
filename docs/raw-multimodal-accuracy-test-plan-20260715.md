# Raw 多模态准确性测试方案 v0.1

> 日期：2026-07-15  
> 阶段目标：真实素材经过多模态处理后，能够输出准确、完整、可追溯的 Raw Markdown。  
> 本轮不做：浏览器登录态、飞书机器人、SaaS、任务系统、自动 Draft/Wiki、知识图谱和部署形态。

## 1. 要回答的问题

本轮只回答四个问题：

1. 传统成熟提取器能提取出多少真实内容？
2. 千问、Gemini 等多模态大模型能否恢复传统工具遗漏或识别错误的内容？
3. 大模型是否同时引入漏行、改写、虚构和时间定位不准等新问题？
4. 在不牺牲证据链的前提下，哪种组合可以稳定生成 Raw Markdown？

“生成了看起来不错的 Markdown”不算通过。只有与人工真值比较后，才能声明准确性。

## 2. Raw 边界

实验继续遵循 `raw-multimodal/v0.1`：

- 传统提取结果、大模型候选和人工真值互不覆盖；
- 大模型不得摘要、解释或补充来源中不存在的内容；
- 每条文本必须能回到时间戳、页面、bbox、关键帧或原始资产；
- 无法确认的冲突标记为 `unresolved`；
- 未达到验收线时仍可生成 Raw，但必须标记 `partial`，不得伪装成 `complete`；
- 人工真值只用于评测，不写回机器原始结果。

## 3. 固定真实样本

### S1：中文技术口播

- 文件：`D:\测试\真实素材\e83b9acb335ee78eaaa5ffa460422e0e.mp4`
- 时长：约 147.70 秒
- 画面：448×960 竖屏
- 模态：人声、视频画面、可能的屏幕文字
- 目的：ASR 字符准确率、专业词、标点、时间定位和完整性

### S2：大学物理公式图

- 文件：`D:\测试\真实素材\2025年大学物理期末公式总结_1_小嘉资料铺_来自小红书网页版.jpg`
- 特征：双栏、正文密集、行内公式与独立公式混排
- 目的：中文正文、阅读顺序、公式识别、公式与解释文字绑定、遗漏检测

### S3：Java 编程录屏

- 文件：`D:\测试\Java-三元运算符.mp4`
- 模态：技术口播、IDE/代码画面、界面变化、屏幕文字
- 目的：ASR 技术词、屏幕变化帧、代码/OCR、语音与画面证据绑定

本轮不增加第四类素材。多镜头影视、多人会议、手写件和复杂表格留到本轮结论成立后再测。

## 4. 人工真值

准确性实验必须先建立真值，保存在被 Git 忽略的：

```text
.oks/ground-truth/raw-accuracy-v01/
├── speech/
│   ├── transcript.md
│   ├── segments.jsonl
│   └── glossary.txt
├── formula-image/
│   ├── reading-order.md
│   ├── text-blocks.jsonl
│   └── formulas.jsonl
└── java-screen/
    ├── visual-events.jsonl
    ├── code-text.jsonl
    └── glossary.txt
```

真值最低要求：

- 口播逐字校对全文，并记录专业词；
- 公式图按阅读顺序人工录入正文，并将每条公式规范化为 LaTeX；
- 编程录屏人工标记重要界面变化时间点、屏幕代码和关键术语；
- 每条真值具有 `source` 和定位，不只保存一份无时间轴的答案文本。

## 5. 对照路线

### 5.1 S1 中文技术口播

| 编号 | 路线 | 作用 |
|---|---|---|
| A0 | faster-whisper | 当前传统基线 |
| A1 | FunASR Paraformer，无热词 | 中文 ASR 候选 |
| A2 | 千问音频/Omni 能力 | 云端音频候选，具体模型由可用地域确定 |
| A3 | Gemini 原视频 | 同时观察音频、画面与时间定位 |

DeepSeek不单独承担语音识别。它只接收 A0–A3 的文本和定位，用于输出差异表，不允许凭语境生成新的“正确逐字稿”。

### 5.2 S2 公式图片

| 编号 | 路线 | 作用 |
|---|---|---|
| D0 | RapidOCR | 轻量正文基线 |
| D1 | PP-FormulaNet（公式裁剪） | 专用公式候选 |
| D2 | 千问视觉/OCR模型 | 中文、版面和公式综合候选 |
| D3 | Gemini 视觉 | 独立多模态候选 |

所有大模型必须返回块级结果：`kind`、`text/latex`、`bbox或区域编号`、`reading_order`。如果模型不能稳定返回 bbox，则至少引用预先切好的区域 ID，不能只交付一整篇漂亮 Markdown。

### 5.3 S3 Java 编程录屏

| 编号 | 路线 | 作用 |
|---|---|---|
| V0 | Watch + faster-whisper + screen-change + RapidOCR | 当前组合基线 |
| V1 | FunASR + screen-change + RapidOCR | 中文语音候选 |
| V2 | 现有关键帧 + 千问视觉 | 代码和屏幕语义候选 |
| V3 | Gemini 原视频或分段视频 | 音画联合候选 |

优先把已有关键帧交给视觉模型，而不是先把整个长视频交给所有模型。只有 V2 无法覆盖语音与画面关系时，再比较 V3 的整视频能力。

Gemini 官方视频接口会处理音频和视频，但默认视觉采样约为 1 FPS；千问接口允许控制视频抽帧 FPS。两者都可能遗漏快速界面变化，因此必须和本地 screen-change 证据比较。

## 6. 统一实验输出

每次调用写入隔离目录，不直接修改 Raw：

```text
.oks/experiments/raw-accuracy-v01/{sample}/{route}/{run-id}/
├── request-manifest.json
├── prompt.txt
├── upstream-response.json
├── candidate.md
├── evidence.jsonl
├── metrics.json
└── errors.json
```

`request-manifest.json`至少记录：

```json
{
  "sample_sha256": "...",
  "provider": "dashscope|gemini|local",
  "model": "精确模型ID",
  "requested_at": "ISO-8601",
  "prompt_sha256": "...",
  "parameters": {},
  "input_regions": [],
  "response_id": "...",
  "latency_seconds": 0,
  "usage": {},
  "estimated_cost": null
}
```

API Key只从环境变量读取：

```text
DASHSCOPE_API_KEY
GEMINI_API_KEY
DEEPSEEK_API_KEY
```

Key不得写入请求清单、响应、日志、Raw或Git。上传云端前必须确认素材允许第三方API处理。

## 7. 提示词约束

所有模型使用同一类“忠实提取”约束：

```text
只转写或提取输入中可直接观察到的内容。
不得总结、解释、改写、补全或纠错。
看不清的内容输出 [unclear]，不得猜测。
保持原始阅读顺序和公式结构。
每个结果必须引用时间戳、区域ID或bbox。
严格按照给定JSON Schema输出。
```

模型恢复错误时另起候选，不允许用新结果覆盖原始提取。

## 8. 指标

### 8.1 ASR

- `CER`：中文字符错误率；
- `critical_term_accuracy`：专业词准确率；
- `omission_rate`：漏句比例；
- `hallucination_rate`：来源中不存在的文本比例；
- `timestamp_coverage`：具有时间定位的文本比例；
- `timestamp_error`：和人工标注的时间偏差。

### 8.2 公式与图片

- `text_CER`：正文字符错误率；
- `formula_exact_match`：规范化 LaTeX 完全匹配率；
- `formula_symbol_accuracy`：符号级准确率；
- `formula_recall`：人工真值公式中被提取出的比例；
- `reading_order_accuracy`：双栏阅读顺序正确率；
- `unsupported_content_count`：模型虚构块数量；
- `locator_coverage`：块级区域定位覆盖率。

### 8.3 视频视觉

- `visual_event_recall`：人工标注重要变化点被证据帧覆盖的比例；
- `redundant_frame_ratio`：重复、无信息帧比例；
- `code_token_accuracy`：代码和界面关键文字准确率；
- `audio_visual_link_coverage`：需要音画联合理解的事件是否同时具有时间和帧证据。

### 8.4 Raw 包机械完整性

- `validate` 必须通过；
- 必需文件存在率 100%；
- Markdown资产断链数 0；
- 成功提取证据的 locator 覆盖率 100%；
- 提取器交付块与 Raw 打包块数量一致；
- 静默遗漏数 0；无法提取的内容必须进入 warning。

## 9. 两阶段验收

### 阶段A：基线校准

第一次不设置漂亮的准确率目标。完成全部路线并计算真实指标，确认错误分布和调用成本。没有真值的结果不得用主观观感宣布胜出。

### 阶段B：候选准入

完成校准后，暂定最低门槛：

| 能力 | 准入条件 |
|---|---|
| 清晰中文口播 | CER ≤ 5%，专业词准确率 ≥ 95%，无整句静默遗漏 |
| 公式图 | 公式召回率 ≥ 95%，规范化公式完全匹配率 ≥ 90%，阅读顺序 ≥ 98% |
| 编程录屏 | 重要视觉事件召回率 ≥ 95%，关键代码/术语准确率 ≥ 95% |
| 所有Raw包 | locator覆盖100%，资产断链0，虚构证据0，`validate`通过 |

门槛是“自动标记为本样本通过”的条件，不代表所有现实输入都已达到同样准确率。低于门槛时仍保留结果，但状态必须是 `partial/unverified`。

## 10. 选择规则

候选进入 Raw 主路线必须同时满足：

1. 在固定真值样本上比当前基线有明确提升；
2. 不以显著增加漏行或虚构换取表面可读性；
3. 能输出或映射来源定位；
4. 能保留原始响应和精确模型信息；
5. 失败时可以回退到当前本地路线；
6. 成本和时延可以被记录；
7. 同样本重复运行结果基本稳定。

最终可能不是“一个模型全部胜出”，而是：

```text
口播ASR：FunASR或千问
公式文档：千问视觉或Gemini + 专用公式模型
编程录屏：本地screen-change + 视觉模型关键帧理解
文本差异：DeepSeek只做冲突整理
```

## 11. 执行顺序与停止条件

1. 为 S1–S3 建立人工真值；
2. 固定本地基线，不改参数反复追分；
3. 接入千问，先跑公式图片，再跑口播/编程关键帧；
4. 接入 Gemini，先跑同一公式图片，再跑口播视频；
5. DeepSeek生成候选差异表，但不参与判定真值；
6. 自动计算指标，生成对照报告；
7. 只将胜出的能力封装为可选 Raw Adapter；
8. 用同样本重新执行 `Raw → validate → recall`。

满足以下条件即停止本轮，不继续扩大系统：

- 三个固定样本均能输出结构完整的 Raw Markdown；
- 每个关键内容单元可追溯；
- 准确率有人工真值和指标支持；
- 模型失败时本地路线仍可用；
- 已明确哪些路线是默认、候选和回退；
- 没有进入登录态、机器人、Wiki和部署开发。

## 12. 本轮交付物

- 三套人工真值；
- 本地、千问、Gemini对照结果；
- 自动指标脚本；
- 一份准确性对照报告；
- 可选的大模型候选Adapter；
- 三个通过校验且能召回的 Raw Bundle；
- 对无法达到门槛的能力给出明确失败记录，不用包装性语言宣布完成。
