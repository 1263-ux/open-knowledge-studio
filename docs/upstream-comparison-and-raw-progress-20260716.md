# Open Knowledge Studio 上游同步与 Raw 多模态开发进展报告

> 报告日期：2026-07-16  
> 报告对象：Open Knowledge Studio 项目组  
> 开发主题：试做多模态信息处理，将现实世界素材抽取为可追溯的 Raw Markdown  
> 当前开发目录：`D:\XiangMuLuoDi\Clone\1263-ux\claude-code-knowledge-studios`

---

## 1. 执行摘要

本阶段没有改造 Open Knowledge Studio 的 Wiki 核心，也没有引入自动知识判断、自动摘要或自动纠错，而是围绕一个更小、更基础的问题开展开发：

> 如何把视频、音频、图片、PDF、PPT、Word、网页等现实世界素材，诚实、可追溯地搬运为 Agent 可读取、可召回的 Raw Markdown。

目前已经完成一套可运行的 Raw 多模态原型：

- 建立统一的 Raw Bundle v0.1 数据结构；
- 接入和复用 Watch、faster-whisper、RapidOCR、MinerU、MarkItDown、PaddleOCR、ffmpeg 等成熟组件；
- 支持本地视频、音频、图片、PDF、PPT、Word和静态 HTML 的抽取与打包；
- 保留来源、时间戳、页码、坐标、截图、原始文件及质量报告；
- 与 OKS 现有 `validate`、`ingest`、`recall` 链路完成联调；
- 使用真实视频、公式 PDF、Office 文档、网页和飞书多维表格收件箱进行了端到端验证；
- 建立了失败暴露、人工反馈、候选结果对照等机制，但没有让 Raw 层承担知识精炼职责；
- 当前自动化测试为 **54 项全部通过**，本机依赖体检结果为 **ready**。

与此同时，学长上游仓库也发生了重要演进：

- 新增全局配置和 `settings/handlers.json` 能力注册表；
- 明确采用 Agent 直接调用工具的三级协议；
- 强化 P5 原则：**OKS 提供能力，不包装运行时**；
- 增加 Goals、Recipes、知识关系、置信度和召回相关设计；
- 新增“知识库即模型”、每日循环、指标体系、知识自动驾驶 L0-L5 等产品方法论；
- 大幅完善 GitHub Pages、架构图和项目展示。

因此，下一步不应将本地的一键编排代码直接覆盖到上游，而应把已经验证的抽取能力重构为可注册、可独立调用的 Level 1 工具，由学长现有的 Agent/Skill 编排。两条路线不是互相否定，而是需要重新确定边界：

```text
学长上游：定义 Agent 如何选择和调用能力
              +
本阶段开发：提供真正可运行的多模态抽取能力
              =
Agent 编排 + Raw Plugin/Adapters + OKS 知识演化
```

---

## 2. 仓库与代码状态

### 2.1 当前代码仍在哪里

当前开发仍位于旧名称的本地克隆目录：

```text
D:\XiangMuLuoDi\Clone\1263-ux\claude-code-knowledge-studios
```

当前分支：

```text
codex/multimodal-ingest
```

当前提交：

```text
1f2d77f feat: improve raw extraction accuracy recovery
```

### 2.2 当前远端关系

当前本地 `origin` 仍指向旧仓库：

```text
https://github.com/1263-ux/claude-code-knowledge-studios.git
```

学长上游为：

```text
https://github.com/open-agent-power/open-knowledge-studio.git
```

新的个人 Fork 为：

```text
https://github.com/1263-ux/open-knowledge-studio.git
```

新的个人 Fork 已经与学长上游最新 `main` 同步，二者当前均位于：

```text
3318ad2 feat: add knowledge automation levels and use cases
```

但是，本地 `origin` 尚未切换到新的个人 Fork，本阶段开发也尚未推送到新 Fork。

### 2.3 “代码有没有提交”的准确答案

不能简单回答“没有提交”，实际分为三层：

1. **已经形成 Git 提交**：本地开发分支相对共同基线共有 8 个功能提交；
2. **只部分推送到旧仓库**：最早的 1 个提交已经存在于旧仓库开发分支，后续 7 个提交仍只在本地；
3. **仍有未提交工作**：Windows Unicode 修复、网页/飞书端到端报告和若干实验脚本仍处于工作区，尚未形成 Git 提交。

