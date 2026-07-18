# Raw 多模态组件选型实验记录（2026-07-15）

> 目标：针对第一阶段已暴露的 ASR 技术词、OCR 噪声、PDF 公式和关键帧问题，复用成熟组件进行同样本对照。  
> 边界：实验结果只作为候选证据，不覆盖现有 Raw，不自动纠错、不摘要、不进入 Wiki。  
> 判断原则：没有人工真值时，只报告观察到的差异，不声称整体准确率提高。

## 1. 实验前项目进度

第一阶段主链已经做到：

- 本地视频、图片、PDF、PPT 和 B 站公开链接能够进入统一适配入口；
- 视频可保留 ASR 时间戳、关键帧、OCR 和来源证据；
- 图片、文档可保留页码、坐标、原始资产和提取器交付结果；
- Raw Markdown 可以被现有 OKS ingest / recall 召回；
- 已有 53 项自动化测试通过；
- Raw 边界保持为“提取、排序、打包、暴露失败”，没有加入知识判断。

当前不是“完全无法提取”，而是已有可运行骨架，但部分上游结果还不够准确。本轮实验的任务是判断哪些成熟组件值得接成第二候选，而不是继续自研底层模型。

## 2. 实验方法

本轮新增三个隔离的实验探针：

- `scripts/experiments/funasr_probe.py`：运行 FunASR，并原样保存模型输出、配置和耗时；
- `scripts/experiments/ppstructure_probe.py`：尝试 PP-StructureV3 版面/OCR 流水线；
- `scripts/experiments/keyframe_probe.py`：在不重复运行 ASR/OCR 的前提下比较两种场景检测策略。

实验文件写入被 Git 忽略的 `.oks/experiments/20260715-component-selection/`，不会污染 Raw。生产默认值也未改变。

## 3. ASR：faster-whisper 与 FunASR

样本为 60 秒 Java 三元运算符教学音频，CPU 推理。

| 路线 | 可观察结果 | 时间定位 | 推理耗时 | 本轮判断 |
|---|---|---|---:|---|
| faster-whisper small 基线 | “键盘录录”3 次，“键盘录入”0 次；“三元运算符”7 次 | 56 个语句段 | 已有基线 | 时间段易直接展示，但技术词有错 |
| FunASR Paraformer，无热词 | “键盘录入”3 次；“三元运算符”6 次；另有 1 次“三元元算” | 547 个细粒度时间区间 | 约 3.38 秒；缓存模型加载约 22.29 秒 | 最有价值的新候选 |
| FunASR Paraformer，通用热词 | “键盘录入”3 次；“三元运算符”3 次，同时出现“元元运算符”2 次 | 547 个细粒度时间区间 | 约 3.41 秒 | 热词在该配置下产生副作用 |

首次下载和加载 FunASR 相关模型约耗时 334 秒，模型资产合计超过 1 GB；后续命中缓存后明显变快。

结论：

1. FunASR 对中文技术口播有真实补充价值，值得保留为中文 ASR 候选；
2. 不能根据几个关键词宣布其整体优于 faster-whisper，因为尚无逐字人工真值；
3. 不能把任意词表直接传给普通 Paraformer 并默认更准。本样本中热词使核心术语变差；
4. 当前最合理的下一步是建立 2 至 3 分钟人工校对真值，再计算 CER，并决定是否将 FunASR 作为中文默认或仅作为第二候选；
5. 若未来需要热词，应测试官方上下文化/热词模型及权重，而不是盲目扩大词表。

FunASR 官方实现明确支持时间戳和热词能力，但具体模型与热词方式必须匹配：<https://github.com/modelscope/FunASR>。

## 4. OCR/版面：RapidOCR 与 PP-StructureV3

目标是验证 PP-StructureV3 能否在当前 Windows CPU 环境中替代“整屏 OCR 原子块”，提供更好的布局和阅读顺序。

实际结果：

1. 首次运行发现 `paddlex[ocr]` 依赖未安装；
2. 在隔离环境补齐依赖后，版面检测、文本检测和识别模型均成功下载；
3. 推理阶段失败于 Paddle oneDNN/PIR：`ConvertPirAttribute2RuntimeAttribute not support ArrayAttribute<DoubleAttribute>`；
4. 尝试关闭 MKLDNN 后仍失败；
5. 当前机器没有可用 NVIDIA GPU，无法切换 GPU 路线验证。

这是上游 Windows CPU 运行时兼容性问题，而不是素材解析失败。Paddle 官方仓库已有同类问题记录：<https://github.com/PaddlePaddle/Paddle/issues/77340>，PaddleOCR 也有相同错误的持续讨论：<https://github.com/PaddlePaddle/PaddleOCR/discussions/17350>。

本轮决策：

