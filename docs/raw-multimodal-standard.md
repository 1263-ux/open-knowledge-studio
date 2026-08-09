---
title: Raw 多模态协议入口
nav_order: 22
parent: 参考
---

# Raw 多模态协议入口

当前机器可读事实源位于：

- `schemas/source-envelope-v0.1.schema.json`
- `schemas/evidence-fragment-v0.1.schema.json`
- `schemas/evidence-manifest-v0.1.schema.json`
- `schemas/raw-bundle-v0.2.schema.json`
- `cli/knowledge_studio/schemas/`（runtime validator）
- `assets/_meta/schemas/`（instance materialization source）

当前 Bundle 版本是 `raw-multimodal/v0.2`。Agent 负责 Source 判断、Provider 选择、Evidence 汇总和 Candidate；OKS CLI 负责协议骨架、机械验证、Raw Bundle 组装、人工 promote 和召回。

设计边界见：[架构设计](architecture.md) 和 [能力架构](capability-architecture.md)。

最小操作路径是：`oks ingest prepare` → Agent Evidence → `oks raw-commit` → Candidate → 人工 promote → Recall。

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
| 来源归属（散落于 metadata） | `source-envelope.json`（`source-envelope-v0.1.schema.json`） |
| Provider 贡献 | `derived/fragments/`（`evidence-fragment-v0.1.schema.json`） |
| Agent 汇总 | `evidence-manifest.json`（`evidence-manifest-v0.1.schema.json`） |

### 读取器兼容性

v0.2 模式是 v0.1 的**严格超集**。读取器应：

1. 通过 `bundle.json` 中的 `schema_version` 检测版本
2. 对 v0.1 包：仅消费 `content.md` + `*.jsonl` + `quality-report.json`
3. 对 v0.2 包：消费 `bundle.json`、`source-envelope.json`、`evidence.jsonl`、`processing-runs.jsonl` 及 derived fragments
4. 忽略未知字段——向前兼容性是有意为之

### 迁移路径

从 v0.1 包迁移到 v0.2：

1. 以 v0.1 包作为来源，新生成一个 v0.2 包；新 Agent-native 来源直接运行 `oks ingest prepare` 后提交 `oks raw-commit`
2. 验证 `oks-connector validate <path>` 或 `oks-connector validate-v2 <path>` 通过
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
