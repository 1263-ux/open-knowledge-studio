---
title: 测试召回
nav_order: 3
parent: 使用指南
---

# 测试召回

> 验证知识能否被准确召回，并优化召回效果。

召回是 OKS 的核心价值：把沉淀的知识在需要时找回来。这个阶段的关键是：**用自然问题测试**，而不是关键词堆砌。

---

## 快速导航

- [提问技巧](#提问技巧)
- [召回不准的原因](#召回不准的原因)
- [调优技巧](#调优技巧)
- [理解评分](#理解评分)

---

## 提问技巧

OKS 使用 **Node-BM25**（node-level BM25，每个 `##` heading 一个 node）。好的提问方式：

### ✅ 正确的提问

**1. 用自然语言（不是关键词堆砌）**
- ✅ "Kimi K3 适合用来做文档分析吗？"
- ❌ "Kimi K3 文档分析 成本 性能"

**2. 包含上下文**
- ✅ "我要设计智能文档分析系统，Kimi K3 适合吗？"
- ❌ "Kimi K3"

**3. 测试不同措辞（paraphrase）**
- ✅ "Kimi K3 价格" / "Kimi K3 成本" / "Kimi K3 多少钱"
- Node-BM25 会匹配到不同段落

**4. 用 `--explain` 查看评分原因**

```bash
oks recall "Kimi K3 成本" --explain
```

输出示例：
```
[1] Kimi K3 实测 — 1天烧完1个月算力，普通人慎买
    score=0.84, relevance=1.92
    
    评分因子：
    - token-overlap: 3 (Query 和 Wiki 有 3 个 token 重叠)
    - idf-overlap: 1.00 (IDF 加权重叠度)
    - title-terms: 2 (标题中匹配 2 个词)
    - type: concept×0.6 (concept 类型，decay 后)
```

---

## 召回不准的原因

### 三个最常见原因

**1. Wiki 不存在**

Draft 还没晋升

```bash
# 检查
oks wiki list | grep <关键词>

# 解决
oks drafts promote <slug>
```

**2. Query 偏差（用词不匹配）**

Wiki 用"成本"，你问"价格"

- Node-BM25 靠字面匹配
- 同义词需要 paraphrase

```bash
# 测试不同措辞
oks recall "Kimi 成本"
oks recall "Kimi 价格"
oks recall "Kimi 多少钱"
```

**3. 类型权重**

不同类型有不同的权重：

| 类型 | 权重 | 说明 |
|------|------|------|
| `concept` | 1.5 | 技术概念、产品特性 |
| `strategy` | 1.5 | 方法论、决策建议 |
| `generic` | 0.5 | 一般性内容 |

解决：调整 Wiki 的 `type` 字段

---

## Triple-Layer Recall 架构

理解召回的三层架构，帮助定位问题：

```
Layer 1 (召回层): Node-BM25 fts5 索引
    ↓ 字面匹配 + IDF 加权
Layer 2 (注入层): Soul Boost
    ↓ type×boost + review×1.2 + goal 重排
Layer 3 (衰减层): Memory Curve
    ↓ type-specific λ → hot/warm/cold/evictable
```

**召回不准通常是 Layer 1 的问题**（用词不匹配），不是 Layer 2/3。

---

## 调优技巧

### 1. Goal 加权（Layer 2）

设置 active goal 提升相关领域召回

```bash
# 方式 1：全局配置
oks config set active_goal master-ai-product-selection

# 方式 2：在 goal.md 中配置
# profiles/goals/master-ai-product-selection.md
```

效果：与 goal 相关的 Wiki 页面会获得额外加权

### 2. 主动标记使用

```bash
oks wiki use <slug>
```

- 提升使用记录
- 增加 `review_bonus`（Layer 2）

### 3. 调整类型

编辑 Wiki 文件的 frontmatter：

```yaml
---
title: Kimi K3 实测
type: concept  # 改为 concept 或 strategy 提升权重
area: computing
---
```

### 4. 用 `--scope` 限定范围

```bash
oks recall "query" --scope computing
```

只在 computing area 中召回

### 5. 调整 limit

```bash
# 默认返回 5 条
oks recall "query"

# 返回更多结果
oks recall "query" --limit 10
```

---

## 理解评分

### 评分因子详解

使用 `--explain` 查看完整评分：

```bash
oks recall "Kimi K3 成本" --explain
```

**主要因子**：

**token-overlap**: Query 和 Wiki 有多少 token 重叠
- 数值越高越好
- 例：3 表示 3 个 token 匹配

**idf-overlap**: IDF 加权重叠度
- 0.0 - 1.0 范围
- 考虑词的稀有性（稀有词权重更高）

**title-terms**: 标题中匹配的词数
- 标题匹配比正文匹配权重更高
- 例：2 表示标题中有 2 个词匹配

**type boost**: 类型权重
- concept: 1.5
- strategy: 1.5
- generic: 0.5

**decay factor**: 记忆衰减
- hot: 1.0（新知识）
- warm: 0.8-0.9
- cold: 0.5-0.7
- evictable: < 0.5

### 评分示例

```bash
$ oks recall "Kimi K3 成本" --limit 1 --explain

[1] Kimi K3 实测 — 1天烧完1个月算力，普通人慎买
    score=0.84, relevance=1.92
    
    评分因子：
    - token-overlap: 3
    - idf-overlap: 1.00
    - title-terms: 2
    - type: concept×0.6 (decay 后)
    - review_bonus: 1.2 (已审核)
```

**解读**：
- 高分（0.84）表示高相关性
- title-terms=2 说明标题匹配度高
- concept 类型获得提权
- 已通过人工审核，额外加权

---

## 完整案例：Kimi 知识召回

### 测试召回

```bash
$ oks recall "Kimi K3 成本" --limit 1 --explain
```

### 结果分析

**召回成功**：
- score=0.84（高相关性）
- relevance=1.92
- 准确召回 "Kimi K3 实测 — 1天烧完1个月算力，普通人慎买"

**显示核心信息**：
- 成本：20元/次、300+元/十几小时
- 结论："普通用户我劝你别买"
- 三大场景：应用开发、编程、办公

**评分因子**：
- token-overlap: 3
- idf-overlap: 1.00
- title-terms: 2
- type: concept×0.6

👉 [查看完整演示](../../examples/oh-my-research/demo/kimi-video-walkthrough.md#第-5-步测试召回)

---

## 常见问题

### Q: 为什么召回找不到我的知识？

**检查清单**：

1. ✅ **Draft 已晋升到 Wiki？**
   ```bash
   oks wiki list
   ```

2. ✅ **Query 用词合适？**
   - 尝试不同措辞（paraphrase）
   - 用 `--explain` 查看评分详情

3. ✅ **类型权重合理？**
   - `generic` 类型被降权 0.5
   - 改为 `concept` 或 `strategy`

4. ✅ **Wiki 内容完整？**
   - 检查 Wiki 文件，确认关键词在正文中
   - Node-BM25 匹配每个 `##` heading 段落

### Q: 如何提升召回准确率？

**最有效的方法**：

1. **改进 Query**：用自然语言 + 上下文
2. **调整类型**：重要知识用 `concept` 或 `strategy`
3. **测试措辞**：尝试 3-5 种不同问法
4. **设置 Goal**：激活相关领域的加权

---

## 下一步

召回测试完成后，了解实际工作流：

- **[常见工作流](workflows.md)** - 在实际工作中使用 OKS
- **[召回引擎详解](../algorithms/recall-engine.md)** - 深入理解 Triple-Layer Recall

---

**核心原则**：召回质量 = 知识质量 × Query 质量。好的知识 + 好的提问 = 准确的召回。
