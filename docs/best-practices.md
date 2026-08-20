---
title: 最佳实践
nav_order: 4
---

# OKS 最佳实践

> 如何正确使用 OKS 管理知识

**OKS 不是笔记软件**。它不要求你长期坐在里面写作、整理页面。OKS 负责的是：把你已有的文件、网页、媒体和主动提交的信息，经 Agent 提取、人工审核后，沉淀成可召回的文件系统知识。

---

## 核心理念

### 知识 vs 资料

| | 资料（Raw） | 知识（Wiki） |
|---|---|---|
| **谁写** | 人收集，工具提取 | AI 起草，人审核 |
| **特点** | 原始的、未经筛选的 | 审核后的、可复用的 |
| **衰减** | 无（永久保留） | 有（type-specific λ） |
| **召回** | 按时间新鲜度 | 按相关性 + 记忆曲线 |

**一个好的工作流**：把资料存入 `raw/`，然后把值得长期记住的部分提炼到 `wiki/`。

### 三个关键决策点

每次使用 OKS，你会遇到三个决策点：

1. **收集时**：这份资料值得收录吗？（A/B/C 分级）
2. **审核时**：这个 Draft 值得晋升吗？（审核标准）
3. **召回时**：为什么找不到 / 如何优化？（调优技巧）

下面按这三个阶段展开最佳实践。

---

## 阶段 1：收集 Raw

### ✅ 应该收集

- **你真正看过/读过的资料**
  - 看完的技术视频、文章、论文
  - 读完的书籍章节
  - 参与过的技术讨论

- **未来可能需要追溯来源的信息**
  - 技术选型的调研资料
  - 重要决策的讨论记录
  - 踩坑和解决方案

- **包含具体数据和结论的内容**
  - 成本数据、性能指标
  - 对比分析、测评结果
  - 明确的技术建议

### ❌ 不应该收集

- **随手转发的链接**（没看过内容）
  - 收藏夹堆积症的根源
  - 没读过就入库 = 噪音

- **纯娱乐内容**（没有复用价值）
  - 除非你在研究这个领域
  - 娱乐就娱乐，不要假装学习

- **敏感信息**（安全成本高于价值）
  - 密码、密钥、token
  - 个人隐私、商业机密
  - OKS 是本地文件系统，但也要注意备份安全

### 💡 A/B/C 分级策略

入库时对资料分级，帮助后续决策：

- **A级**：核心资料，必须完整保留
  - 项目核心技术决策文档
  - 关键技术的深度教程
  - 重要会议记录

- **B级**：有价值，提取关键点即可
  - 技术博客、产品介绍
  - 一般性技术讨论
  - 参考案例

- **C级**：参考资料，保留索引
  - 快速浏览的文章
  - 备用方案资料
  - "可能有用"的链接

**实践建议**：A 级必审必晋升，B 级选择性晋升，C 级可以只保留 Raw 不生成 Wiki。

### 📸 实例：Kimi 视频入库

我们用 B 站的 Kimi K3 实测视频（B 级资料）演示完整流程。视频内容是产品评测，包含具体的成本数据和使用建议，值得收录并提炼知识。

