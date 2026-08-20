---
title: 审核与晋升 Wiki
nav_order: 2
parent: 使用指南
---

# 审核与晋升 Wiki

> 把 Agent 生成的 Draft 审核后晋升为可复用的 Wiki 知识。

Draft 是 Agent 提取的知识候选，必须经过人工审核才能进入 Wiki。这是 OKS 的核心质量保障环节。

---

## 快速导航

- [审核标准](#审核标准)
- [审核流程](#审核流程)
- [知识关系](#知识关系)
- [常见错误](#常见错误)
- [批量处理](#批量处理)

---

## 审核标准

审核 Draft 时，检查三个维度：

### 1. 准确性

**事实正确，无明显错误**
- ✅ 核心数据是否准确（如成本、性能）
- ✅ 结论是否符合原始资料
- ❌ 有没有 AI 幻觉（编造的内容）

### 2. 可复用性

**未来能实际使用**
- ✅ 信息是否具体、可操作
- ✅ 有没有时效性问题
- ✅ 能否支持实际决策

### 3. 可追溯性

**关联到 Raw 来源**
- ✅ 能否找回原始资料
- ✅ Provider 链是否清晰
- ✅ 置信度标注是否合理

> **快速判断法**：问自己"三个月后我会用到吗？如果用到，这个 Draft 够用吗？"

---

## 审核流程

### 1. 查看 Draft 列表

```bash
oks drafts list
```

输出示例：
```
drafts/kimi-k3-evaluation.md  [concept]  待审核
drafts/postgresql-setup.md    [strategy] 待审核
```

### 2. 阅读 Draft 内容

```bash
# 用编辑器打开
code drafts/kimi-k3-evaluation.md

# 或用 cat/less 查看
cat drafts/kimi-k3-evaluation.md
```

检查重点：
- 标题和类型是否准确
- 正文内容是否完整
- 来源引用是否清晰
- 有无明显错误

### 3. 做出决策

| 决策 | 命令 | 何时使用 |
|------|------|---------|
| **晋升** | `oks drafts promote <slug>` | 内容准确、可复用 |
| **编辑** | 手动修改文件后晋升 | 方向正确，需改写 |
| **拒绝** | `oks drafts reject <slug>` | 不值得长期保留 |

### 4. 验证晋升结果

```bash
# 确认 Wiki 已创建
oks wiki list | grep <关键词>

# 测试召回
oks recall "相关问题" --limit 3
```

---

## 知识关系

OKS 支持 4 种知识关系，帮助维护知识网络：

### supersedes（替代）

**新知识替代旧知识**

```yaml
---
title: Kimi K3.5 新特性
supersedes: kimi-k3-features
---
```

- 旧知识自动标记为 `archived`
- 召回时优先返回新知识

**示例**：Kimi K3.5 发布后，替代 K3 的特性描述

### enriches（丰富）

**补充新细节**

```yaml
---
title: Kimi K3 在法律场景的应用
enriches: kimi-k3-features
---
```

- 两个知识都保持 `active`
- 召回时一起返回

**示例**：新增 K3 在特定场景的测试数据

### confirms（确认）

**验证已有结论**

```yaml
---
title: Kimi K3 成本验证
confirms: kimi-k3-cost-warning
---
```

- 增加置信度
- 多个来源验证同一结论

**示例**：第二个测评也证实了高成本问题

### challenges（质疑）

**质疑现有观点**

```yaml
---
title: Kimi K3 成本优化后可接受
challenges: kimi-k3-cost-warning
---
```

- 两个观点并存
- 用 `human_reviewed_at` 判断优先级

**示例**：新测试显示成本优化后可接受

---

## 常见错误

### ❌ 不审核直接晋升

- AI 提取可能有误差
- 必须人工确认准确性
- **错误知识比没知识更危险**

### ❌ Draft 堆积不处理

- Draft 数量 > 20 就该清理
- 时间久了记不清上下文
- **建议每周/每两周审核一次**

### ❌ 晋升后不验证召回

- 晋升后测试一次召回
- 确认能用自然问题找到
- 发现问题及时调整

### ❌ 过度提炼导致信息丢失

具体数据要保留：
- ❌ "比较贵" → ✅ "20元/次"
- ❌ "不推荐" → ✅ "我劝你别买"
- ❌ "成本高" → ✅ "十几小时烧掉 300+ 元"

---

## 批量处理

### Draft 太多怎么办？

**现状**：Draft 数量 > 20，不知道从哪开始。

**策略**：

**1. 用 A/B/C 分级**
- A 级（核心）：必须审核
- B 级（有用）：选择性审核
- C 级（参考）：批量 reject

**2. 批量 reject 明显不合适的**

```bash
oks drafts list
# 找出不需要的
oks drafts reject <slug1>
oks drafts reject <slug2>
```

**3. 定期清理**
- 每周审核一次
- 超过 1 个月的 Draft 要么晋升要么 reject

**时间估算**：
- 5-10 个 Draft：15-30 分钟
- 20+ Draft：建议分两次审核

---

## 完整案例：Kimi Draft 审核

### 审核前准备

```bash
$ oks drafts list
drafts/kimi-k3-evaluation.md  [concept]  2026-08-19
```

### 审核检查点

打开 Draft 文件，检查：

✅ **成本数据准确**
- 20元/次、300+元/十几小时

✅ **核心结论完整**
- "普通用户我劝你别买"

✅ **三大场景清晰**
- 应用开发、编程、办公

✅ **来源可追溯**
- B站视频 + ASR 转写 + Provider 链

### 晋升操作

```bash
$ oks drafts promote kimi-k3-evaluation

✅ Promoted to wiki/kimi-k3-evaluation.md
```

### 验证结果

```bash
$ oks wiki list | grep kimi
wiki/kimi-k3-evaluation.md  [concept]  rel=1.0

$ oks recall "Kimi K3 成本" --limit 1
[1] Kimi K3 实测 — 1天烧完1个月算力，普通人慎买
    score=0.84, relevance=1.92
    成本：20元/次、300+元/十几小时...
```

👉 [查看完整演示](../../examples/oh-my-research/demo/kimi-video-walkthrough.md#第-3-步审核-draft)

---

## 下一步

审核完成后，测试召回效果：

- **[测试召回](recalling.md)** - 验证知识能否被准确召回
- **[常见工作流](workflows.md)** - 在实际工作中使用 OKS

---

**核心原则**：人工审核是质量保障的唯一途径。准确性 > 数量，宁可少而精，不要多而杂。
