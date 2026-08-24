---
name: master-ai-product-selection
type: learning
status: active
created: 2026-08-20
---

# 学习目标：掌握 AI 产品选型

## 目标

深入理解主流大语言模型（Kimi Ki3、GPT-4、Claude、Gemini）的技术特点，能够根据具体场景做出合理的技术选型决策。

## 为什么要学这个

- **工作需要**：团队要做智能文档分析系统，需要选合适的 AI 模型
- **知识积累**：AI 产品迭代快，需要持续追踪最新能力
- **决策能力**：从"听说过"到"能讲清楚为什么选它"

## 学习范围

### 核心关注点

1. **Kimi 系列**：Ki3、Ki3.5 的技术特点和应用场景
2. **对比维度**：上下文长度、多模态能力、推理质量、成本
3. **实战案例**：各产品在文档分析、代码生成、对话系统的表现

### 资料来源

- 官方产品介绍视频（B 站、YouTube）
- 技术博客和论文
- 实际使用经验和测试记录

## 成果形式

- **Wiki 知识库**：每个产品一个核心特性页面
- **对比分析**：多维度对比表格，支持快速决策
- **案例集**：真实场景下的选型案例和踩坑记录

## 验收标准

能够回答以下问题（基于 OKS 召回的知识）：

1. Kimi Ki3 的核心优势是什么？适合什么场景？
2. 对比 GPT-4 和 Claude，Ki3 在中文场景的表现如何？
3. 设计一个智能文档分析系统，应该选哪个模型？为什么？

## 进度追踪

- [ ] 收录 Kimi 产品介绍视频（B 站 + YouTube）
- [ ] 晋升 Kimi Ki3 特性到 Wiki
- [ ] 收录 GPT-4、Claude、Gemini 对比资料
- [ ] 完成一次实际技术选型（基于 OKS 召回）
- [ ] 沉淀选型决策过程到 Wiki

## OKS 配置

这个 goal 会影响 OKS 的召回行为：

- 当你问 AI 产品相关问题时，`ai-models` 和 `technical-comparison` 类型的 Wiki 会获得召回加权
- 可以用 `oks recall "问题" --goal master-ai-product-selection` 显式指定
- 或者设为 active goal（`oks config set active_goal master-ai-product-selection`），自动生效

## 相关资源

- [Kimi 官网](https://kimi.moonshot.cn/)
- [Moonshot AI 技术博客](https://www.moonshot.cn/blog)
- [大模型能力对比评测](https://github.com/...)（待补充）
