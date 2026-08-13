---
title: 衰减系统
nav_order: 2
parent: 算法
---
# 衰减系统（记忆曲线）

## 难题背景

知识库随时间累积，旧知识占据召回排序高位，挤掉新知识。需要衰减淘汰——但不能：

- 破坏性删除（丢可追溯性）
- 自我强化（被读多→显得可信→更优先，CONSTITUTION P9 禁止）

难题：如何让旧知识退场，同时保留可逆性 + 不让使用量造可信度？

## 技术设计

记忆曲线评分：

```
score = importance × e^(-λ × days_old) + 0.5 × ln(1 + access_count) + pin_bonus
```

Active ×1.2，dropped/archived → 0.0（退出召回）。

四项：

- **importance**（0-1，人工设定）
- **e^(-λ × days_old)** — 时间衰减，λ 越大衰减越快
- **ln(1 + access_count)** — 访问增强，被用多分高，但 ln 抑制暴涨
- **pin_bonus** — 固定页加成（默认 0.5）

## 原理

### 类型 λ 差异

不同知识保鲜期不同：

| 类型 | λ | 理由 |
|------|---|------|
| concept | 0.0 | "什么是 REST API"不过时 |
| strategy | 0.014 | "用微服务拆单体"随技术环境过时最快 |
| anti-pattern | 0.010 | "不要用 var 声明"教训保鲜期长 |
| unknown | 0.030 | fallback，快速衰减 |

### access 不推状态

`access_count` 只进 `ln` 项影响排序，不改 `confidence` 或 `status`。被读多说明相关不说明正确；让重复抬高可信度会自我强化——越常注入 → 越常被用 → 越显得可信 → 越优先注入。见 CONSTITUTION P9。

`confidence` 只在"同一份知识被独立重新推导出来"时提升（指纹命中既有页面）：

```python
new_confidence = min(1.0, current + 0.1 × (1 - current))
```

那是关于内容的真实证据；"被读过"不是。

### 归档可逆

`archive` 只改 frontmatter 的 `status`，不删文件（Git 保留）。`unarchive` 拉回 `Provisional`（非 `Active`——离开归档不是一次人工审阅）。这是 A3 前提：衰减可无人自动归档，只因可逆且不破坏。

## 指标

Tier 分级（按 score）：

| Tier | Score | 行为 |
|------|-------|------|
| hot | ≥ 0.7 | 优先召回 |
| warm | ≥ 0.4 | 正常召回 |
| cold | ≥ 0.15 | 低优先级 |
| evictable | < 0.15 | 归档候选 |

`archive_threshold`（默认 0.15，可配）——低于此分进入归档候选，下次 `oks distill` 标 `dropped`。

## 实验

无量化衰减效果评测（需长期跟踪知识库召回质量）。λ 取 0.014/0.010/0.0 是经验值——concept 不衰（永恒）vs strategy 快衰（易过时）是知识论直觉，非数据拟合。

可调：`~/.oks/config.json` 的 `decay` 段覆盖 `archive_threshold` + `pin_bonus`。

## 结论

衰减是可逆淘汰，不是破坏。归档退出召回但留 Git，`unarchive` 拉回——最坏代价是召回覆盖变窄，不造损失。一旦衰减变成破坏性操作，A3 的推理即失效。

访问量只进排序不进可信度——记忆热度反映"真被用"，防自我强化回路。
