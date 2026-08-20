---
title: 概述
nav_order: 1
---

<div align="center">
  <img src="assets/oks-logo-readme.png" width="360" alt="Open Knowledge Studio">
</div>

# Open Knowledge Studio

> Agent 把资料变成知识，人审核，未来能召回

**流程**：`资料 → Candidate → 人工审核 → Wiki → Recall 注入`

---

## 🚀 三条清晰路径

### 路径 1: 第一次用？从这开始

| 步骤 | 做什么 | 时间 |
|------|--------|------|
| 1️⃣ | [安装 OKS](installation.md) | 2 分钟 |
| 2️⃣ | [跑通第一个闭环](first-knowledge-loop.md) | 5 分钟 |
| 3️⃣ | [看真实案例](../examples/oh-my-research/demo/kimi-video-walkthrough.md) | 10 分钟 |

**总耗时**：17 分钟，完全理解 OKS

> **从哪开始**：[从这里开始](start-here.md)

---

### 路径 2: 已经装好？开始用

**常用操作**：
- 📥 **收录资料** - 对 Agent 说"收录这个"
- ✅ **审核 Candidate** - [审核指南](review-candidates.md)
- 🔍 **召回知识** - Agent 自动注入，或 `oks recall`
- 💡 **最佳实践** - [三个阶段](best-practices.md)

**进阶**：
- [上下文注入机制](usage/context-injection.md)
- [配置 Goal 和 Profile](usage/profiles.md)

---

### 路径 3: 遇到问题？这里排查

| 问题 | 解决 |
|------|------|
| 装不上 | [安装故障](reference/troubleshooting.md) |
| 召回不准 | [召回调优](best-practices.md#阶段-3召回-recall) |
| Agent 报错 | [验证 OKS 状态](verify.md) |

---

## 📚 深入了解

<details>
<summary><strong>概念和原理</strong></summary>

- [设计哲学](concepts/philosophy.md) - 为什么这样设计
- [记忆模型](concepts/memory-model.md) - Raw vs Wiki
- [Triple-Layer Recall](algorithms/recall-engine.md) - R@1=82.5%
- [文件系统范式](concepts/file-system-paradigm.md)

</details>

<details>
<summary><strong>真实案例</strong></summary>

| 场景 | 你在托管什么 |
|------|-------------|
| [托管你的学习](../examples/oh-my-research/) | 文章、视频、课程 |
| [托管你的 GitHub](../examples/oh-my-github/) | 技术决策、踩坑 |
| [托管你的飞书](../examples/oh-my-feishu/) | 手机表单 + IM 审核 |
| [托管你的书籍](../examples/oh-my-book/) | 阅读笔记 |

[更多案例](examples.md)

</details>

<details>
<summary><strong>技术参考</strong></summary>

- [CLI 命令](reference/cli.md)
- [Ingest 协议](reference/ingest.md)
- [召回评估数据](algorithms/recall-evaluation.md)
- [故障排查](reference/troubleshooting.md)

</details>

---

## 🎯 OKS 核心边界

**OKS 做什么**：
- ✅ 保留来源（Raw + 可追溯证据）
- ✅ 提出知识（Agent 生成 Candidate）
- ✅ 人工审核（Candidate → Wiki）
- ✅ 自动召回（Hook 注入会话）

**OKS 不做什么**：
- ❌ Core 不调用 AI API
- ❌ 不包装失败为成功
- ❌ 不由模型自行声称 `[verified]`

---

## 📊 召回质量（v0.6.4）

**OKS Triple-Layer Recall**：
- Node-BM25 召回 + Soul Boost 注入 + Memory Curve 衰减
- 50-case 消融实测：**R@1=82.5%** / R@3=92.5% / MRR=0.907

详见 [召回评估](algorithms/recall-evaluation.md)

---

**Agent-native、文件系统优先的知识工作台**
