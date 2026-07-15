# Raw 抽取准确性恢复方案调研

> 日期：2026-07-15
> 范围：公式、ASR、OCR、关键帧
> 暂不进入：登录态、飞书机器人、Wiki加工、LLM自由纠错。

## 1. 目标重新表述

Raw 可以保留粗糙的机器输出，但面向召回的 `content.md` 不能长期把明显误识别当作没有疑问的文本。解决方向不是让LLM自由改写，而是：

```text
原始素材
  → 多个成熟提取器/同一提取器的上下文增强
  → 时间、页面、bbox对齐
  → 一致内容直接采用
  → 分歧内容保留候选和原始证据
  → content.md择证据呈现，不生成来源中不存在的内容
```

必须继续保留：

- 提取器原始输出不可改写；
- 每个候选结果的 `method`、版本和参数；
- 页码、时间戳、bbox和原始素材定位；
- 无法判定时明确保留不确定性，而不是猜一个答案。

准确性验收使用开发基准，不在每份Raw中引入A/B/C质量评级。

## 2. 市面方案结论

### 2.1 PDF与公式

#### 当前基线：MinerU

MinerU继续适合作为结构与资产基线：能够输出Markdown、页面元素、图片和公式候选。当前问题不是没有公式，而是复杂公式的LaTeX候选存在语义错误。

官方仓库：<https://github.com/opendatalab/MinerU>

#### 候选一：PP-StructureV3

PP-StructureV3包含版面检测、OCR、表格、公式和阅读顺序模块，并能输出Markdown。它适合做第二条本地文档候选路线，尤其可只重跑公式密集页，不必替换全部PDF流程。

- 介绍：<https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PP-StructureV3.html>
- 官方仓库：<https://github.com/PaddlePaddle/PaddleOCR>

#### 候选二：PaddleOCR-VL

PaddleOCR-VL是面向文档解析的视觉语言模型，官方强调文本、表格、公式、图表和复杂真实拍摄场景。它值得进入对比实验，但当前机器没有可见NVIDIA GPU，不应未经实测直接替换本地CPU主线。可以先使用官方体验/API或少量页面测试其质量上限。

官方仓库：<https://github.com/PaddlePaddle/PaddleOCR>

#### 候选三：Mathpix

Mathpix是付费云端STEM OCR，支持图片、PDF、印刷/手写数学、表格和Mathpix Markdown。它适合用少量公式页建立商业方案上限，不适合默认发送所有私人文档；测试前必须确认费用、数据保留和用户授权。

官方文档：<https://docs.mathpix.com/>

#### 其他可复用候选

- Marker：PDF转Markdown/JSON，结合Surya完成OCR、布局和阅读顺序；<https://github.com/datalab-to/marker>
- Surya：OCR、布局、阅读顺序和表格识别；<https://github.com/datalab-to/surya>
- Texify：专门把数学图片转为LaTeX/Markdown；<https://github.com/VikParuchuri/texify>
- Docling：开放源代码的文档转换和PDF理解；<https://github.com/docling-project/docling>

当前不应同时安装全部项目。第一轮只比较 MinerU、PP-StructureV3，再用 Mathpix 或 PaddleOCR-VL 对少量错误页做上限参考。

#### 推荐组合

```text
数字PDF
  ├─ 原生文本层：优先保留原生文本与坐标
  ├─ MinerU：结构、资产、公式候选A
  └─ 公式错误页
       ├─ PP-StructureV3/公式模型：候选B
       └─ 可选Mathpix：商业上限候选C
```

只对公式区域追加候选，避免整份PDF重复跑多个重型模型。候选一致时采用；候选冲突时在 `content.md` 标记待核验并链接原页/公式裁剪图。

### 2.2 中文ASR与技术词

#### 当前基线：faster-whisper small

当前Watch Skill根据机器资源选择 `small`，启用了VAD，但没有把项目热词传入 `faster-whisper`。faster-whisper本身支持 `hotwords`、`initial_prompt`、word timestamps和VAD，因此第一步可以先复用现有引擎，不必立即换模型。

