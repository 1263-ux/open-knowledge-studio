# Open Knowledge Studio

> 把一条有价值的信息，变成能够在未来任务中被找到、被使用、并推动系统改进的个人知识。

当前阶段只做一件事：跑通一条真实的自进化学习 Loop，然后根据真实反馈微调。

## 当前主 Loop

```text
发现内容
  → Capture（来源 + 为什么保存 + 学习问题）
  → Raw（机械抽取 + evidence + 失败事实）
  → Candidate（用自己的理解重讲）
  → 人工审核
  → Wiki
  → 新任务召回并使用
  → 反馈
  → 改进 PR
```

完整任务、逐项验收标准和停止条件见：[自进化学习主 Loop](core-learning-loop-poc.md)。

## 从这里开始

1. 阅读[阶段历史简报](phase-history-summary.md)，了解已经完成和未完成的能力。
2. 按[主 Loop POC](core-learning-loop-poc.md)选择一条已成功生成 Raw 的公开文章。
3. 生成 Teach-back Candidate，并由用户审核。
4. 晋升一篇 Wiki，在隔离任务中验证召回和实际使用。
5. 只修复本轮暴露的最大问题，通过测试和 PR 合入。

## 当前能力边界

已经真实验证：

- 本地或已取得的 PDF、DOCX、PPTX、图片、音频和视频可以形成带证据的 Raw；
- 当前飞书 Base 已跑通静态 HTML、直接 PDF、附件和公开浏览器快照；
- Challenge、登录要求和平台 HTTP 412 会诚实停止，不生成伪 Raw；
- Raw Bundle 可以记录来源、运行、逐模态状态、证据和质量警告。

尚未完成：

- 任意平台 URL 的稳定资源获取；
- 登录态浏览器到 Capture 的固定产品入口；
- 当前 Base 的 Raw → Candidate → Wiki → 新任务使用闭环；
- 基于真实使用反馈持续改进并 Merge 的完整 Loop。

详细证据与数字见[阶段历史简报](phase-history-summary.md)。

## 文档导航

### 当前执行

| 页面 | 内容 |
|---|---|
| [自进化学习主 Loop](core-learning-loop-poc.md) | 当前唯一主任务、任务清单和二元验收标准 |
| [阶段历史简报](phase-history-summary.md) | 过去阶段的真实成果、失败和当前能力边界 |
| [快速开始](start-here.md) | Studio 基础 CLI 和第一条知识的操作路径 |

### 长期架构

| 页面 | 内容 |
|---|---|
| [架构设计](architecture.md) | Raw、Draft、Wiki、Profile 和 Settings 的职责 |
| [Raw Materials](raw-materials.md) | 原始材料层和蒸馏入口 |
| [Memories](memories.md) | Wiki 页面结构、类型和审核后的知识 |
| [Dreaming 循环](dreaming-cycle.md) | Candidate、人工审核和知识演化 |
| [召回引擎](recall-engine.md) | 当前词法评分、主题关联和记忆曲线 |
| [记忆模型](memory-model.md) | 记忆类型、来源和冲突处理 |
| [衰减系统](decay-system.md) | Wiki 页面生命周期与衰减 |
| [Frontmatter Schema](frontmatter-schema.md) | Wiki YAML 元数据规范 |

## 机器事实源

Studio 负责编排和知识闭环；多模态解析协议与能力清单由独立 connector 维护：

- [oks-connector 协议](https://github.com/1263-ux/oks-connector/blob/codex/raw-poc-validation/docs/protocols-v0.1.md)
- [机器可读 Schema](https://github.com/1263-ux/oks-connector/tree/codex/raw-poc-validation/schemas)
- [Capability Manifests](https://github.com/1263-ux/oks-connector/tree/codex/raw-poc-validation/capabilities)

Studio 文档不再复制一套可能漂移的 Raw v0.x 字段定义。

## 核心不变量

- Raw 保存来源、机械抽取、证据和失败，不充当知识结论。
- AI 可以生成 Candidate，但必须人工审核后才能进入 Wiki。
- Git 记录知识和系统的演化。
- “搜到了”不等于“学会了”；只有在真实任务中使用并产生反馈，Loop 才完成。
