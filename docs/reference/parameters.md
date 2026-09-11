---
title: 参数表
nav_order: 3
parent: 参考
redirect_from:
  - /reference/recall-yaml.html
---

# recall.yaml 参数表

`settings/recall.yaml` 是召回参数的**唯一事实源**：hook（userprompt / posttool）与 CLI 召回共用同一份。本文镜像 `assets/settings/recall.yaml` 的默认值；上游的 P6 lint audit 会抓"定义了参数但实现不支持"的漂移。

完整默认文件见仓库 [assets/settings/recall.yaml](https://github.com/1263-ux/open-knowledge-studio/blob/main/assets/settings/recall.yaml)。

## recall（共用召回阈值，所有 hook 共享）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `floor` | `0.7` | 召回相关性阈值，低于此值不注入 |
| `topn` | `3` | 最多注入的页数 |
| `minlen` | `6` | prompt 最短长度，短于它不触发召回 |
| `cooldown` | `10` | 冷却（秒/轮），抑制重复注入 |

## posttool（PostToolUse hook 专有行为）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `mode` | `signal` | 行为模式：signal=按 signal_rel_floor 过滤后才提示 |
| `signal_rel_floor` | `2.5` | relevance 超过此值才发 signal（提示文件冲突等） |

## conflict

| 参数 | 默认值 | 说明 |
|---|---|---|
| `window` | `300` | 文件冲突检测的时间窗口（秒） |

## 注入预算（L0–L3 分层）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `inject.budget_chars` | `4000` | 总注入预算（字符，约 1K token） |
| `inject.per_page_chars` | `200` | 每页 body_preview 上限（L2 摘要级） |
| `inject.title_only_floor` | `0.5` | rel 低于此值的页只注入标题行（L0） |

预算触发时按 tier 降级：L2（全文 200c）→ L1（overview 100c）→ L0（abstract 50c）→ 仅标题 → 截断。

## 其它

| 参数 | 默认值 | 说明 |
|---|---|---|
| `search_backend` | `fts5` | 召回后端：`fts5`（SQLite FTS5 节点级，默认）或 `native`（6 因子兼容后端） |
| `embedding_fallback` | `false` | fts5 召回不足时切换 embedding 补充（慢，默认关） |
| `mail_topn` | `3` | hook 注入的未读 Mail 上限 |

## 环境变量覆盖

以下 `OKS_*` 环境变量可临时覆盖 yaml 值（兼容层，优先级高于 recall.yaml）：

`OKS_RECALL_FLOOR`、`OKS_RECALL_TOPN`、`OKS_RECALL_MINLEN`、`OKS_RECALL_COOLDOWN`、`OKS_POSTTOOL_FLOOR`、`OKS_POSTTOOL_TOPN`、`OKS_POSTTOOL_MODE`、`OKS_POSTTOOL_RECALL`、`OKS_POSTTOOL_SIGNAL_REL_FLOOR`、`OKS_CONFLICT_WINDOW`、`OKS_SEARCH_BACKEND`、`OKS_MAIL_TOPN`

命名规则：`OKS_` + 大写参数名（如 `recall.floor` → `OKS_RECALL_FLOOR`）。
