---
title: 托管你的研究
nav_order: 3
parent: 案例
---
# 托管你的研究

*让读过的论文、跑过的实验、闪过的想法，围绕一个研究问题积累成可召回的研究记忆，而不是散落在几十个 PDF 和笔记里。*

研究的痛点是：读了几百篇论文却记不住哪篇说了什么，做过的实验结论散落各处，一个好想法当时没记就忘了。把研究当成一个 goal 驱动的知识库来托管，让它随你的研究一起生长。

## 设 goal

- **研究 goal**：推进一个具体的研究问题（如"验证方法 X 在场景 Y 上是否更优"）。
- goal 是对抗熵增的关键——文献浩如烟海，没有边界只会越读越散。goal 决定哪些论文、哪些结论值得沉淀。

## 收集入 raw/

把持续产生的研究材料汇入 `raw/`，按来源归档：

- 读的论文 → `raw/{date}/papers/`，记下核心贡献、方法、和你问题的关系。
- 跑的实验 → 记下设置、结果、异常。
- 冒出的想法 → 立刻记，哪怕只有一句。
- 组会/讨论的结论 → 存下来。

保真为先，不急着下结论——这是 [Raw 多模态标准](../algorithms/raw-multimodal.md) 的原则。

## 审查沉淀 wiki/

在 goal 约束下 `/promote`：

- **concept**：领域内的关键方法、定义、你理解透的机制。
- **strategy**：验证有效的实验设计、分析套路。
- **anti-pattern**：走过的弯路、失败的实验（**召回时会被加权**，帮你不再重复）。

沉淀时用[知识演化关系](../algorithms/frontmatter-schema.md)串起论文之间的 supersedes / confirms / challenges——这正是文献综述的骨架。

## 召回复用

```bash
oks recall "方法X 局限 反例"
oks recall "你的研究问题" --topic-id <方向>
```

- 写 related work 时，召回某方向读过的所有论文及你的批注。
- 设计新实验前，召回相似实验的设置与踩过的坑。
- 让 Agent 带着你的研究上下文一起讨论下一步。

{: .important }
> 随着知识演化，被推翻的旧结论会被标记 superseded / challenged 而**不是删除**。研究最怕丢失"我们当初为什么放弃这条路"，Git 历史 + 关系标记把它完整留住。

---

## 案例：托管 Kimi K3 研究

把上面的流程落到一个真实研究目标上：**评估 Kimi K3 在长程软件工程上的能力边界**。下面是这个研究库里的一条速查记忆 + 它如何被 oks 召回复用。

### 速查卡

| 项目 | 值 |
|---|---|
| **模型** | `kimi-k3` |
| **厂商** | Moonshot（月之暗面） |
| **规模** | 2.8T 参数 MoE，单 token 激活 104B |
| **架构** | Kimi Delta Attention、Attention Residuals、Stable LatentMoE（16/896 专家） |
| **上下文** | 1M tokens |
| **模态** | 文本、图片、视频（原生视觉） |
| **API** | OpenAI SDK 兼容；`base_url=https://api.moonshot.ai/v1` |
| **推理** | 思考模式始终开启；`reasoning_effort`：`low` / `high` / `max`（默认） |
| **定价** | $0.30（缓存命中）/ $3.00（缓存未命中）/ $15.00（输出）每百万 token |
| **开源权重** | 2026 年 7 月 27 日已发布 |
| **arXiv** | `2607.24653` |

Kimi K3 是月之暗面的旗舰模型，也是首个开源 3T 级模型。目标场景为长程编程、智能体知识工作、推理和多模态任务。整体落后于 Claude Fable 5 和 GPT 5.6 Sol，但优于其他所有受测模型。最强的已验证能力是长程软件工程——公开案例涵盖 GPU 内核优化、编译器构建和芯片设计。

### 怎么托管进来

1. **设 goal**：`profiles/goals/kimi-k3-eval.md`——"评估 Kimi K3 在长程 SWE 场景的能力边界"。
2. **收集 raw**：官方 blog / arXiv 论文 / 速查卡 → `oks ingest run` 落到 `raw/{date}/papers/` + `raw/{date}/blogs/`，带 provenance。
3. **审查沉淀**：把"架构三件套（KDA / AttnRes / Stable LatentMoE）"提炼成 concept；把"GPU 内核优化案例"提炼成 strategy；把"K3 落后 Fable 5"标 `challenges` 到已有的 Claude 评测页。
4. **召回**：下次评估别的模型时，`oks recall "长程 SWE 基准"` 带出 Kimi3 的成绩做横向对比；`oks recall "MoE 训练稳定性"` 带出 Stable LatentMoE 的机制做架构参考。

这条记忆里的每条断言都带 `[verified]`（源自官方 blog / arXiv）或 `[inferred]`（AI 蒸馏未审），召回时一眼分清。

---

## 第一步该做什么

1. 给当前研究问题设一个 goal。
2. 把**最近读的一篇**关键论文记进 `raw/papers/`，附上它和你问题的关系。
3. 提炼成一条 concept 记忆，搜一次试试。

## 接下来读哪里

- **[梦幻循环](../algorithms/dreaming-cycle.md)**：让 AI 帮你从大量论文里发现模式。
- **[前言模式](../algorithms/frontmatter-schema.md)**：A4 知识演化关系的字段定义。
