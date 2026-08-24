# OKS 文档体系梳理报告

**梳理时间**: 2026-08-20  
**上游仓库**: open-agent-power/open-knowledge-studio  
**最新版本**: v0.6.4 (Triple-Layer Recall)

---

## 现有文档结构

### 1. 入门层 (Getting Started)
| 文档 | 覆盖内容 | 目标用户 |
|------|---------|---------|
| `start-here.md` | 选择路径（Agent / 纯CLI） | 第一次接触 OKS |
| `installation.md` | pipx 安装、init、验证 | 准备安装 |
| `first-knowledge-loop.md` | 完整闭环（收录→审核→召回） | 已安装，第一次使用 |
| `quick-start.md` | 快速命令参考 | 想快速上手 |
| `verify.md` | 成功信号检查 | 不确定哪里出错 |

**覆盖良好** ✅  
- 路径清晰（Agent 优先 / CLI 备选）
- 强调"用真实资料"
- 完整闭环示范

### 2. 使用层 (Usage)
| 文档 | 覆盖内容 | 缺失点 |
|------|---------|--------|
| `memories.md` | Wiki 生命周期、类型 | - |
| `conversations.md` | 对话存档 | 缺具体案例 |
| `library.md` | Raw 管理 | - |
| `context-injection.md` | Hook 注入机制（17KB，最长） | - |
| `profiles.md` | 画像、goal 配置 | 缺实际配置示例 |

**覆盖较好** ✅  
- 核心功能都有文档
- `context-injection.md` 非常详细（17KB）

**可改进** ⚠️
- 缺少**端到端使用场景**
- 缺少**常见工作流**示例

### 3. 概念层 (Concepts)
| 文档 | 覆盖内容 |
|------|---------|
| `philosophy.md` | 设计哲学 |
| `constitution.md` | 记忆架构（A1-A5, P0-P11） |
| `memory-model.md` | 6类记忆模型 |
| `file-system-paradigm.md` | 文件系统优先 |
| `architecture.md` | 系统架构 |

**覆盖完整** ✅  
- 设计原则清晰
- 架构边界明确

### 4. 算法层 (Algorithms)
| 文档 | 覆盖内容 | 亮点 |
|------|---------|------|
| `recall-engine.md` | Triple-Layer Recall 原理 | ✅ |
| `recall-evaluation.md` | 50-case 消融实验 | ✅ R@1=82.5% |
| `decay-system.md` | 记忆衰减曲线 | ✅ |

**覆盖优秀** ✅✅  
- v0.6.1+ 定名 Triple-Layer Recall
- 有真实消融实验数据
- 技术深度足够

### 5. 参考层 (Reference)
| 文档 | 覆盖内容 |
|------|---------|
| `cli.md` | 命令行参考 |
| `ingest.md` + 子文档 | 摄入协议、Agent-native walkthrough |
| `troubleshooting.md` | 故障排查 |
| `community.md` | 社区资源 |

**覆盖良好** ✅

### 6. 案例层 (Examples)
| 文档 | 覆盖内容 | 状态 |
|------|---------|------|
| `examples.md` | 案例索引 | ✅ |
| `examples/oh-my-research/` | 托管你的学习（新手入门） | ✅ 刚完成推广演示 |
| `examples/oh-my-book/` | 托管你的书籍 | ✅ |
| `examples/oh-my-feishu/` | 托管你的飞书 | ✅ |
| `examples/oh-my-github/` | 托管你的 GitHub | ✅ |
| `examples/oh-my-maintainer/` | 托管你的开源项目 | ✅ |
| `examples/oh-my-resume/` | 托管你的简历 | ✅ |

**覆盖优秀** ✅✅  
- 6 个真实场景
- 新手从"托管你的学习"开始
- 我们刚完成了 Kimi 视频演示（有截图）

---

## 文档缺口分析

### 🔴 明显缺失

#### 1. **Best Practices / 最佳实践指南**
**状态**: ❌ 完全缺失  
**影响**: 用户不知道"正确的使用方式"

**应该包含**:
- 知识管理三阶段（收集→沉淀→召回）的最佳实践
- 什么该放 Raw，什么该放 Wiki
- Draft 审核的标准和技巧
- Goal 配置的实际案例
- 避免的常见错误

#### 2. **Visual Guide / 可视化指南**
**状态**: ❌ 缺失  
**影响**: 新手难以建立心智模型

**应该包含**:
- 数据流图（资料→Raw→Draft→Wiki→Recall）
- 目录结构图解
- 召回注入流程图
- 对比图（有 OKS vs 无 OKS）

#### 3. **Workflows / 工作流模式**
**状态**: ⚠️ 部分缺失  
**影响**: 用户不知道如何组合使用功能

**应该包含**:
- 日常学习工作流
- 技术调研工作流
- 项目维护工作流
- 团队协作工作流

#### 4. **Real-world Tutorial / 真实场景教程**
**状态**: ⚠️ 有案例但缺教程  
**影响**: 案例是"what"，教程是"how"