因此，新 Fork 当前是干净的上游版本，尚未包含本阶段 Raw 多模态能力。

### 2.4 三条代码线的关系

| 代码线 | 当前提交 | 状态 |
|---|---:|---|
| 本地 `main` / 旧 `origin/main` | `6d56ec4` | 比学长上游落后 10 个提交 |
| 本地开发分支 | `1f2d77f` | 相对共同基线有 8 个本地功能提交 |
| 学长上游 / 新 Fork `main` | `3318ad2` | 最新主线，包含 10 个上游新提交 |

本地开发分支与最新上游已经发生分叉：

```text
共同基线 6d56ec4
├── 本地 Raw 开发：8 个提交
└── 学长上游演进：10 个提交
```

双方同时修改的文件只有 4 个：

- `CLAUDE.md`
- `cli/knowledge_studio/recall.py`
- `docs/index.md`
- `docs/raw-materials.md`

文件冲突数量不多，但架构边界变化较大，因此不能以“覆盖 main”的方式整合。

---

## 3. 学长上游最新变化

从共同基线 `6d56ec4` 到最新 `3318ad2`，上游新增 10 个提交，主要可以分为四类。

### 3.1 多模态能力注册与三级工具协议

上游新增：

- `settings/handlers.json`
- `cli/knowledge_studio/config.py`
- 全局配置 `~/.oks/config.json`
- Knowledge Base 路径和 API Key 配置能力

`handlers.json` 将外部能力分成三级：

| 级别 | 典型工具 | 含义 |
|---|---|---|
| Level 0 | `curl`、`pdftotext` | 通用、轻量、可直接调用的系统工具 |
| Level 1 | `oks-video`、`oks-audio` | 遵守标准 JSON 协议的专用提取能力 |
| Level 2 | Agent Reach、`yt-dlp` | 平台相关或需要额外环境的高级能力 |

这个设计解决的不是“具体如何识别视频”，而是：

> Agent 如何发现本机有哪些能力、检查能力是否可用，并选择合适的工具。

### 3.2 明确 P5：OKS 提供能力，不包装运行时

上游曾短暂加入内部 handler/ingest 运行时，随后又主动移除，并明确：

> OKS provides capability, not runtime wrapping.

当前主线期望：

```text
Agent / Claude Code
  ↓ 读取 handlers.json
判断模态和可用工具
  ↓ 直接调用外部 CLI
生成 Raw
  ↓
OKS ingest / recall / store
```

也就是说：

- Agent 是编排器；
- OKS 核心不应重新实现复杂调度器；
- 不应在核心 CLI 内自动识别所有模态；
- 不应在核心 CLI 内直接加入 AI API 调用；
- Level 1 工具应输出标准、机器可读的结果。

这对本地开发的整合方式有直接影响，详见第 8 节。

### 3.3 知识库能力和方法论扩展

上游新增或强化：

- `profiles/goals/`：目标可以参与召回相关性；
- `profiles/recipes/`：可复用的知识工作流；
- `supersedes`、`enriches`、`confirms`、`challenges` 等知识关系；
- 存储时对旧知识关系和置信度的处理；
- Recall 返回更丰富的关系和置信信息；
- 动态来源标签和查询行为；
- “知识库即模型”理念；
- Daily Loop；
- 知识库指标体系；
- 知识自动驾驶 L0-L5；
- 简历、GitHub、科研等案例。

这些更新说明上游正在继续强化 Wiki、Recall 和知识演化层，而本阶段工作补充的是它尚未具备的真实多模态入口。

### 3.4 项目文档和展示升级

上游还完成了：

- GitHub Pages 主题和导航升级；
- 新增架构图、召回引擎图、记忆模型图、流水线图；
- 文档视觉样式优化；
- 评论区和案例页；
- 哲学、指标、自动驾驶等独立页面。

这些更改提升了项目的可解释性和对外展示能力，但不会直接替代底层多模态抽取器。

---

## 4. 本阶段已经做了什么

从共同基线开始，本地共形成 8 个已提交开发节点。

### 4.1 已提交的开发历史

