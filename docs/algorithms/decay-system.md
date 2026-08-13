---
title: 衰减系统
nav_order: 2
parent: 算法
---
# Decay System（衰减系统）

*记忆曲线、类型特定 λ 与 tier 分级——知识如何随时间衰减。*

知识随时间衰减，衰减率由类型决定。

## 记忆曲线

```
score = importance × e^(-λ × days_old) + 0.5 × ln(1 + access_count) + pin_bonus
```

Active 页面获得 ×1.2 乘数。Dropped/archived → 0.0。

- **importance** — 页面的重要性（0.0-1.0），人工设定
- **e^(-λ × days_old)** — 时间衰减，λ 越大衰减越快
- **ln(1 + access_count)** — 访问增强，被访问越多分数越高
- **pin_bonus** — 固定页面加成（默认 0.5）

## 类型特定衰减（λ）

| 类型 | λ | 行为 |
|------|---|------|
| concept | 0.0 | 不衰减 — 概念是永恒的 |
| strategy | 0.014 | 最快衰减 — 策略最容易过时 |
| anti-pattern | 0.010 | 中等衰减 — 教训保鲜期长 |
| unknown | 0.030 | 快速衰减（fallback） |

{: .note }
Concept 不衰减是因为 "什么是 REST API" 这类知识不会过时。Strategy 衰减最快（λ=0.014）是因为 "用微服务拆分单体" 这类策略最容易随技术环境变化而过时。Anti-pattern 衰减较慢（λ=0.010）是因为 "不要用 var 声明变量" 这类教训的保鲜期更长——踩过的坑在很长时间内仍然值得警惕。

## Tier 分级

| Tier | Score | 行为 |
|------|-------|------|
| hot | ≥ 0.7 | 优先召回 |
| warm | ≥ 0.4 | 正常召回 |
| cold | ≥ 0.15 | 低优先级 |
| evictable | < 0.15 | 归档候选 |

分数越高的页面在召回时排序越靠前。Evictable 级别的页面是归档候选 — 系统会在下一次 `oks distill` 时考虑将其标记为 `status: dropped`。

## 生命周期

```
Provisional → Active（人工审阅，记录为 human_reviewed_at）→ Dropped（score < 归档阈值，或 oks wiki archive）
```

- **Provisional** — 尚未经人工审阅。`oks wiki create` 直接写出的页面停在这里
- **Active** — 人工审阅通过（`oks drafts promote` 晋升），frontmatter 带 `human_reviewed_at`
- **Dropped** — 分数低于归档阈值或被显式归档；`oks wiki unarchive` 可拉回 Provisional

访问次数**不改变状态**。它只进入记忆曲线影响排序 —— 被读得多说明相关，不说明正确
（CONSTITUTION P9）。

## 访问计数

每次页面被**显式使用**时（`oks wiki use <slug>`；召回与搜索只读、不计数），
`access_count` +1。它只进入记忆曲线的 `0.5 × ln(1 + access_count)` 项，
**只影响排序**。

使用量不改变 `confidence`，也不改变 `status`。被读得多说明这页持续相关，
不说明它正确；让重复本身抬高可信度会形成自我强化回路 —— 越常被注入 → 越常被用
→ 越显得可信 → 越优先注入。见 CONSTITUTION P9。

confidence 只在**同一份知识被独立重新推导出来**时提升（指纹命中既有页面）：

```python
new_confidence = min(1.0, current + 0.1 × (1 - current))
```

那是关于内容的真实证据；"被读过"不是。

## 配置

衰减参数是 `cli/knowledge_studio/store.py` 里的代码默认值，可通过 `~/.oks/config.json` 的 `decay` 段覆盖（不存在独立的 yaml 配置文件）：

```json
{ "decay": { "archive_threshold": 0.3, "pin_bonus": 0.5 } }
```

- **archive_threshold** — 低于此分数的页面成为归档候选
- **pin_bonus** — Pinned 页面获得的额外分数

源码：`cli/knowledge_studio/store.py`（`DECAY_LAMBDA` + 默认 config）

## 归档是可逆的

```bash
oks wiki archive <slug>    # 置 status: dropped，退出召回
oks wiki unarchive <slug>  # 拉回 Provisional，重新进入召回
```

归档**不删除任何文件** —— 它只改 frontmatter 的 `status`，页面留在 Git 里。

这一点是 A3 的前提：衰减可以在无人审查的情况下自动归档，**只因为它可逆且不破坏**。
晋升是"制造一条断言"，未经审阅的错误会渗进之后每一个回答；归档只是"停止呈现"，
最坏代价是召回覆盖变窄，不会凭空造出损失。一旦衰减变成破坏性操作，这条推理即失效。

`unarchive` 恢复为 `Provisional` 而非 `Active` —— 离开归档不是一次人工审阅。

## 下一步

* **[召回引擎](recall-engine.md)**：记忆曲线如何作为第 6 个因子影响召回
* **[Dreaming 循环](dreaming-cycle.md)**：衰减在演化循环中的位置
* **[宪法](../concepts/constitution.md)**：认知桶结构

---

{% include comments.html %}
