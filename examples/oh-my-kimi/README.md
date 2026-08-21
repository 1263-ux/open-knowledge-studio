# 托管你的 AI 产品学习

*把看过的 Kimi 视频、技术介绍，变成设计 AI 产品时能召回的知识。*

## 🚀 30 秒开始

**前提：你已经装好 OKS**（没装的话，先看[安装](../../docs/installation.md)）。

1. 打开你的 Agent（Claude Code / Codex），对它说：

   > "把这个 Kimi 产品介绍视频收录进我的 OKS：[视频链接]"

2. 它收录完会生成一条草稿，你过一眼，说：

   > "可以，晋升。"

3. 过几天要设计方案时，问它：

   > "Kimi 的 Ki3 模型有什么特点？帮我设计一个使用 Ki3 的技术方案。"

   OKS 会把相关知识自动找出来，Agent 基于这些知识给你设计方案。

**就这么三步。** 下面是完整的演示过程。

---

## 为什么需要它

你有没有这种场景：

- 刷了一堆 AI 产品的介绍视频，当时觉得"这个不错"
- 过几周要做技术选型了，想不起来看过哪些产品、各有什么特点
- 只好重新搜索，或者凭模糊印象瞎猜

**OKS 帮你把"看过的视频"变成"记得住的知识"。**

---

## 完整演示：从视频到技术方案

### 演示素材

我们用两个 Kimi 官方视频作为演示：

1. **B 站视频**：[Kimi 产品介绍]（待补充链接）
2. **YouTube 视频**：[Kimi Technical Overview]（待补充链接）

这两个都是介绍性视频，正好展示 OKS 如何从"产品宣传"中提取"可复用的技术知识"。

---

### 第一步：入库前的状态

![入库前状态](assets/screenshots/01-before-ingest.png)

**此时的问题：**
- 知识库里没有 Kimi 相关内容
- 如果问 Agent "Kimi 的 Ki3 有什么特点"，它只能基于训练数据回答（可能过时）
- 无法基于你看过的具体视频内容给建议

---

### 第二步：收录视频

![开始入库](assets/screenshots/02-start-ingest.png)

对 Agent 说：

```
把这个 Kimi 产品介绍视频收录进我的 OKS：
https://www.bilibili.com/video/BV1...
```

**OKS 做了什么：**
1. 识别视频源（B 站）
2. 提取视频元信息（标题、时长、发布时间）
3. 如果有字幕，提取文字内容
4. 生成 Raw Bundle 存入 `raw/{YYYY}/{MM}/{DD}/video/`
5. 创建待审核的 Draft 候选

![入库进行中](assets/screenshots/03-ingest-processing.png)

---

### 第三步：审核 Draft

![查看 Draft](assets/screenshots/04-review-draft.png)

入库完成后，查看生成的 Draft：

```bash
oks drafts list
```

![Draft 列表](assets/screenshots/05-draft-list.png)

查看具体内容：

```bash
oks drafts get kimi-ki3-features
```

**Draft 示例内容：**

```markdown
---
title: Kimi Ki3 模型特点
type: concept
area: ai-models
importance: 0.8
---

## 核心特点

- **超长上下文**：支持 128k tokens 上下文窗口
- **多模态能力**：支持文本、图片理解
- **推理优化**：针对中文场景优化的推理能力
- **工具调用**：原生支持 function calling

## 技术架构

- 基于 Transformer 架构
- 采用 MoE（Mixture of Experts）设计
- ...

## 应用场景

1. 长文档分析
2. 多轮对话
3. 代码生成
...
```

**审核要点：**
- ✅ 信息准确（基于视频内容提取）
- ✅ 结构清晰（便于后续召回）
- ✅ 来源可追溯（关联到 raw bundle）

---

### 第四步：晋升到 Wiki

![晋升到 Wiki](assets/screenshots/06-promote.png)

审核通过后，晋升：

```bash
oks drafts promote kimi-ki3-features
```

或对 Agent 说：

```
这条 draft 可以，晋升到 wiki。
```

![晋升成功](assets/screenshots/07-promote-success.png)

---

### 第五步：基于知识设计方案