👉 [查看完整演示](../examples/oh-my-research/demo/kimi-video-walkthrough.md#第-2-步入库视频)

**入库过程**：
- yt-dlp 提取视频元数据
- ffmpeg 提取音频
- faster-whisper 转写为文字（220 段）
- AI 生成结构化 Draft

**时间成本**：约 5-10 分钟（取决于视频长度）

---

## 阶段 2：沉淀 Wiki

### ✅ Draft 审核标准

审核 Draft 时，检查三个维度：

1. **准确性**：事实正确，无明显错误
   - 核心数据是否准确（如成本、性能）
   - 结论是否符合原始资料
   - 有没有 AI 幻觉（编造的内容）

2. **可复用性**：未来能实际使用
   - 信息是否具体、可操作
   - 有没有时效性问题
   - 能否支持实际决策

3. **可追溯性**：关联到 Raw 来源
   - 能否找回原始资料
   - Provider 链是否清晰
   - 置信度标注是否合理

**快速判断法**：问自己"三个月后我会用到吗？如果用到，这个 Draft 够用吗？"

### ❌ 常见错误

- ❌ **不审核直接晋升**
  - AI 提取可能有误差
  - 必须人工确认准确性
  - 错误知识比没知识更危险

- ❌ **Draft 堆积不处理**
  - Draft 数量 > 20 就该清理
  - 时间久了记不清上下文
  - 建议每周/每两周审核一次

- ❌ **晋升后不验证召回**
  - 晋升后测试一次召回
  - 确认能用自然问题找到
  - 发现问题及时调整

- ❌ **过度提炼导致信息丢失**
  - 具体数据要保留（如"20元/次"不是"比较贵"）
  - 关键结论要原样保留（如"我劝你别买"）
  - 可以精简，但不要丢失核心信息

### 💡 知识关系技巧

OKS 支持 4 种知识关系（CONSTITUTION A4），帮助维护知识网络：

- **supersedes**（替代）：新知识替代旧知识
  - 例：Kimi K3.5 发布后，替代 K3 的特性描述
  - 旧知识标记为 `archived`

- **enriches**（丰富）：补充新细节
  - 例：新增 K3 在特定场景的测试数据
  - 两个知识都保持 `active`

- **confirms**（确认）：验证已有结论
  - 例：第二个测评也证实了高成本问题
  - 增加置信度

- **challenges**（质疑）：质疑现有观点
  - 例：新测试显示成本优化后可接受
  - 两个观点并存，用 `human_reviewed_at` 判断优先级

**实践建议**：在 Draft 的 frontmatter 中用 `supersedes: <slug>` 标注关系。

### 📸 实例：Kimi Draft 审核

![Draft 内容示例](../examples/oh-my-research/assets/screenshots/04-wiki-list.png)

审核时检查：
- ✅ 成本数据准确（20元/次、300+元/十几小时）
- ✅ 核心结论完整（"普通用户我劝你别买"）
- ✅ 三大场景清晰（应用开发、编程、办公）
- ✅ 来源可追溯（B站视频 + ASR 转写 + Provider 链）

👉 [查看完整演示](../examples/oh-my-research/demo/kimi-video-walkthrough.md#第-3-步审核-draft)

---

## 阶段 3：召回 Recall

### ✅ 提问技巧

OKS 使用 **Node-BM25**（node-level BM25，每个 `##` heading 一个 node），语义召回在 R@1 指标上反而不如字面匹配。好的提问方式：

1. **用自然语言**（不是关键词堆砌）
   - ✅ "Kimi K3 适合用来做文档分析吗？"
   - ❌ "Kimi K3 文档分析 成本 性能"

2. **包含上下文**
   - ✅ "我要设计智能文档分析系统，Kimi K3 适合吗？"
   - ❌ "Kimi K3"

3. **测试不同措辞**（paraphrase）
   - ✅ "Kimi K3 价格" / "Kimi K3 成本" / "Kimi K3 多少钱"
   - Node-BM25 会匹配到不同段落

4. **用 `--explain` 查看评分原因**
   ```bash
   oks recall "Kimi K3 成本" --explain
   ```
   - 查看 `token-overlap`, `idf-overlap`, `title-terms` 等因子
   - 理解为什么某个页面排在前面

### ❌ 为什么召回不准

三个最常见原因：

1. **Wiki 不存在**
   - Draft 还没晋升
   - 检查：`oks wiki list | grep <关键词>`
   - 解决：审核并晋升 Draft

2. **Query 偏差**（用词和 Wiki 不匹配）
   - Wiki 用"成本"，你问"价格"
   - Node-BM25 靠字面匹配，同义词需要 paraphrase
   - 解决：测试不同措辞

3. **类型权重**
   - `generic` 类型被降权 0.5（Soul Boost 注入层）
   - `concept/strategy` 类型被提权 1.5
   - 解决：调整 Wiki 的 `type` 字段

**Triple-Layer Recall 架构**：
- **Layer 1（召回层）**：Node-BM25 fts5 索引
- **Layer 2（注入层）**：Soul Boost（type×boost + review×1.2 + goal 重排）
- **Layer 3（衰减层）**：Memory Curve（type-specific λ → hot/warm/cold/evictable）

召回不准通常是 Layer 1 的问题（用词不匹配），不是 Layer 2/3。

### 💡 调优技巧

1. **Goal 加权**（Layer 2 注入层）
   - 设置 active goal 提升相关领域召回
   - 例：`oks config set active_goal master-ai-product-selection`
   - 或在 goal.md 中配置

2. **主动标记使用**
   - `oks wiki use <slug>` 提升使用记录
   - 增加 `review_bonus`（Layer 2）

3. **调整类型**
   - `concept` 权重 1.5（技术概念、产品特性）
   - `strategy` 权重 1.5（方法论、决策建议）
   - `generic` 权重 0.5（一般性内容）
   - 改 frontmatter 的 `type` 字段

4. **用 `--scope` 限定范围**
   ```bash
   oks recall "query" --scope computing
   ```
   - 只在 computing area 中召回

### 📸 实例：Kimi 知识召回

![召回结果](../examples/oh-my-research/assets/screenshots/05-recall.png)

```bash
$ oks recall "Kimi K3 成本" --limit 1 --explain
```

**结果**：
- **score=0.84**, relevance=1.92
- 准确召回 "Kimi K3 实测 — 1天烧完1个月算力，普通人慎买"
- 显示核心信息：20元/次、300+元/十几小时

**评分因子**（`--explain` 输出）：
- `token-overlap: 3` - Query 和 Wiki 有 3 个 token 重叠
- `idf-overlap: 1.00` - IDF 加权重叠度
- `title-terms: 2` - 标题中匹配 2 个词
- `type: conceptx0.6` - concept 类型（注：这里显示 0.6 是 decay 后，原始是 1.5）

👉 [查看完整演示](../examples/oh-my-research/demo/kimi-video-walkthrough.md#第-5-步测试召回)

---

## 完整案例：从 Kimi 视频到技术方案

### 真实演示（不是模拟）

我们用 B 站的 Kimi K3 实测视频，完整跑通了 OKS 全流程：

**时间线**：
1. 入库前：wiki 7 个，没有 Kimi 相关内容
2. 入库：B 站视频 → ASR 转写（220 段）→ Draft 生成
3. 审核：检查准确性和可复用性
4. 晋升：wiki 从 7 个增加到 8 个
5. 召回：`oks recall "Kimi K3 成本"` → score=0.84
6. 应用：基于召回知识设计技术方案
7. 对比：有 OKS vs 无 OKS 的 6 维度对比

**总耗时**：~7 分钟（其中 5 分钟是看视频）

**演示亮点**：
- ✅ B 站视频自动转文字（faster-whisper）
- ✅ AI 提取核心知识（成本数据、结论）
- ✅ 召回准确（相关性 0.84）
- ✅ 基于知识做技术选型（60,000元/月成本分析）

👉 **[查看完整演示（7 步 + 截图）](../examples/oh-my-research/demo/kimi-video-walkthrough.md)**

### 技术方案设计示例

![技术方案](../examples/oh-my-research/assets/screenshots/06-design-solution.png)

**问题**："我要设计一个智能文档分析系统，Kimi K3 适合吗？"

**AI 回答（基于 OKS 召回）**：

**优势**（来自 OKS）：
- 效果强：2026 WAIC 发布，最强国产大模型
- 应用开发能力：成功搭建律师事务所官网

**关键风险**（来自 OKS）：
- **成本极高**：20元/次
- **消耗速度快**：十几小时烧掉 300+ 元
- **核心结论**："普通用户我劝你别买，因为确实有点贵"

**成本估算**：
- 假设每天处理 100 个文档
- Kimi K3：20元/次 × 100 = **2,000元/天** = **60,000元/月**

**结论**：❌ 不推荐作为主力模型，建议用 Claude/GPT-4 等成本可控方案。

**知识来源标注**：
- ✅ 成本数据、"我劝你别买"：来自 OKS wiki 召回
- ⚠️ 替代方案（Claude/GPT-4）：基于通用知识

### 效果对比

![有 OKS vs 没有 OKS](../examples/oh-my-research/assets/screenshots/07-comparison-table.png)

| 维度 | 没有 OKS | 有 OKS |
|------|---------|--------|
| **知识来源** | AI 训练数据（可能过时） | 你看过的最新视频 |
| **成本数据** | 模糊（"可能比较贵"） | 具体（20元/次、300+元） |
| **可追溯性** | 无法验证 | 关联到原始视频 + Provider 链 |
| **时效性** | 依赖模型更新 | 看完视频立即可用 |
| **个性化** | 通用回答 | 基于你关注的特性 |
| **决策质量** | 缺乏依据 | 有理有据，引用具体数据 |

**核心收获**：从"看过这个视频"到"能用它做技术选型"，只需 7 分钟。

---

## 常见工作流

### 工作流 1：日常学习

**场景**：看技术文章、视频、课程，想把学到的东西记住。

**流程**：
```
1. 看到好文章/视频
   ↓
2. 收录到 OKS（对 Agent 说"收录这篇文章"）
   ↓
3. 周末集中审核 Drafts（15-30 分钟）
   ↓
4. 写方案/回答问题时自动召回
```

**技巧**：
- 平时只收集，不审核（降低心理负担）
- 每周固定时间审核（如周日晚上）
- 审核时批量处理（一次处理 5-10 个）

**示例**：
- 看了 10 个技术视频
- 收录到 Raw（10 分钟）
- 周末审核，晋升 3 个高价值 Wiki（20 分钟）
- 下周写方案时召回使用

### 工作流 2：技术选型

**场景**：需要选择技术方案，需要对比多个候选方案。

**流程**：
```
1. 列出候选方案（如 3 个 AI 模型）
   ↓
2. 收集每个方案的资料（官网、评测、视频）
   ↓
3. 沉淀每个方案的核心特性到 Wiki
   ↓
4. 召回对比 → 制作对比表 → 做出决策
```

**技巧**：
- 为每个方案建立 goal（提升相关召回）
- 用统一的结构记录（成本、性能、使用场景）
- 对比时用 `oks recall "方案 A vs 方案 B"`

**示例**：
- 候选：Kimi K3 / GPT-4 / Claude Opus
- 每个方案收集 2-3 份资料
- 沉淀为 3 个 Wiki 页面（核心特性 + 成本 + 场景）
- 召回对比 → 选出最合适方案

### 工作流 3：项目维护

**场景**：维护开源项目或团队代码库，需要记录决策和踩坑。

**流程**：
```
1. 每次重要决策 → 写决策文档 → 收录 OKS
   ↓
2. 踩坑后 → 补充 anti-pattern 到 Wiki
   ↓
3. 新人 onboarding → 召回项目知识
   ↓
4. 定期审查 → 更新过时知识
```

**技巧**：
- 用 `supersedes` 更新过时决策
- 用 `challenges` 记录争议点
- 建立项目 profile（在 `profiles/projects/` 下）

**示例**：
- 决策：为什么选择 PostgreSQL 而不是 MySQL
- 踩坑：PostgreSQL 在 Windows 上的性能问题
- 新人问："为什么用 PostgreSQL？" → 召回决策文档
- 半年后：PostgreSQL 15 解决了性能问题 → 更新 Wiki

### 工作流 4：团队协作

**场景**：团队共享知识库，避免重复踩坑。

**流程**：
```
1. 每个人维护自己的 OKS 实例
   ↓
2. 定期导出高价值 Wiki → 团队共享目录
   ↓
3. 其他人导入到自己的 OKS
   ↓
4. 团队会议时召回相关知识
```

**技巧**：
- 用 git 管理知识库（OKS 是文件系统）
- 建立团队 profile（在 `profiles/teams/` 下）
- 定期同步（如每周 sync 一次）

**注意**：
- OKS 设计为单人使用，多人共享需要约定规范
- 避免同时编辑同一个文件（用 git 解决冲突）
- 敏感信息不要放进共享知识库

---

## FAQ

### Q1: 为什么召回找不到我的知识？

**检查清单**：

1. ✅ **Draft 已晋升到 Wiki？**
   ```bash
   oks wiki list
   ```
   - 如果还在 Draft，先晋升

2. ✅ **Query 用词合适？**
   - 尝试不同措辞（paraphrase）
   - 用 `--explain` 查看评分详情

3. ✅ **类型权重合理？**
   - `generic` 类型被降权 0.5
   - 改为 `concept` 或 `strategy`

4. ✅ **Wiki 内容完整？**
   - 检查 Wiki 文件，确认关键词在正文中
   - Node-BM25 匹配每个 `##` heading 段落

**解决方案**：
```bash
# 查看评分详情
oks recall "你的问题" --explain

# 测试不同措辞
oks recall "Kimi 成本"
oks recall "Kimi 价格"
oks recall "Kimi 多少钱"

# 限定范围
oks recall "你的问题" --scope computing
```

### Q2: Draft 太多处理不过来？

**现状**：Draft 数量 > 20，不知道从哪开始。

**策略**：

1. **用 A/B/C 分级**
   - A 级（核心）：必须审核
   - B 级（有用）：选择性审核
   - C 级（参考）：批量 reject

2. **批量 reject 明显不合适的**
   ```bash
   oks drafts list
   # 找出不需要的
   oks drafts reject <slug1>
   oks drafts reject <slug2>
   ```

3. **定期清理**
   - 每周审核一次
   - 超过 1 个月的 Draft 要么晋升要么 reject

**时间估算**：
- 5-10 个 Draft：15-30 分钟
- 20+ Draft：建议分两次审核

### Q3: 如何批量处理历史资料？

**场景**：有大量历史文档/视频/笔记，想全部导入 OKS。

**建议**：

❌ **不要一次性导入**
- 会生成大量 Draft
- 审核负担太重
- 容易放弃

✅ **分批处理**
1. **优先处理最近 3 个月的**
   - 记忆最清晰
   - 最有可能用到

2. **旧资料可以只保留 Raw**
   - 不一定要生成 Wiki
   - 需要时再召回 Raw

3. **用主题分批**
   - 这周处理"AI 相关"
   - 下周处理"数据库相关"

**时间安排**：
- 每周处理 5-10 份资料
- 3 个月处理 60-120 份
- 比一次性处理更可持续

### Q4: 成本和性能如何？

**存储成本**：
- 视频转写：约 100KB/分钟（纯文本）
- Wiki 页面：约 2-5KB/页
- Raw Bundle：取决于资料类型

**召回性能**：
- 50 个 Wiki：< 100ms
- 500 个 Wiki：< 500ms
- Node-BM25 fts5 索引，不随 Wiki 数量线性增长

**ASR 成本**（视频转写）：
- faster-whisper 本地运行：**免费**
- tiny 模型：快速，略有误差
- base/small 模型：准确，较慢

**推荐配置**（个人使用）：
- 知识库：1000-2000 个 Wiki
- Raw 文件：无上限（按需保留）
- 硬盘空间：10-50GB

### Q5: 如何处理知识更新？

**场景**：Kimi 发布新版本 K3.5，旧的 K3 知识怎么办？

**策略**：

1. **用 `supersedes` 标注替代关系**
   ```yaml
   ---
   title: Kimi K3.5 新特性
   supersedes: kimi-k3-features
   ---
   ```
   - 旧知识自动标记为 `archived`
   - 召回时优先返回新知识

2. **用 `enriches` 补充细节**
   ```yaml
   ---
   title: Kimi K3 在法律场景的应用
   enriches: kimi-k3-features
   ---
   ```
   - 两个知识都保持 `active`
   - 召回时一起返回

3. **用 `challenges` 记录争议**
   ```yaml
   ---
   title: Kimi K3 成本优化后可接受
   challenges: kimi-k3-cost-warning
   ---
   ```
   - 两个观点并存
   - 用 `human_reviewed_at` 判断优先级

**实践建议**：
- 不要删除旧知识（改为 `archived`）
- 保留演进历史（可追溯）
- 定期审查（每季度一次）

### Q6: OKS 适合团队使用吗？

**设计定位**：OKS 是**个人知识管理工具**，设计为单人使用。

**团队使用的挑战**：
- ❌ 没有权限管理
- ❌ 没有冲突解决机制
- ❌ 没有协作审核流程

**可行的团队模式**：

1. **各自维护 + 定期同步**
   - 每人维护自己的 OKS 实例
   - 定期导出高价值 Wiki → 共享目录
   - 其他人选择性导入

2. **用 git 管理共享知识库**
   - OKS 是文件系统，天然支持 git
   - 用 PR 流程审核知识
   - 用 git 解决冲突

3. **建立团队规范**
   - 统一的 Wiki 模板
   - 明确的审核标准
   - 定期的知识同步会议

**推荐实践**：
- 个人知识：自己的 OKS
- 团队知识：共享 git repo（手动维护）
- 不要把 OKS 当成团队 Wiki（用 Notion/Confluence）

### Q7: 如何备份和迁移？

**备份**：
- OKS 是纯文件系统
- 直接备份整个目录即可
- 推荐：用 git 版本管理

**迁移**：
```bash
# 导出整个知识库
tar -czf my-oks-backup.tar.gz my-knowledge-base/

# 在新机器上
tar -xzf my-oks-backup.tar.gz
cd my-knowledge-base
oks status  # 确认正常
```

**注意事项**：
- `wiki/` 和 `raw/` 是核心数据
- `drafts/` 可以选择性备份
- `.git/` 包含版本历史

**云同步**：
- 可以用 Dropbox/iCloud/OneDrive
- 但要注意 git 冲突
- 推荐：主动 push/pull，不要自动同步

---

## 延伸阅读

### 算法与架构
- **[Triple-Layer Recall](algorithms/recall-engine.md)** - Node-BM25 召回 + Soul Boost 注入 + Memory Curve 衰减
- **[召回评估](algorithms/recall-evaluation.md)** - 50-case 消融实验，R@1=82.5%, MRR=0.907
- **[CONSTITUTION](concepts/constitution.md)** - P0-P11 不变式，A1-A5 记忆架构

### 使用指南
- **[记忆管理](usage/memories.md)** - Wiki 生命周期、类型、衰减
- **[上下文注入](usage/context-injection.md)** - Hook 机制、注入时机
- **[CLI 命令](reference/cli.md)** - 完整命令参考

### 真实案例
- **[托管你的学习](../examples/oh-my-research/)** - 新手入门，从 Kimi 视频到技术方案
- **[托管你的 GitHub](../examples/oh-my-github/)** - 技术决策沉淀
- **[托管你的飞书](../examples/oh-my-feishu/)** - 手机表单采集 + IM 审核

---

## 社区与支持

- **GitHub Discussions**: [提问和讨论](https://github.com/open-agent-power/open-knowledge-studio/discussions)
- **Issues**: [报告问题](https://github.com/open-agent-power/open-knowledge-studio/issues)
- **贡献指南**: [CONTRIBUTING.md](https://github.com/open-agent-power/open-knowledge-studio/blob/main/CONTRIBUTING.md)

---

**最后提醒**：OKS 不是魔法。它不会自动让你"记住所有东西"。它的价值在于：把你**真正看过、真正理解**的内容，变成**未来能重新找到、实际能用**的知识。

把时间花在阅读、理解、审核上，而不是收集和整理上。这才是知识管理的本质。