| 提交 | 内容 |
|---|---|
| `a208877` | 增加有人类确认门槛的口播视频录入样例 |
| `aeea3b3` | 建立多模态 Raw 抽取流水线 |
| `c2176c5` | 收缩下一阶段范围，明确 Raw 边界 |
| `0ac89a2` | 增加多模态反馈闭环和验证机制 |
| `6e8f405` | 增加一条命令式 Raw 录入入口 |
| `48794b0` | 固化 Raw 阶段评审和浏览器采集方向 |
| `2f7b1a3` | 调研识别准确度恢复方案 |
| `1f2d77f` | 实现 ASR、OCR、关键帧和公式候选改进 |

已提交改动规模约为：

- 30 个文件；
- 约 6393 行新增；
- 4 行删除。

主要代码集中在 `scripts/`，没有大规模侵入 Wiki 核心。

### 4.2 Raw Bundle v0.1

建立统一 Raw 产物结构：

```text
raw-bundle/
├── raw.md                 # 入口说明和来源信息
├── content.md             # 可读取、可召回的机器提取正文
├── metadata.json          # 来源、模态、工具、时间和处理状态
├── evidence.jsonl         # 原子证据及定位信息
├── quality-report.json    # 客观过程指标和失败暴露
└── assets/                # 原始文件、截图、帧和页面资产
```

它遵循以下原则：

1. Raw 不是知识；
2. 不在 Raw 中自动总结；
3. 不在 Raw 中自动纠错；
4. 不在 Raw 中判断“是否值得入库”；
5. 提取成功多少就保存多少；
6. 失败也保留现场和原因；
7. 每个片段尽量保留返回原素材的位置。

### 4.3 核心代码设计

#### `scripts/raw_bundle_adapter.py`

这是当前主要适配和打包层，负责：

- 接收不同提取器的结果；
- 统一 Markdown、元数据和证据格式；
- 保留时间戳、页码、坐标和资产引用；
- 生成 `quality-report.json`；
- 校验链接、正文和证据链；
- 避免上游提取器的私有格式扩散到 OKS。

#### `scripts/media_ingest.py`

负责视频和音频相关处理：

- 音频提取；
- 字幕/ASR 路由；
- 带时间戳转写；
- 视频帧和 OCR 结果整理；
- 本地文件与在线链接能力探测；
- 将媒体中间产物交给 Raw Bundle 适配器。

#### `scripts/raw_ingest.py`

当前提供：

- 一条命令入口；
- 输入探测；
- 格式路由；
- 环境 `doctor`；
- `validate`；
- 已安装提取能力的调度。

这里与上游新的 P5 原则存在边界重叠。后续建议保留其中的健康检查和独立 Adapter 能力，将“自动路由与编排”迁移到 Agent Skill，而不是继续扩张为 OKS 内部运行时。

#### `scripts/formula_candidates.py`

负责：

- 从 MinerU 页面结果中寻找独立公式区域；
- 调用 PaddleOCR PP-FormulaNet 形成第二候选；
- 保存候选和来源证据；
- 不自动覆盖 MinerU 原始公式。

该设计的重点不是“让 Raw 自己决定正确答案”，而是防止单一提取器错误成为唯一事实。

#### `scripts/multimodal_feedback.py`

负责：

- 记录实验反馈；
- 对照不同提取路线；
- 将问题回传到下一轮实验；
- 不直接修改原始机器结果。

### 4.4 Recall 联调

对 `cli/knowledge_studio/recall.py` 增加了多模态 Raw 适配：

- 一个 Bundle 优先以 `content.md` 作为召回正文；
- 避免同一 Bundle 的多个说明文件重复命中；
- OCR 或非正文证据可使用 locator 返回原位置；
- 保留对普通 Markdown Raw 的兼容。

另外，当前工作区还有一个尚未提交的 Windows UTF-8 修复，用于避免公式和 Unicode 字符在 CLI 输出时触发编码异常。

### 4.5 Skill 与配置

本地新增：

- `.claude/skills/media-ingest/SKILL.md`
- `settings/raw-tools.example.json`
- 多组 requirements 文件

其作用是：

- 告诉 Agent 如何调用媒体抽取能力；
- 分离 Watch、文档、MinerU 和公式环境；
- 避免把所有大型依赖装进 OKS 核心 Python 环境；
- 通过显式配置引用外部工具路径。

这种“能力环境分离”的实践与上游 `handlers.json` 非常适合整合。

---

## 5. 当前已经具备的多模态能力

### 5.1 能力矩阵