**examples/ 有案例但缺乏**:
- 手把手的操作教程
- 每一步的截图
- 预期输出和常见错误

**我们刚完成的 Kimi 演示正好填补了这个空缺！**

#### 5. **FAQ / 常见问题**
**状态**: ❌ 完全缺失  
**影响**: 用户重复提问

**应该包含**:
- 为什么 Recall 找不到我的知识？
- Draft 和 Wiki 有什么区别？
- 如何处理大量历史资料？
- 成本和性能问题

---

## 文档质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **完整性** | 7/10 | 核心功能都有文档，缺实践指南 |
| **深度** | 9/10 | 算法层非常详细，有消融实验 |
| **可读性** | 8/10 | 结构清晰，语言简洁 |
| **实用性** | 6/10 | 缺少端到端教程和最佳实践 |
| **可视化** | 3/10 | 几乎没有图表和截图 |

**总体评分**: 7.3/10

**优势**:
- ✅ 技术深度优秀（Triple-Layer Recall + 消融实验）
- ✅ 架构清晰（concepts/ 层次完整）
- ✅ 案例丰富（6 个真实场景）

**短板**:
- ❌ 缺少最佳实践指南
- ❌ 可视化不足（几乎没有截图和图表）
- ⚠️ 缺少手把手教程（案例是"what"不是"how"）

---

## 最佳实践文档定位建议

### 方案 A：创建 `docs/best-practices.md`（推荐）

**定位**: 填补"如何正确使用 OKS"的空白

**结构**:
```markdown
# OKS 最佳实践

## 知识管理三阶段

### 阶段 1：收集（Raw）
- ✅ 什么该收集
- ❌ 什么不该收集
- 💡 技巧：A/B/C 分级策略
- 📸 截图：Raw Bundle 示例

### 阶段 2：沉淀（Draft → Wiki）
- ✅ 审核标准
- ❌ 常见错误
- 💡 技巧：知识关系（supersedes/enriches/confirms/challenges）
- 📸 截图：Draft 审核过程

### 阶段 3：召回（Recall）
- ✅ 如何提问
- ❌ 为什么召回不准
- 💡 技巧：Goal 加权 + 主动标记使用
- 📸 截图：召回结果解读

## 完整案例：从 Kimi 视频到技术方案
- 👉 链接到 examples/oh-my-research/demo/kimi-video-walkthrough.md
- 7 步截图 + 详细说明
- 对比效果（60,000元/月成本分析）

## 常见工作流
- 日常学习流程
- 技术选型流程
- 项目文档维护流程

## 常见问题与解决
- Q: 为什么召回找不到？
- Q: Draft 太多怎么办？
- Q: 如何批量处理历史资料？
```

**优势**:
- ✅ 直接解决用户最关心的"怎么用好"问题
- ✅ 可以引用我们刚完成的 Kimi 演示（有真实截图）
- ✅ 补充现有文档体系的最大短板

**放置位置**:
- `docs/best-practices.md` - 单独一页
- 在 `docs/index.md` 中加入导航链接

---

### 方案 B：扩展 `examples/oh-my-research/`（次选）

**定位**: 把"托管你的学习"打造成最佳实践的典范

**结构**:
```
examples/oh-my-research/
├── README.md （现有，新手入门）
├── demo/
│   ├── kimi-video-walkthrough.md （✅ 已完成，完整演示）
│   ├── best-practices.md （新增，提炼最佳实践）
│   └── workflows.md （新增，常见工作流）
└── assets/screenshots/ （✅ 已完成，7张截图）
```

**优势**:
- ✅ 集中在一个案例中深入展示
- ✅ 利用现有的 Kimi 演示素材

**劣势**:
- ❌ 最佳实践散落在案例中，不够系统
- ❌ 用户可能找不到（以为只是一个案例）

---

## 我的推荐

### 🎯 推荐方案：A + B 结合

**第一步：创建 `docs/best-practices.md`（核心）**
- 系统化的最佳实践指南
- 知识管理三阶段 + 常见工作流 + FAQ
- 大量引用 Kimi 演示作为实例
- 配图：流程图 + 对比表 + 关键截图

**第二步：强化 `examples/oh-my-research/`（案例）**
- 保持 `kimi-video-walkthrough.md` 作为"真实演示"
- README.md 中突出"这是最佳实践的参考实现"
- 在演示文档末尾添加"更多最佳实践"链接到 docs/

**第三步：更新 `docs/index.md` 导航**
```markdown
## 按需要深入
- **开始使用**：... · [**最佳实践**](best-practices.md) ← 新增
- **案例**：[可复制的真实场景](examples.md) · [**完整演示**](../examples/oh-my-research/demo/kimi-video-walkthrough.md) ← 新增
```

---

## 内容框架草稿

### `docs/best-practices.md` 目录