官方实现：<https://github.com/SYSTRAN/faster-whisper>

#### 候选：FunASR

FunASR的Paraformer路线提供中文ASR、时间戳、VAD、标点和热词能力。对“键盘录入、三元运算符、Scanner”等中文技术词，它比无上下文的通用Whisper更值得实测。

官方仓库与示例：<https://github.com/modelscope/FunASR>

SenseVoice也支持中文/粤语/英文等识别和CTC时间对齐，可作为后续口音或音频事件需求的候选，不需要第一轮同时接入。

官方仓库：<https://github.com/FunAudioLLM/SenseVoice>

#### 推荐组合

```text
音频
  ├─ Whisper基线：VAD + 时间戳 + 显式语言
  ├─ 上下文增强：hotwords / initial_prompt
  └─ 中文技术内容：FunASR Paraformer + 同一组热词
          ↓
      按时间段对齐两路结果
```

不按模型自报置信度直接决定真伪。先用人工金标准计算中文字符错误率和关键术语召回，再决定默认路线。两路冲突时保留候选，不用LLM猜词。

WhisperX主要解决词级时间对齐和说话人分离，不直接解决“键盘录入”这类词识别错误，当前单人口播不应优先引入。

### 2.3 OCR噪声和阅读顺序

#### 根因

RapidOCR在整张屏幕上忠实识别所有可检测文字，但它不知道哪些是正文、菜单、状态栏、按钮或装饰。单纯提高置信度阈值会同时删除部分真实小字，不能作为最终方案。

#### 可复用方案

1. **用户区域优先**：图片上传允许用户给出裁剪区域；浏览器未来直接传正文DOM或用户选区。这是最可靠、成本最低的降噪方式。
2. **版面检测**：PP-DocLayout/PP-StructureV3可以识别标题、正文、页眉页脚、表格、公式、图片等区域，并恢复复杂文档阅读顺序。
3. **OCR升级对比**：用官方PP-OCR当前模型与RapidOCR跑同一批中文截图，不直接假设新模型一定更好。
4. **原子证据不删除**：整屏OCR块仍写入 `evidence.jsonl`；`content.md`只编排用户区域或版面正文区域，噪声仍可回查。

官方布局检测文档：<https://www.paddleocr.ai/main/en/version3.x/module_usage/layout_detection.html>

需要区分“文档页面”和“软件界面截图”。文档版面模型不一定理解IDE、浏览器和会议软件控件，因此软件截图第一优先仍应是用户选区/固定内容区域，而不是盲目套论文版面模型。

### 2.4 视频关键帧

#### 当前失败原因

Watch Skill已经复用PySceneDetect，但固定使用默认 `ContentDetector`。只有检测到至少两个场景时才使用场景帧，否则回退均匀采样。`ContentDetector`适合明显镜头切换，IDE录屏、PPT逐步变化和板书通常没有硬切，因此真实样本全部为 `uniform` 是符合其算法特点的结果。

项目旧的 `media_ingest.py` 已包含 `AdaptiveDetector` 实现，可以复用，不需要重新实现基础场景检测。

PySceneDetect官方的 `AdaptiveDetector` 使用相邻帧变化的滚动平均，而不是固定阈值：<https://www.scenedetect.com/docs/latest/api/detectors.html>

TransNetV2是成熟的镜头边界模型，适合影视/短视频硬切和渐变镜头，但不是IDE文字变化检测器，第一轮不引入其TensorFlow依赖。

官方仓库：<https://github.com/soCzech/TransNetV2>

#### 推荐透明路由

```text
--video-profile speech
  → ASR优先，少量均匀帧

--video-profile shots
  → PySceneDetect AdaptiveDetector

--video-profile screen
  → 低频采样（例如1fps）
  → 内容区域dHash/彩色哈希/SSIM变化
  → OCR文字变化辅助
  → 近重复帧去重
```

第一版由用户或测试用例显式选择 profile，避免先建设复杂自动分类器。OpenCV已有多种图像哈希实现，可直接复用：<https://docs.opencv.org/master/d4/d93/group__img__hash.html>