| 模态 | 当前实现 | 真实验证 | 可追溯性 | 当前结论 |
|---|---|---|---|---|
| 本地视频 | ASR、时间戳、抽帧、OCR | 已验证 | 时间戳、帧、原视频 | 原型可用 |
| 本地音频 | faster-whisper ASR | 已验证 | 时间戳、原音频 | 原型可用 |
| 图片 | RapidOCR | 已验证 | bbox、置信度、原图 | 原型可用 |
| PDF | MinerU | 已验证 | 页码、图片、公式区域 | 普通文本可用，公式需核对 |
| PPT | MarkItDown + 媒体映射 | 已验证 | 幻灯片和图片资产 | 原型可用 |
| Word | MarkItDown + 媒体映射 | 已验证 | 文档和图片资产 | 原型可用 |
| 静态 HTML | 正文、标题、列表、链接、代码 | 已验证 | URL、HTML、截图 | 实验可用 |
| B站公开链接 | yt-dlp/字幕路由 | 已探测 | 失败原因保留 | 平台路线仍受 412/字幕限制 |
| 飞书多维表格收件箱 | 表单、记录、附件下载 | 已验证 | record id、附件哈希 | 收件可用，状态回写受权限限制 |

### 5.2 视频样本结果

真实 Java 学习视频完成：

- 视频时长约 142 秒；
- 生成带时间戳 ASR；
- 保存视觉证据；
- 形成 221 条 evidence；
- Raw 可被 OKS Recall 找到。

本阶段没有把 ASR 文本包装成“知识总结”，原始识别偏差仍显式保留。

### 5.3 音频样本结果

真实 60 秒音频完成：

- 带时间戳转写；
- 56 条 evidence；
- 原始音频保留；
- 可校验、可召回。

### 5.4 图片样本结果

图片路线支持：

- OCR 文本；
- bounding box；
- OCR confidence；
- 原图资产；
- 证据定位。

飞书真实图片样本生成 154 条 evidence。

### 5.5 PDF 和公式样本结果

真实 7 页公式 PDF 生成：

- 页面和正文 Markdown；
- 299 条 evidence；
- 页面图片和公式区域；
- MinerU 原始候选；
- PP-FormulaNet 第二候选。

目前可以做到“公式可检索、可定位、可对照候选”，但不能保证公式可以不经核对直接作为正确答案。

已暴露的错误包括：

- `\rceil`、`\ddagger` 等错误符号；
- 希腊字母误识别；
- 重复 `\perp`；
- 上下标、根式和对数底数变形；
- 正文和公式边界混乱。

### 5.6 Office 文档结果

已真实验证：

- PPT 图片映射 17/17；
- Word 图片映射 6/6；
- Markdown 中的资产路径可回到对应图片；
- 文档结构和原文件均保留。

### 5.7 网页真实世界验证

使用 Anthropic 的 “Building effective agents” 页面进行了端到端测试。

HTTP 基线路线：

- 约 18.5k 字符；
- 68 条 evidence；
- 只能识别 2 个标题；
- 没有图片；
- 混入 newsletter 等页面噪声。

浏览器渲染后路线：

- 19 个 Markdown 标题；
- 8 个远程图片引用；
- 91 条 evidence；
- 清除了 newsletter 噪声；
- 保存原始 HTML、渲染 HTML 和全页截图；
- `validate` 和 `recall` 通过。

当前仍未完成远程图片本地化，作者字段也未稳定抽取，因此网页 Adapter 仍应标记为 experimental。

### 5.8 飞书 Raw Inbox 端到端验证

已使用真实飞书多维表格完成：

- 表单提交；
- 多维表格记录读取；
- 视频和公式图片附件下载；
- SHA256 往返一致性验证；
- 附件进入多模态 Raw；
- Raw 绑定飞书 record id；
- `validate` 和 `recall` 通过。

其中一个 3 倍速视频的普通 ASR 返回 0 个片段，烧录字幕 OCR 路线恢复了 272 个候选，最终形成 519 条 evidence。这证明系统能够如实暴露首选路线失败，并尝试独立的恢复路线。

当前阻塞：多维表格状态和摘要回写受到 Base 资源权限错误 `91403` 限制。该问题不影响附件收件和 Raw 生成，但影响完整状态闭环。

---

## 6. 已做的准确度恢复实验

