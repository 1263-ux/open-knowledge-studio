---
title: Raw 多模态协议入口
nav_order: 22
parent: 参考
---

# Raw 多模态协议入口

当前机器可读事实源位于：

- `schemas/capture-envelope.schema.json`
- `schemas/capability-manifest.schema.json`
- `schemas/processing-run.schema.json`
- `schemas/raw-bundle-v0.2.schema.json`
- `capabilities/`

当前 Bundle 版本是 `raw-multimodal/v0.2`。Studio 只负责 Capture 编排、Candidate、人工审核、Wiki 晋升与召回；来源获取后的机械解析、证据定位、质量状态和失败事实由 connector 负责。

设计边界与迁移历史见：

- [自进化学习主 Loop](core-learning-loop-poc.md)
- [阶段历史汇总](phase-history-summary.md)
- [架构设计](architecture.md)

## 兼容性契约

### v0.1 不变性（已冻结）

v0.1 包保证以下最低约定，不受 v0.2 变更影响：

- 每个包包含一个 `content.md` 主文件及零个或多个 `*.jsonl` 证据边车
- 来源归属记录在 `metadata.json` 中，包含 `source_uri`、`captured_at`、`source_type`
- 质量报告写入 `quality-report.json`，包含 `processing_status`（`complete` / `partial` / `failed`）
- 包验证在导入前检查这三个文件的存在性

### v0.1 → v0.2 映射

| v0.1 路径 / 字段 | v0.2 对应项 |
|---|---|
| `metadata.json` | `bundle.json`（schema 版本锁定为 `raw-multimodal/v0.2`） |
| `quality-report.json` → `processing_status` | `bundle.json` → `processing_status`（相同语义） |
| 来源归属（散落于 metadata） | `capture_envelope`（`capture-envelope.schema.json`） |
| 处理步骤（无正式结构） | `processing-runs.jsonl`（`processing-run.schema.json`） |
| 能力发现（硬编码） | `capabilities/` 清单（`capability-manifest.schema.json`） |

### 读取器兼容性

v0.2 模式是 v0.1 的**严格超集**。读取器应：

1. 通过 `bundle.json` 中的 `schema_version` 检测版本
2. 对 v0.1 包：仅消费 `content.md` + `*.jsonl` + `quality-report.json`
3. 对 v0.2 包：消费 `bundle.json`、`capture-envelope`、`processing-runs.jsonl` 及 capability 清单
4. 忽略未知字段——向前兼容性是有意为之

### 迁移路径

从 v0.1 包迁移到 v0.2：

1. 以 v0.1 包作为来源，新生成一个 v0.2 包：
   - 运行 `oks-connector finalize-v2 <output> --capture-envelope <capture.json> --processing-run <run.json> [--source <source>]`
   - 该命令写入 `bundle.json`（`schema_version: raw-multimodal/v0.2`）并消费捕获信封与处理运行记录
2. 验证 `oks-connector validate <path>` 通过
3. 原 v0.1 包保留不动，以确保可审计溯源

### Raw 不是 Knowledge

Raw 包是**原始材料**，不是知识。协议保证以下不变量：

- **不静默丢失**：每次转换必须经过显式的 `finalize-v2` 或 `validate` 步骤；没有自动升级或隐式数据删除
- **来源不可变**：`capture_envelope` 中的 `source_uri`、`source_record`、`captured_at` 在 bundle 生命周期内不可更改；任何重新捕获必须生成新的 capture ID
- **Raw 与 Wiki 分离**：Raw 包从不直接进入 `wiki/`；只有经过 Agent Teach-back 与人工审核（`drafts/` → 审核动作 → `wiki/`）的知识才能写入 Wiki
- **质量状态可审计**：每个 bundle 的 `processing_status`（`complete` / `partial` / `failed`）与失败事实（`errors` 数组）随包持久化，不可回填掩盖

v0.2 连接器 schema 和能力清单是规范事实源。本文档仅描述**兼容性保证**与**不变量**，不重新声明字段定义。

---

{% include comments.html %}