![召回知识](assets/screenshots/08-recall.png)

现在，当你需要设计技术方案时：

```
我要设计一个智能文档分析系统，考虑使用 Kimi Ki3。
请帮我设计技术方案，说明为什么选 Ki3、怎么用。
```

**OKS 自动召回：**

![召回结果](assets/screenshots/09-recall-result.png)

```
🔍 Recalled from OKS:
- kimi-ki3-features.md (0.85 relevance)
- ai-model-comparison.md (0.72 relevance)
```

**Agent 基于召回的知识给出方案：**

![技术方案](assets/screenshots/10-technical-design.png)

```markdown
## 智能文档分析系统技术方案

### 模型选型：Kimi Ki3

**选择理由：**
1. **超长上下文**（128k tokens）—— 支持一次性处理完整长文档
2. **中文优化** —— 你的视频提到 Ki3 针对中文场景做了推理优化
3. **多模态能力** —— 支持 PDF、图片中的表格和图表理解

**技术架构：**
...
```

---

### 对比：有 OKS vs 没有 OKS

| 维度 | 没有 OKS | 有 OKS |
|------|---------|--------|
| **知识来源** | AI 训练数据（可能过时） | 你看过的最新视频 |
| **可追溯性** | 无法验证信息来源 | 每条知识都关联到原始视频 |
| **个性化** | 通用回答 | 基于你关注的产品特性 |
| **时效性** | 依赖模型更新 | 看完视频立即可用 |

![对比图](assets/screenshots/11-comparison.png)

---

## 更多玩法

### 1. 对比多个 AI 产品

同样的流程，收录多个产品视频：
- Kimi Ki3
- GPT-4
- Claude Opus
- Gemini Pro

然后问：

```
对比这几个模型，哪个更适合我的文档分析场景？
```

OKS 会召回所有相关知识，Agent 给你一个基于实际特性的对比分析。

### 2. 持续追踪产品更新

每次 Kimi 发布新版本视频，收录进 OKS：

```
收录这个 Kimi Ki3.5 发布视频，和之前的 Ki3 版本对比。
```

OKS 会自动建立知识关系（`supersedes` / `enriches`）。

### 3. 建立学习目标

让 OKS 记住你的学习目标：

```
我的目标是：深入理解大语言模型的技术选型和应用。
请创建学习目标，追踪我看过的视频和沉淀的知识。
```

参考 [goal 示例](goal.md)。

---

## 技术细节

### 支持的视频源

- ✅ B 站（bilibili.com）
- ✅ YouTube
- ✅ 本地视频文件（需要字幕文件）

### Raw Bundle 结构

```
raw/2026/08/20/video/
├── kimi-intro-bilibili/
│   ├── metadata.json          # 视频元信息
│   ├── transcript.txt          # 字幕文本
│   └── manifest.json           # Bundle 索引
```

### Draft → Wiki 的质量控制

- **人工审核必需**：AI 提取可能有误，必须人工确认
- **来源可追溯**：每个 Wiki 条目都关联回 Raw Bundle
- **版本管理**：Wiki 修改记录在 git history

---

## 常见问题

**Q: 视频没有字幕怎么办？**

A: 可以：
1. 使用 OKS 的 `/media-ingest` skill（实验性功能，需要 Whisper）
2. 手动提供字幕文件
3. 或者只收录视频链接作为参考，手动写 Draft

**Q: 入库一个视频要多久？**

A: 取决于视频长度和字幕提取方式：
- 有现成字幕：10-30 秒
- 需要 ASR 转录：5-15 分钟

**Q: 收录太多视频会不会召回变慢？**

A: 不会。OKS 使用 Node-BM25 索引，召回速度不随知识量线性增长。50 个 Wiki 条目的召回延迟在 100ms 以内。

---

## 下一步

- 试试其他场景：[托管你的学习](../oh-my-research/)、[托管你的 GitHub](../oh-my-github/)
- 深入了解：[完整文档](https://open-agent-power.github.io/open-knowledge-studio/)
- 加入讨论：[GitHub Discussions](https://github.com/open-agent-power/open-knowledge-studio/discussions)
