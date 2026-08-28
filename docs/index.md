---
title: 概述
nav_order: 1
nav_exclude: true
---

<div class="oks-hero">
  <p class="oks-eyebrow">OPEN KNOWLEDGE STUDIO</p>
  <h1>让 Agent 记住团队已经确认的判断</h1>
  <p class="oks-lead">OKS 是面向 Agent 的可审核外部知识库：保存来源、审核结果和可复用知识，让下一次任务直接沿用已经确认的经验，而不是重新解释背景。</p>
  <div class="oks-actions">
    <a class="btn btn-primary" href="{{ '/first-knowledge-loop.html' | relative_url }}">完成第一条知识闭环</a>
    <a class="btn" href="{{ '/oh-my/' | relative_url }}">查看真实案例</a>
  </div>
</div>

<div class="oks-card-grid">
  <div class="oks-card">
    <h3>有来源</h3>
    <p>原始材料和机械提取结果可以回到具体来源，不把收集到的内容直接当成结论。</p>
  </div>
  <div class="oks-card">
    <h3>人工审核</h3>
    <p>Agent 可以提出 Candidate，但只有人能接受、修改或拒绝它成为长期知识。</p>
  </div>
  <div class="oks-card">
    <h3>可持续复用</h3>
    <p>后续任务召回已审核知识，同时说明证据缺口和可能过时的部分。</p>
  </div>
</div>

## 从一个真实问题开始

1. 给 Agent 一份真实材料，并说明什么证据可信、什么必须由你决定。
2. 查看它提出的 Candidate：来源支持什么、还缺什么、是否值得复用。
3. 换一个任务，确认 Agent 只使用已审核知识，并能说清它从哪里来。

不需要先理解目录、协议或算法；先完成一条小闭环，再按需要进入日常任务、案例或参考资料。

## OKS 不会替你越过的边界

- 来源被保存，不代表来源中的主张已经证实。
- Agent 写出的总结，不会自动变成长期知识。
- 证据不足时，系统应说明缺口，而不是补出一个确定答案。
- 发布、合并、删除和外部发送等高风险动作，仍需要人的明确授权。

从[第一次学习循环](first-knowledge-loop.html)开始，或先看案例[托管你的学习](oh-my/study.html)。需要把已审核知识交付为文件时，阅读 [Office 工作流](usage/office.html)。