```markdown
# OKS 最佳实践

> 如何正确使用 OKS 管理知识

## 核心理念

### 知识 vs 资料
- 资料（Raw）：原始的、未经筛选的
- 知识（Wiki）：审核后的、可复用的

### 三个关键决策点
1. 这份资料值得收录吗？（A/B/C 分级）
2. 这个 Draft 值得晋升吗？（审核标准）
3. 这次召回为什么不准？（调优技巧）

## 阶段 1：收集 Raw

### ✅ 应该收集
- 你真正看过/读过的资料
- 未来可能需要追溯来源的信息
- 包含具体数据和结论的内容

### ❌ 不应该收集
- 随手转发的链接（没看过）
- 纯娱乐内容（没有复用价值）
- 敏感信息（成本高于价值）

### 💡 A/B/C 分级策略
- **A级**：核心资料，必须完整保留
- **B级**：有价值，提取关键点即可
- **C级**：参考资料，保留索引

### 📸 实例：Kimi 视频入库
[链接到 kimi-video-walkthrough.md 第2步]

---

## 阶段 2：沉淀 Wiki

### ✅ Draft 审核标准
1. **准确性**：事实正确，无明显错误
2. **可复用**：未来能实际使用
3. **可追溯**：关联到 Raw 来源

### ❌ 常见错误
- ❌ 不审核直接晋升
- ❌ Draft 堆积不处理
- ❌ 晋升后不验证召回

### 💡 知识关系技巧
- **supersedes**：新知识替代旧知识
- **enriches**：补充新细节
- **confirms**：验证已有结论
- **challenges**：质疑现有观点

### 📸 实例：Kimi Draft 审核
[链接到 kimi-video-walkthrough.md 第3-4步]

---

## 阶段 3：召回 Recall

### ✅ 提问技巧
- 用自然语言（不是关键词堆砌）
- 包含上下文（"我要设计XX，需要YY"）
- 测试不同措辞（paraphrase）

### ❌ 为什么召回不准
1. **Wiki 不存在**：还没晋升
2. **Query 偏差**：用词和 Wiki 不匹配
3. **类型权重**：generic 类型被降权

### 💡 调优技巧
- **Goal 加权**：设置 active goal 提升相关领域召回
- **主动标记**：`oks wiki use <slug>` 提升使用记录
- **explain 模式**：`--explain` 查看评分原因

### 📸 实例：Kimi 知识召回
[链接到 kimi-video-walkthrough.md 第5-6步]

---

## 完整案例

### 从 Kimi 视频到技术方案（7 分钟）

**演示亮点**：
- ✅ 真实运行（不是模拟）
- ✅ B站视频自动转文字
- ✅ AI 提取成本数据（20元/次、300+元）
- ✅ 召回准确（score=0.84）
- ✅ 技术方案有理有据（60,000元/月分析）

👉 [查看完整演示](../examples/oh-my-research/demo/kimi-video-walkthrough.md)

![效果对比](../examples/oh-my-research/assets/screenshots/07-comparison-table.png)

---

## 常见工作流

### 日常学习
1. 看到好文章/视频 → 收录到 Raw
2. 周末集中审核 Drafts
3. 写方案时自动召回

### 技术选型
1. 收集候选方案的资料
2. 沉淀每个方案的核心特性
3. 对比召回 → 做出决策

### 项目维护
1. 沉淀每次重要决策
2. 踩坑后补充 anti-pattern
3. 新人 onboarding 时召回

---

## FAQ

### Q: 为什么召回找不到我的知识？
**检查清单**：
1. ✅ Draft 已晋升到 Wiki？`oks wiki list`
2. ✅ Query 用词合适？尝试不同措辞
3. ✅ 类型权重？generic 类型被降权 0.5

**解决方案**：
- 使用 `--explain` 查看评分详情
- 设置 goal 提升相关领域权重

### Q: Draft 太多处理不过来？
**策略**：
- 用 A/B/C 分级，优先处理 A 级
- 批量 reject 明显不合适的
- 定期清理（每周/每月）

### Q: 如何批量处理历史资料？
**建议**：
- 不要一次性导入，分批处理
- 优先处理最近 3 个月的
- 旧资料可以只保留 Raw，不一定要 Wiki

### Q: 成本和性能如何？
- **存储**：约 100KB/分钟视频（转写文本）
- **召回延迟**：< 100ms（50个 Wiki）
- **ASR 成本**：faster-whisper 本地运行，免费

---

## 延伸阅读

- [算法：Triple-Layer Recall](algorithms/recall-engine.md) - R@1=82.5%
- [架构：CONSTITUTION](concepts/constitution.md) - P0-P11 不变式
- [参考：CLI 命令](reference/cli.md) - 完整命令列表
```

---

## 下一步行动

你选择：
- **A. 立即创建 `docs/best-practices.md`**（我按照上面框架执行）
- **B. 先讨论框架细节**（你有其他想法）
- **C. 同时完成任务 2 的其他内容**（配图、工作流图表等）

我的建议是 **A**，因为框架已经很清晰，我们有现成的 Kimi 演示素材（真实截图 + 完整流程），可以直接开始写。

你觉得呢？
