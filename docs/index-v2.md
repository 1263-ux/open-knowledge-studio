---
title: 概述
nav_order: 1
---

<div align="center">
  <img src="assets/oks-logo-readme.png" width="360" alt="Open Knowledge Studio">
</div>

# Open Knowledge Studio

> 让 Agent 把资料转化为可审核、可追溯、以后能重新召回利用的知识。

OKS 是一个 Agent-native、文件系统优先的知识工作台——**Agent 状态栏注入 + Recall 原语**。

```
你的资料 → Candidate → 人工审核 → Wiki → Recall 注入
```

---

## 3 条路径，快速开始

选择最适合你的起点：

### 🚀 路径 1：我是新手（推荐）

从零开始，5 分钟见效：

1. **[安装 OKS](getting-started/installation.md)** — 2 分钟
2. **[5 分钟见效](getting-started/quick-wins.md)** — 立即体验价值
3. **[最佳实践](best-practices.md)** — 学会用好 OKS

### ⚡ 路径 2：我已安装，要开始用

已经装好了，直接开始：

1. **[第一个知识闭环](getting-started/first-loop.md)** — 用真实资料跑通流程
2. **[常见工作流](guides/workflows.md)** — 日常学习、技术选型、项目维护
3. **[完整演示](../examples/oh-my-research/)** — 从视频到技术方案

### 🔧 路径 3：遇到问题了

不确定哪里出错：

1. **[确认 OKS 正在工作](verify.md)** — 按成功信号逐步检查
2. **[故障排除](reference/troubleshooting.md)** — 常见问题和解决方案
3. **[社区支持](reference/community.md)** — 获取帮助

---

## OKS 负责什么

**保留来源**
- Raw 保存原始材料和可追溯证据

**提出知识**
- Agent 根据证据生成 Candidate，执行 A/B/C 分级

**保留人的判断**
- Candidate 经过审核后才能成为 Wiki 知识

**在任务中找回来**
- `oks recall` 同时检索 Raw + Wiki
- Hook 自动注入会话上下文

**把失败说清楚**
- `partial`、`failed`、`skipped` 不会被包装成成功

---

## 核心边界

- Core 不调用 AI API，只负责文件、协议、审核生命周期和 Recall 评分
- 采集与提取由独立发布的 `oks-connector` 和 Agent 可用工具完成
- `raw/executions/` 和 `raw/.logs/` 是溯源记录，不作为记忆参与 Recall
- `[verified]` 只来自 trace 证据或 `human_reviewed_at`，不能由模型自行声明

---

## 快速导航

### 开始使用

- **[安装](getting-started/installation.md)** — 用 pipx 安装
- **[5 分钟见效](getting-started/quick-wins.md)** — 快速体验核心价值
- **[第一个知识闭环](getting-started/first-loop.md)** — 用真实资料跑通流程
- **[最佳实践](best-practices.md)** — 如何正确使用 OKS
- **[确认在工作](verify.md)** — 验证安装和配置

### 使用指南

- **[收集 Raw 材料](guides/collecting.md)** — 选择性收录，A/B/C 分级
- **[审核与晋升 Wiki](guides/reviewing.md)** — 质量保障环节
- **[测试召回](guides/recalling.md)** — 优化召回效果
- **[常见工作流](guides/workflows.md)** — 日常学习、技术选型、项目维护

### 真实案例

- **[案例索引](examples.md)** — 可复制的真实场景
- **[完整演示：Kimi 视频 → 技术方案](../examples/oh-my-research/demo/kimi-video-walkthrough.md)** — 7 分钟，从视频到技术选型

### 核心概念

- **[哲学](concepts/philosophy.md)** — 设计理念
- **[宪法](concepts/constitution.md)** — 不变式和架构
- **[记忆模型](concepts/memory-model.md)** — 6 种记忆类型
- **[文件系统范式](concepts/file-system-paradigm.md)** — 为什么用文件

### 算法详解

- **[召回引擎](algorithms/recall-engine.md)** — Triple-Layer Recall
- **[衰减系统](algorithms/decay-system.md)** — 记忆曲线
- **[召回评估](algorithms/recall-evaluation.md)** — R@1=82.5%, MRR=0.907

### 参考文档

- **[CLI 命令](reference/cli.md)** — 完整命令参考
- **[Ingest 流程](reference/ingest.md)** — Agent-native 采集
- **[故障排除](reference/troubleshooting.md)** — 常见问题
- **[社区](reference/community.md)** — 获取帮助

---

## 召回质量（v0.6.1）

**OKS Triple-Layer Recall**：
- Layer 1: Node-BM25 召回（fts5 索引）
- Layer 2: Soul Boost 注入（type/review/goal 加权）
- Layer 3: Memory Curve 衰减（type-specific λ）

**50-case 语义改写消融实测**：
- R@1 = 82.5%
- R@3 = 92.5%
- MRR = 0.907

👉 [查看完整评估](algorithms/recall-evaluation.md)

---

## 效果对比

### 有 OKS vs 没有 OKS

| 维度 | 没有 OKS | 有 OKS |
|------|---------|--------|
| **知识来源** | AI 训练数据（可能过时） | 你看过的最新资料 |
| **数据准确性** | 模糊（"可能比较贵"） | 具体（20元/次、300+元） |
| **可追溯性** | 无法验证 | 关联原始资料 + Provider 链 |
| **时效性** | 依赖模型更新 | 看完资料立即可用 |
| **个性化** | 通用回答 | 基于你关注的特性 |
| **决策质量** | 缺乏依据 | 有理有据，引用具体数据 |

---

## 社区与支持

- **GitHub Discussions**: [提问和讨论](https://github.com/open-agent-power/open-knowledge-studio/discussions)
- **Issues**: [报告问题](https://github.com/open-agent-power/open-knowledge-studio/issues)
- **贡献指南**: [CONTRIBUTING.md](https://github.com/open-agent-power/open-knowledge-studio/blob/main/CONTRIBUTING.md)

---

**核心原则**：OKS 不是自动化笔记软件，是人机协作的知识工作台。Agent 提取，人审核，共同构建可信赖的知识库。
