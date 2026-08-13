---
title: 宪法
nav_order: 2
parent: 概念
---
# 宪法（A1-A5 架构不变量）

完整文本见 [CONSTITUTION.md](https://github.com/open-agent-power/open-knowledge-studio/blob/main/CONSTITUTION.md)。下面是摘要。

## A1: 四桶 + 两基础设施

四个认知桶 `profiles/` `raw/` `wiki/` `drafts/`，两个基础设施 `settings/` `_meta/`。记忆生命周期：Observe → Write → Store → Retrieve → Inject → Forget。

## A2: 六类记忆 + 注入顺序 + source labels

User / Project / Episodic / Semantic / Procedural / Draft 六类，映射到四桶 + skills。每条注入的知识带 source label（`[verified]` / `[inferred]` / `[stale]` / `[untrusted-source]`），未识别类型默认 untrusted。

## A3: Dreaming — 人审门控

`raw/` → AI 蒸馏 → `drafts/` → 人审 → `wiki/`。**绝不 auto-promote**——raw 内容不审不进 wiki。AI 写的只是 Candidate，人的 yes/no 是决策。

## A4: 知识演变

四种关系：`supersedes`（取代）/ `enriches`（补充）/ `confirms`（印证）/ `challenges`（质疑）。关系记在 frontmatter，召回时旧页降权。

## A5: 原子写

所有持久化用 `mkstemp` + `fsync` + `os.replace`——写一半崩溃不留半文件。