### 6.1 ASR 热词候选

针对技术词和同音词，测试了带热词的第二转写候选。

结果：

- 样本中的“键盘录入”得到恢复；
- 但候选的时间戳粒度变粗；
- 因此没有自动替换原始 ASR，而是保留双方作为候选。

结论：热词适合作为领域上下文，不适合被当作无条件自动纠错器。

### 6.2 OCR ROI

针对整屏 OCR 混入状态栏、菜单、会议控件和单字符噪声的问题，测试正文区域裁剪。

样本结果：

- OCR block 数量从 85 降至 22；
- 噪声约减少 74.1%；
- 处理耗时从 5.03 秒下降到 3.41 秒。

结论：浏览器选区、窗口正文区域和文档 ROI 比“对整张屏幕做更强 OCR”更值得优先实现。

### 6.3 关键帧路线

早期真实视频全部使用均匀抽帧，无法证明“智能关键帧”已经成熟。

后续对屏幕录制样本测试场景变化路线：

- 检出 26 个场景段；
- 最终选择 11 帧；
- 对照均匀路线为 10 帧。

目前证明了场景检测路线可运行，但还需要更多教学视频、编程视频和口播视频验证是否真正提高信息覆盖，而不是只增加画面变化敏感度。

### 6.4 公式第二候选

使用 MinerU 负责页面布局，使用 PP-FormulaNet 对独立公式区域生成第二候选。

当前结果：

- 部分公式得到恢复；
- 两个工具仍可能同时出错；
- 不适合在 Raw 层自动“投票”；
- 最合理的 Raw 行为是保存原候选、第二候选和页面裁剪，让后续 Wiki 或人类核对。

---

## 7. 当前工程质量

### 7.1 自动化测试

2026-07-16 在本机重新执行：

```text
54 passed in 1.02s
```

测试覆盖：

- Raw Bundle 格式和校验；
- 媒体路由；
- 反馈记录；
- 公式候选；
- Recall 多模态兼容；
- Windows CLI Unicode 行为。

### 7.2 环境体检

`python scripts/raw_ingest.py doctor` 当前返回：

```json
{"ready": true}
```

已确认：

| 组件 | 版本/状态 |
|---|---|
| Watch Skill | 1.0.0 |
| RapidOCR | 3.9.1 |
| faster-whisper | 1.2.1 |
| yt-dlp | 2026.7.4 |
| MarkItDown | 0.1.6 |
| MinerU | 3.4.4 |
| PaddleOCR | 3.7.0 |
| ffmpeg / ffprobe | 8.1.2 |

### 7.3 依赖隔离

当前没有将所有模型和解析器塞进 OKS 核心环境，而是拆分为：

- OKS 项目 `.venv`；
- Watch 媒体环境；
- MinerU 环境；
- Paddle Formula 环境；
- 系统 ffmpeg。

优点：

- 降低核心依赖冲突；
- 可单独替换提取器；
- 符合“能力可插拔”的方向。

不足：

- 初次部署仍偏重；
- 当前配置依赖本机路径；
- 尚未形成跨机器的一键安装清单；
- 暂时更适合开发验证，不是面向普通用户的轻量分发版本。

---

## 8. 本地开发与上游架构如何整合

### 8.1 两边真正互补的部分

学长上游解决：

- Agent 如何发现工具；
- 如何区分 Level 0/1/2；
- 如何配置知识库；
- 如何让 Skill 负责路由；
- Raw 之后如何进入 Draft/Wiki/Recall；
- 知识库如何围绕目标长期演化。

本地开发解决：

- 视频到底如何转写并保留时间戳；
- 图片如何保留 OCR 坐标；
- PDF 如何保留页码、公式和图片证据；
- PPT/Word 图片如何落盘和映射；
- 网页渲染后如何抽取正文；
- 飞书附件如何进入 Raw；
- 不同提取器结果如何统一成 Raw Bundle；
- 识别失败如何被记录和恢复。

两者组合后，才能形成完整链路：

```text
用户/Agent
  ↓
上游 ingest Skill 判断模态
  ↓
handlers.json 选择 Level 0/1/2 工具
  ↓
本地 Raw Adapter 执行真实抽取
  ↓
Raw Bundle v0.1
  ↓
OKS validate / recall
  ↓
Draft / Wiki / Knowledge Evolution
```

