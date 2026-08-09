---
title: 快速开始
nav_order: 2
parent: 概述
---
# 快速开始

*最短可用路径：保存一条 → 搜索到它 → 验证工作。*

Open Knowledge Studio 最容易理解的方式是一个循环：

* 保存一条有价值的东西
* 再找到它
* 让 Agent 用它

{: .note }
本页是这个循环的最短路径。**前置条件**：Python ≥ 3.12、git；Claude Code（或兼容 Agent）为可选，但 `/ingest`、`/query` 等技能依赖它——没有 Agent 时走下文标注的"纯 CLI 路径"。安装：`pipx install "git+https://github.com/1263-ux/claude-code-knowledge-studios.git@main#subdirectory=cli" && pipx ensurepath && oks init my-knowledge-base && cd my-knowledge-base`（pipx 本身：Ubuntu 用 `sudo apt install pipx`，macOS 用 `brew install pipx`，Windows 用 `py -m pip install --user pipx && py -m pipx ensurepath`；Ubuntu 24.04 / Homebrew Python 受 PEP 668 保护，直接 `pip install` 会报 externally-managed-environment）。

## Studio 是什么

简单来说，Studio 做三件事：

* 存储你的决策、洞察、来源和对话
* 让它们可搜索、可复用
* 让 Agent 从同样的记忆开始工作，而不是每次从零开始

你不需要理解整个系统就能开始用。

## 第一个循环

### Step 1: 准备一个 Source

先准备一个普通 Markdown/TXT 文件，或一个需要 Provider 处理的 URL。推荐让 Agent 从协议入口开始，而不是手工创建 Raw JSON：

```bash
oks ingest prepare ./my-first-note.md --kb-root <你的实例目录>
```

本地文本会返回 `text_ready=true`，协议骨架和原始内容已经预填充；URL、PDF、音视频和图片会额外返回 Recipe 与 `candidate_providers`。

### Step 2: Agent 读取协议并完成 Evidence

在 Claude Code 或兼容 Agent 中运行 `/ingest`。Agent 应读取 shipped Skill，先查看 Recipe 和当前能力状态：

```bash
oks capability status --json
```

Agent 对非文本 Source 选择最小 Provider 集合，保存 Provider 原始输出，填写 evidence text、confidence 和 `agent_judgment`，然后提交 manifest。文本 Source 可以直接进入下一步。

### Step 3: 机械提交 Raw Bundle

```bash
oks raw-commit <manifest-dir> --output <你的实例目录>/raw/my-first-note
```

`raw-commit` 会验证 schema、artifact hash、fragment 引用和 provenance；它不会总结内容，也不会自动写入 Wiki。

### Step 4: 生成 Candidate 并人工审查

Agent 读取 `evidence.jsonl` 和 `content.md`，用自己的话写入 `drafts/<slug>.md`。这一步才是 Candidate，不要把未经判断的 Raw 当作知识。

{: .note }
**纯 CLI 路径**（没有 Claude Code 时）：跳过 drafts，直接把知识写成 wiki 页，然后跳到 Step 4——
```bash
cd <你的实例目录>
oks wiki create --title "CLI framework decision" --type strategy --area computing \
  --content "Chose Typer over Click: native type hints + Rich integration."
```

### Step 5: 提升到 wiki

审查草稿并提升：

```bash
cd <你的实例目录>
oks drafts list           # 查看候选
oks drafts promote <slug> # 提升到 wiki/
```

或用 `/promote` 技能交互式审查。

### Step 6: 确认搜索能找到它

```bash
cd <你的实例目录>
oks search "CLI framework decision"
```

如果搜索结果反映了你刚保存的内容，循环就跑通了。

### Step 5: 连接 AI Agent

Agent 技能预配置在 `.claude/skills/`。核心技能：

| 技能 | 使用场景 |
|------|----------|
| `/query <问题>` | 提问 — Studio 召回相关 wiki 页面并注入上下文 |
| `/ingest` | Agent-native 摄入：prepare → Recipe/Capability → Evidence → Raw → Candidate |
| `/promote` | 审查 drafts 并提升到 wiki |
| `/status` | 查看知识库概览 |

试一下：

```
/query What did we decide about CLI frameworks?
```

Agent 会召回你刚提升的 wiki 页面，并带引用回答。

## 验收标准

以下每一条你都应该能回答"是"：

* 我用 `oks ingest prepare` 生成了协议 workspace
* 我完成了 Evidence 并通过 `oks raw-commit`
* 我把 Candidate 写入了 `drafts/` 中的草稿
* 我把草稿提升到了 `wiki/`
* 我用 `oks search` 搜索到了它
* 在 Agent 会话中，`/query` 召回了我的知识

如果任何一条是"否"，查看下面的验证步骤。

## 验证

### 搜索是否工作

```bash
oks search "your topic"
```

应该返回 `wiki/` 中的结果，带相关性分数。

### 召回是否工作

```bash
oks recall "your topic"
```

应该同时返回 episodic 结果（来自 `raw/`）和 knowledge 结果（来自 `wiki/`）。

### Agent 集成是否工作

在 Agent 会话中：

```
/query What do I know about <topic>?
```

应该将相关 wiki 页面注入上下文，并带来源标签如 `[verified]` 或 `[inferred]` 回答。

## 第一天少做

{: .tip }
> 保存一条记忆。蒸馏一个草稿。提升一个 wiki 页面。跑一次搜索。停。
>
> 第一天的目标是验证循环跑通，不是配置所有域。

## 下一步

* [记忆模型](memory-model.md) — wiki 页面结构、类型和搜索
* [Raw 多模态协议](raw-multimodal-standard.md) — 原始材料、Evidence 和导入格式
* [能力架构](capability-architecture.md) — Provider 与按需安装边界
* [架构设计](architecture.md) — 认知桶结构和记忆生命周期
* [召回引擎](recall-engine.md) — 6+1 因子评分算法
* [Dreaming 循环](dreaming-cycle.md) — 知识演化管线

---

{% include comments.html %}