- RapidOCR 继续作为轻量默认 OCR；
- PP-StructureV3 标记为“候选阻塞”，不进入生产依赖；
- 不在本轮继续排列组合 Paddle 版本，避免把时间消耗在上游运行时维护上；
- 浏览器扩展/截图入口优先做用户选区和正文区域捕获，因为减少输入噪声比事后猜阅读顺序更稳定；
- 若以后确有复杂文档版面需求，再用固定 Docker/Linux 环境复测 PP-StructureV3 或 MinerU，不要求每个用户本地安装整套重依赖。

## 5. PDF 公式：MinerU 与 PP-FormulaNet

复用前一轮已经完成的真实候选结果，不重复消耗模型推理：

- 对 3 个 MinerU 已定位的独立公式块，PP-FormulaNet_plus-M 在约 4.09 秒内给出第二候选；
- `sin²θ + cos²θ = 1` 两路语义一致，专用公式模型输出更紧凑；
- MinerU 的 `\mid x+y` 被第二候选识别为 `x+y`；
- MinerU 的不确定根式被第二候选识别为 `2\sqrt{p}`；
- 另一真实裁剪中，专用公式模型避免了 MinerU 正文曾出现的 `\rceil`、`\ddagger` 和重复 `\perp`。

限制仍然明确：只覆盖 MinerU 已经定位并导出图像的独立公式块，行内公式并未全覆盖；两路候选冲突时 Raw 不替用户选择答案。

本轮决策：保留 MinerU 主结果，同时将 PP-FormulaNet 作为可追溯第二候选。自动裁决和公式语义校正不属于 Raw。

## 6. 关键帧：通用场景与屏幕变化路线

对两个真实视频各取前 60 秒，只比较检测边界，不重复跑 ASR 和 OCR。

| 样本 | AdaptiveDetector | 屏幕变化检测 | 观察 |
|---|---:|---:|---|
| Java 编程录屏 | 2 段，约 14.41 秒 | 4 段，约 5.92 秒 | 屏幕路线捕获到 56 至 57 秒附近的连续变化 |
| 口播视频 | 0 段，约 14.82 秒 | 4 段，约 8.77 秒 | 屏幕路线会把镜头/人物运动当作变化 |

结论：

- 视频类型路由是必要的；一套检测器不能覆盖录屏、口播和影视剪辑；
- `screen` 只适合屏幕录制，不能作为所有视频默认值；
- 口播的知识主要来自音频，视觉侧可以低频取证，不需要制造大量关键帧；
- 当前样本没有真实多镜头影视素材，因此 `shots` 路线仍不能宣称已经充分验证；
- 检测到更多帧不等于信息更完整，后续必须使用人工标注的变化点计算召回和冗余。

## 7. 本轮组件决策

| 问题 | 当前默认 | 实验候选 | 决策 |
|---|---|---|---|
| 中文口播 ASR | faster-whisper | FunASR Paraformer | 保留候选；完成小真值集后再决定默认 |
| 技术热词 | initial prompt / 候选输出 | FunASR 热词 | 不默认启用，先验证模型与权重 |
| 普通图片 OCR | RapidOCR | PP-StructureV3 | RapidOCR 保持默认；PP-Structure 当前阻塞 |
| 独立 PDF 公式 | MinerU | PP-FormulaNet | 双候选并存，不自动裁决 |
| 录屏关键帧 | screen change | AdaptiveDetector | 继续按 `screen` 路由 |
| 口播关键帧 | 低频视觉证据 | screen change | 不使用 screen 路由，以音频为主 |

## 8. 当前完成度与下一实验

已经可以确认：

- Raw Pipeline 已经能接收现实素材并生成可追溯 Markdown；
- 已从单一路线发展到“高风险模态可以保留成熟组件的第二候选”；
- 公式、中文 ASR、录屏关键帧均找到了能实际运行的改进路线；
- 未把候选模型的结果伪装成真值，也未把 Raw 变成知识精炼层；
- 当前全量测试为 `53 passed`。

仍不能确认：

- 任意视频、任意文档都能高保真解析；
- FunASR 整体错误率低于 faster-whisper；
- 关键帧变化点召回率达到生产要求；
- 行内数学公式已完整恢复；
- PP-StructureV3 可在当前 Windows CPU 环境稳定部署。

下一轮只做两个小而硬的实验：

1. 建立一个 2 至 3 分钟中文技术口播人工真值集，对 faster-whisper、FunASR 无热词和正确的上下文化热词模型计算 CER；
2. 建立三个短视频变化点真值：录屏、口播、多镜头各一个，对 `screen`、`shots` 和低频均匀证据策略计算漏检与冗余。

在这两个真值实验完成前，不继续扩张新的重量级提取器，也不改 Wiki 设计。