### 8.2 当前的架构冲突

主要冲突不是数据格式，而是“谁负责路由”。

本地 `scripts/raw_ingest.py` 当前具备一键输入探测和自动调度；上游最新 P5 明确要求 Agent 直接编排工具，不在 OKS 内部再包一层运行时。

如果直接合并并继续扩张 `raw_ingest.py`，会重新引入上游刚刚删除的运行时包装。

### 8.3 建议的整合方式

建议将本地成果定位为 **Raw Plugin / Level 1 Adapters**：

```text
oks-raw-video <input> --output <dir> --json
oks-raw-audio <input> --output <dir> --json
oks-raw-image <input> --output <dir> --json
oks-raw-document <input> --output <dir> --json
oks-raw-web <url> --output <dir> --json
```

这些命令：

- 独立运行；
- 输出标准 JSON 状态；
- 生成 Raw Bundle；
- 不调用 Wiki；
- 不进行知识判断；
- 注册进 `settings/handlers.json`；
- 由 `.claude/skills/ingest/SKILL.md` 选择和调用。

现有 `raw_bundle_adapter.py` 可继续作为协议适配和打包核心；`raw_ingest.py doctor` 可以保留为能力体检，但自动路由逻辑应转交 Skill。

### 8.4 Raw 目录规范需要对齐

上游当前建议：

```text
raw/{YYYY}/{MM}/{DD}/{source}/
```

其中 source 包括：

- articles
- papers
- videos
- audio
- repos
- misc

本地 Raw Bundle 结构不需要推翻，只需把一个 Bundle 作为该目录下的一个素材单元：

```text
raw/2026/07/16/videos/<bundle-id>/
├── raw.md
├── content.md
├── metadata.json
├── evidence.jsonl
├── quality-report.json
└── assets/
```

这样既服从上游来源目录，又保留多模态证据结构。

### 8.5 Raw 与上游 A/B/C Triage 的关系

上游 ingest Skill 在 Raw 落盘后还有 A/B/C 评估，并将高质量内容送到 Draft。

建议明确边界：

- Raw Adapter 只提取和暴露问题；
- A/B/C 是 Agent 对“是否进入 Draft”的判断；
- 不把 A/B/C 写回成对 Raw 原始内容的篡改；
- 任何 Draft/Wiki 结论必须能回到 Raw evidence。

这样既保持 Raw “傻、快、诚实”，又不妨碍上游进行后续知识筛选。

---

## 9. 当前尚未解决的问题

### 9.1 准确性边界

- ASR 仍存在同音词、技术词和多人重叠错误；
- OCR 仍可能出现阅读顺序和界面噪声；
- 复杂数学公式不能直接信任；
- 表格、复杂多栏论文和手写内容尚未系统验证；
- 关键帧路线还缺少足够样本证明收益。

### 9.2 平台链接能力

- 三个 B 站样本均没有公开字幕；
- 在线 `yt-dlp` 请求遇到 HTTP 412；
- 因此“B 站平台字幕直接进入 Raw”仍保持 blocked；
- 当前真正验证的是本地视频 ASR 回退和无字幕路线。

后续可以研究浏览器已登录态、用户主动分享、官方 API 和浏览器扩展，但不应为了平台反爬而让 Raw 核心变成爬虫平台。

### 9.3 网页能力

- HTTP 静态抓取对动态页面和阅读顺序不足；
- 浏览器渲染路线仍是实验脚本；
- 远程图片尚未全部本地化；
- 登录态、授权范围和用户确认机制尚未产品化。

### 9.4 飞书闭环

- 附件接收、下载和 Raw 入库已经验证；
- Base 状态回写受权限 `91403` 阻塞；
- 尚未封装为长期运行的机器人或 workflow；
- 当前更接近真实 E2E 实验，不是生产服务。

### 9.5 Recall 体验

- 当前多模态召回已经可命中；
- 但 snippet 仍偏向正文开头 200 字，而不是围绕查询词截取；
- OCR、公式和长文档的命中展示仍可改进。

### 9.6 部署与复现

- 本机环境已经跑通；
- 依赖多个 Python 环境和本地模型；
- 尚未完成新机器 bootstrap；
- 尚未决定最终是本地插件、轻量客户端还是服务端能力。

这一阶段应先完成工具协议整合和真实使用，不急于提前决定完整产品部署形态。

