## 概述

1. **案例体系面向小白重构**：
   - 根 `README.md`：中英文"继续阅读"增加"真实案例"入口，进阶内容（架构原则/摄入边界）单独分组。
   - `examples/README.md`：从"维护者边界说明"重写为**案例导航 index**（顶部"第一次来？30 秒看懂怎么用" + 6 个案例表格）。
   - `examples/oh-my-research/`（托管你的学习）：从"研究案例"改造成**小白入门案例**——顶部"🚀 30 秒开始"（收录→晋升→召回三句话）、goal 一句话模板（Agent 代填字段）、学习笔记模板带示例。

2. **清理**：
   - 删除 `examples/raw-bundles/`（6 个口播录屏帧文件，个人产物）。
   - 移动 `docs/superpowers/` → `internal/superpowers/`（2 个内部实现计划，从公开 docs 站点移出）。
   - 磁盘清理 `examples/oh-my-feishu/.oks/runs/` 和 `__pycache__/`（已 gitignore，不进 diff）。

**Supersedes #40**（已关闭）。#40 只含 2 个文件的导航改动；本分支在其基础上完成案例改造与清理，统一为一个主题。

## 改动清单（相对 `upstream/main@19fd1df`）

| 文件 | 状态 | 说明 |
|---|---|---|
| `README.md` | M | 案例入口 + 进阶分组 |
| `docs/examples.md` | A | 案例导航页（承接 #40） |
| `docs/index.md` | M | 案例链接（承接 #40） |
| `examples/README.md` | M | 案例 index |
| `examples/oh-my-github/README.md` | M | 交叉链接同步 |
| `examples/oh-my-research/README.md` | M | 30 秒开始 + 小白流程 |
| `examples/oh-my-research/goal.md` | M | 一句话模板 |
| `examples/oh-my-research/sample/research-question.md` | M | 模板带示例 |
| `examples/raw-bundles/**` (6 files) | D | 删个人产物 |
| `docs/superpowers/**` → `internal/superpowers/**` | R | 移内部计划 |

**合计**：16 文件，+172 / −284。

## 非目标

- 不改 OKS CLI / Core / 协议 / Provider / Connector。
- 不改其他 5 个案例的内容（仅交叉链接）。
- 不提交本地 `records/acceptance/`、`settings/`、个人知识库。

## 验证

- `git diff --check upstream/main...HEAD` PASS
- 6 个 `examples/oh-my-*` 目录与链接均存在
- 引导链完整：根 README → 案例 index → 学习案例 → goal/模板
- `python -m pytest -q`: **199 passed**
- fresh-context 独立审查通过

## 重点审查

- `examples/` 从"协议样例说明"变成"用户案例导航"是否符合仓库定位。
- `raw-bundles` 删除是否有异议（如需保留可恢复）。
- `superpowers` 移到 `internal/` 是否合适（避免公开站点发布内部计划）。
- "托管你的学习"是否适合作为小白默认入口。