Watch当前使用灰度pHash去重；其自身代码也注明纯颜色状态变化可能不可见。屏幕录制路线应增加彩色变化或区域差异信号，不能只调整SceneDetect阈值。

## 3. 如何让Raw回归准确而不越界

建议只增加“证据对齐和选择”，不增加生成式纠错：

```text
extractor outputs（不可变）
  ├─ candidate A
  ├─ candidate B
  └─ source crop / audio interval
          ↓
alignment（时间/页码/bbox）
          ↓
content.md
  ├─ 一致：呈现一致文本并回链证据
  ├─ 明显优胜：呈现经金标准验证过的优先路线
  └─ 冲突：保留候选或不确定标记，要求回看证据
```

不能做：

- 让LLM根据常识重写公式或技术词；
- 因为某一路置信度高就删除其他候选；
- 把拼写检查结果伪装成原始听写；
- 在没有原页/原音频证据时自动“修成看起来正确”的文本。

可以做：

- 在ASR调用前注入用户提供的课程/项目热词；
- 使用字幕OCR与ASR按时间对齐；
- 对公式框调用第二个专用识别器；
- 按用户区域和版面区域编排OCR；
- 将所有候选保留在原子证据中。

## 4. 必须建立小型金标准

不存在一个开源工具能保证所有真实素材自动准确。要判断复用项目是否真的改善当前样本，必须先做最小人工真值：

| 能力 | 最小金标准 | 开发指标 |
|---|---|---|
| 公式 | 从错误PDF选择20-30个公式，人工录入正确LaTeX | 规范化精确匹配、可渲染性、关键符号正确 |
| ASR | 校对现有60秒Java音频 | 中文字符错误率、关键术语召回、时间覆盖 |
| OCR | 标注会议截图正文区域和关键文本行 | 正文字符错误率、噪声块数、阅读顺序 |
| 关键帧 | 标出IDE/PPT真实内容变化时间点 | 变化点覆盖、重复帧、无意义帧 |

这些指标只用于 `.oks/feedback/` 开发对比，不写进每份Raw的业务Schema。

## 5. 最小执行方案

### 实验一：ASR热词与FunASR对照

同一条60秒Java音频运行：

1. 当前Whisper small；
2. Whisper small + 热词/initial prompt；
3. FunASR Paraformer + 同一热词。

先解决“键盘录入、三元运算符”等可观测错误。该实验依赖和耗时都低于文档VLM，优先级最高。

### 实验二：OCR区域与布局对照

同一张会议截图运行：

1. 当前整屏RapidOCR；
2. 人工正文ROI + RapidOCR；
3. PP-DocLayout/PP-StructureV3区域 + RapidOCR或PP-OCR。

先证明“区域选择”能否显著减少菜单和状态栏噪声，再决定是否接入重型版面环境。

### 实验三：关键帧双路线

保留Watch作为调用和打包主干：

1. 影视/明显转场样本测试 `AdaptiveDetector`；
2. IDE/PPT录屏测试低频采样 + 区域哈希变化 + OCR文本变化；
3. 与当前均匀采样比较变化点覆盖。

### 实验四：公式候选对照

最后处理最重的公式路线：

1. 从现有PDF裁剪错误最明显的2-3页；
2. MinerU、PP-StructureV3跑同一页；
3. 可选Mathpix或PaddleOCR-VL建立上限参考；
4. 只在真实改善后增加公式区域回退Adapter。

## 6. 当前建议

优先顺序：

```text
ASR热词/FunASR
  → OCR区域化
  → 屏幕录制关键帧
  → 公式多引擎对照
```

原因不是公式不重要，而是当前机器没有NVIDIA GPU，公式VLM和完整文档模型是最重、最慢、最需要外部API权衡的一项。先用三组低成本实验建立“证据对齐 + 候选择优”机制，再把相同机制用于公式。

一句话结论：

> 市面上有成熟零件，但没有万能提取器。最可靠的复用方式是按模态选择强项工具，用人工金标准证明它确实改善当前样本，再通过证据对齐把结果写回Raw，而不是让LLM替原始材料猜一个更顺眼的答案。