---

## 10. 下一步方向展望

下一步建议按“先整合、再试用、最后扩展”的顺序推进。

### P0：安全同步上游并保护现有成果

1. 不直接把当前开发分支强推到新 Fork `main`；
2. 将本地 `origin` 迁移到 `1263-ux/open-knowledge-studio`；
3. 保留旧仓库为只读远端；
4. 从新 Fork 最新 `main` 建立新的集成分支；
5. 将本地 8 个提交分组迁移，而不是机械整体覆盖；
6. 单独处理 4 个双方共同修改文件；
7. 排除 `.agents/`、`.codex/`、`AGENTS.md` 和个人 `raw/misc` 素材，不误纳入代码提交。

### P1：把抽取器对齐为上游 Level 1 能力

1. 定义统一输入输出协议；
2. 将视频、音频、图片、文档和网页拆成独立 Adapter 命令；
3. 每个命令输出标准 JSON 状态；
4. 保留 Raw Bundle v0.1；
5. 注册进 `settings/handlers.json`；
6. 由上游 ingest Skill 完成模态选择和工具调度；
7. 保留 `doctor` 作为能力健康检查。

验收目标：

```text
Agent 收到一个真实素材
→ 从 handlers.json 找到能力
→ 调用对应 Adapter
→ 生成可追溯 Raw Bundle
→ OKS validate 通过
→ OKS recall 可以命中
```

### P2：完成最小真实使用闭环

建议连续使用一段时间，而不是继续只做孤立 benchmark：

- 手机端通过飞书多维表格/表单提交素材；
- PC 或服务端读取新记录和附件；
- Agent 调用 Raw Adapter；
- Raw 落到标准日期/来源目录；
- 用户可以立即 Recall；
- 后续再由上游 Draft/Wiki 流程判断是否进化为知识。

第一轮只需要支持：

- 本地文件；
- 一个网页入口；
- 一个飞书收件入口。

无需同时解决所有平台。

### P3：围绕真实失败补能力

按使用中真实出现的频率排序，而不是提前建设“大而全”平台：

1. 网页远程图片本地化；
2. 飞书 Base 状态回写权限；
3. Recall 查询词居中 snippet；
4. B站/平台登录态的合法用户授权路线；
5. 复杂公式候选的人类核对入口；
6. 教学和编程视频的关键帧覆盖实验；
7. 表格、手写和复杂论文格式扩展。

### P4：连接 Wiki，而不是让 Raw 变成 Wiki

Raw 稳定后，下一阶段重点应转向：

- Draft 如何引用 Raw evidence；
- Wiki 概念、策略、反模式如何从多个 Raw 中演化；
- 新旧知识冲突如何使用 `supersedes/challenges/confirms`；
- Goals 如何影响 Recall 和知识进化；
- 人类反馈如何修正 Draft/Wiki，而不抹掉 Raw 原始记录；
- 如何用指标衡量知识是否被使用、更新和复利。

Raw 的职责仍然保持：

> 把现实世界素材完整、诚实、可定位地送到知识系统门口。

---

## 11. 建议的近期分工

### 多模态 Raw 方向

- 整理并迁移现有 Raw Adapter；
- 对齐 `handlers.json` 标准；
- 维护 Raw Bundle Schema；
- 处理视频、音频、图片、PDF/Office、网页和飞书入口；
- 负责样本验证、失败记录和可复现环境。

### 上游 OKS 核心方向

- 维护 ingest/query Skill；
- 维护 Goals、Recipes、Recall、Store 和 Wiki 演化；
- 明确 Raw 到 Draft/Wiki 的关系协议；
- 维护项目架构约束和 P5 边界。

### 共同接口

双方优先确认四件事：

1. Level 1 工具标准 JSON Schema；
2. Raw Bundle 是否作为官方多模态素材单元；
3. Raw 日期/来源目录与 Bundle 的组合规范；
4. Draft/Wiki 如何引用 `evidence.jsonl` 中的 locator。

接口确认后，多模态抽取器和知识演化层可以并行开发，减少互相改动核心代码。

---

## 12. 当前完成度的诚实判断

### 已经做到

- 多模态 Raw 不是停留在方案层，已有真实代码和真实样本；
- 主流本地素材可以通过一条命令生成 Raw Markdown；
- 来源、时间戳、页码、坐标和原资产能够保留；
- 识别失败不会伪装成成功；
- Raw 可以进入 OKS 校验和召回；
- 飞书收件和网页真实抓取已经跑过端到端实验；
- 已建立提取器候选、反馈和准确度恢复实验；
- 自动化测试与本机环境当前通过。

### 还没有做到

- 不是生产级“解析人类看到的一切”；
- 不是所有平台链接都能无登录解析；
- 不能保证数学公式、ASR 和 OCR 100% 正确；
- 浏览器扩展、飞书机器人和服务端尚未产品化；
- 尚未完成上游最新架构的正式合并；
- 尚未在新 Fork 发布可复用的开发分支或 PR；
- 尚未通过长期真实使用验证 Raw 到 Wiki 的知识复利效果。

### 当前阶段定位

最准确的定位是：

> 已完成多模态 Raw 入口的第一套可运行、可追溯原型，并通过多类真实素材与两个真实入口完成验证；下一步应将它按上游 Agent-direct 协议整合为正式的可插拔能力，然后进入连续试用。

---

## 13. 建议给项目组确认的问题

1. 是否认可 Raw Bundle v0.1 作为多模态素材的官方最小单元？
2. 是否认可“Agent 编排、Adapter 抽取、OKS 演化”的三层边界？
3. Level 1 工具是采用多个 `oks-raw-*` 命令，还是一个带明确子命令的 `raw-plugin`？
4. 上游 ingest Skill 的 A/B/C Triage 是否保持在 Raw 落盘之后？
5. Draft/Wiki 是否需要正式支持 `raw_ref + evidence_id + locator` 引用？
6. 下一阶段优先验证飞书真实使用闭环，还是先完成 GitHub 上的协议整合与 PR？

---

## 附录 A：主要新增文件

### 已提交代码

```text
.claude/skills/media-ingest/SKILL.md
scripts/raw_bundle_adapter.py
scripts/raw_ingest.py
scripts/media_ingest.py
scripts/multimodal_feedback.py
scripts/formula_candidates.py
settings/raw-tools.example.json
scripts/requirements-*.txt
scripts/tests/test_raw_bundle_adapter.py
scripts/tests/test_raw_ingest.py
scripts/tests/test_media_ingest.py
scripts/tests/test_multimodal_feedback.py
scripts/tests/test_formula_candidates.py
```

### 已提交设计文档

```text
docs/raw-multimodal-standard.md
docs/raw-ingest-quickstart.md
docs/raw-multimodal-benchmark-20260714.md
docs/raw-phase-review-20260715.md
docs/raw-accuracy-recovery-research-20260715.md
docs/raw-accuracy-improvement-results-20260715.md
docs/browser-capture-and-feishu.md
docs/multimodal-next-step.md
```

### 尚未提交的最新成果

```text
cli/knowledge_studio/cli.py
cli/tests/test_cli.py
docs/raw-component-selection-experiment-20260715.md
docs/raw-multimodal-accuracy-test-plan-20260715.md
docs/raw-inbox-e2e-validation-20260716.md
docs/raw-web-e2e-validation-20260716.md
scripts/experiments/funasr_probe.py
scripts/experiments/ppstructure_probe.py
scripts/experiments/keyframe_probe.py
scripts/experiments/burned_subtitle_probe.py
scripts/experiments/merge_watch_transcript_candidate.py
scripts/experiments/web_raw_probe.py
```

以下内容属于本机配置或用户个人素材，不应纳入项目提交：

```text
.agents/
.codex/
AGENTS.md
raw/misc/2026-07-13-口播相关观点-录屏片段.md
raw/misc/assets/
```

---

## 附录 B：推荐整合策略

```text
open-agent-power/open-knowledge-studio:main (3318ad2)
                    ↓
1263-ux/open-knowledge-studio:main
                    ↓ 新建集成分支
codex/raw-plugin-integration
                    ↓
迁移 Raw Bundle + Adapters + Tests
                    ↓
注册 settings/handlers.json
                    ↓
修改 ingest Skill 调用 Level 1 能力
                    ↓
真实样本验收
                    ↓
提交 Draft PR 给项目组评审
```

不建议：

```text
直接将旧开发分支强推到新 Fork main
```

原因是这样会把上游 10 个新提交表现为被删除，并掩盖 P5 架构边界差异。

