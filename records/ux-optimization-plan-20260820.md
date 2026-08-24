# 用户体验优化方案

**分析时间**: 2026-08-20  
**核心问题**: 1. Agent 原生指引不够 2. 首页布局凌乱 3. 截图质量差

---

## 问题 1：Agent 原生指引不足

### 现状分析

**当前问题**：
- `first-knowledge-loop.md` 内容偏 CLI（命令行）
- 用户不知道"如何用 Agent 操作 OKS"
- 缺少对话式操作示例

**示例对比**：

❌ **当前写法**（偏 CLI）：
```markdown
## 1. 交给 Agent

在知识库目录中，把文件或 URL 交给兼容 Agent：

> 收录这份资料。保留来源证据，生成 Candidate 后停下来让我审核。

如果要先显式创建工作区：
```bash
oks ingest prepare <文件或URL>
```
```

✅ **应该这样写**（Agent 原生）：
```markdown
## 1. 告诉 Agent 收录资料

打开 Claude Code / Codex，直接说：

> "把这篇文章收录进我的 OKS：https://example.com/article"

或者：

> "收录这个 PDF 文件，生成候选后让我审核"

**Agent 会做什么**：
1. 读取 `/ingest` Skill
2. 提取内容（文字、元数据）
3. 生成 Candidate
4. 告诉你 Candidate 在哪

**你不需要**：
- ❌ 记命令（oks ingest prepare）
- ❌ 管理文件路径
- ❌ 手动运行命令

**完全对话式**：像跟人说话一样。
```

---

### 优化方案

#### A. 重写 `docs/start-here.md`

**新标题**: 从这里开始（Agent 原生版）

**新结构**：
```markdown
# 从这里开始

> OKS 是 Agent 原生的。你通过**对话**使用它，不是命令行。

## 第一步：装好 OKS

[安装指南](installation.md) — 一个命令，2 分钟

---

## 第二步：跟 Agent 说话

打开你的 Agent（Claude Code / Codex / Cursor），说：

### 场景 1: 收录网页
```
你: "把这篇技术文章收录进 OKS：https://..."

Agent: 
  ✓ 提取内容
  ✓ 生成 Candidate
  → Candidate 在 drafts/20260820-xxx.md
```

### 场景 2: 收录视频
```
你: "收录这个 B 站视频"

Agent:
  ✓ 提取字幕
  ✓ 生成知识要点
  → Draft 已生成，请审核
```

### 场景 3: 审核 Candidate
```
你: "看看有哪些 Draft"

Agent: 
  → 显示 Draft 列表

你: "这个看起来不错，晋升到 Wiki"

Agent:
  ✓ 晋升成功
  → wiki/computing/concepts/xxx.md
```

### 场景 4: 召回知识
```
你: "帮我设计一个 XX 系统，需要用到 YY 技术"

Agent:
  🔍 自动召回相关知识
  → 基于你的知识库给建议
```

---

## 常见误区

❌ **错误理解**："我要学命令行"  
✅ **正确理解**："我只需要跟 Agent 说话"

❌ **错误理解**："OKS 是个复杂工具"  
✅ **正确理解**："OKS 是个安静的助手，Agent 帮你用它"

---

## 下一步

- **跑通一次完整流程**：[第一个知识闭环](first-knowledge-loop.md)
- **看真实案例**：[7 分钟：视频 → 技术方案](../examples/oh-my-research/demo/kimi-video-walkthrough.md)
- **遇到问题**：[故障排查](verify.md)
```

#### B. 重写 `docs/first-knowledge-loop.md`

**核心改进**：
- 每一步都用**对话示例**
- 突出 Agent 做了什么
- 弱化 CLI 命令（放到"技术细节"折叠区）

---

## 问题 2：首页布局凌乱

### 现状分析

**凌乱的原因**（基于 index.md）：

1. **信息过载**：
   - "按需要深入"部分堆了 30+ 链接
   - 一行挤了 7-8 个链接
   - 没有视觉分组

2. **层级不清**：
   - "开始使用" vs "使用 OKS" 区别不明显
   - "召回质量"技术细节放在导航区

3. **缺少视觉引导**：
   - 纯文字链接
   - 没有图标、颜色分区
   - 新手不知道从哪开始

---

### 优化方案

#### 新首页结构

```markdown
# Open Knowledge Studio

> Agent 把资料变成知识，人审核，未来能召回

<div align="center">
  <img src="assets/oks-logo-readme.png" width="360" alt="OKS">
</div>

---

## 🚀 3 条清晰路径

### 路径 1: 第一次用？从这开始

| 步骤 | 做什么 | 时间 |
|------|--------|------|
| 1️⃣ | [安装 OKS](installation.md) | 2 分钟 |
| 2️⃣ | [跑通第一个闭环](first-knowledge-loop.md) | 5 分钟 |
| 3️⃣ | [看真实案例](../examples/oh-my-research/demo/kimi-video-walkthrough.md) | 10 分钟 |

**总耗时**：17 分钟，完全理解 OKS

---

### 路径 2: 已经装好？开始用

**常用操作**：
- 📥 [收录资料](first-knowledge-loop.md#1-交给-agent) - 跟 Agent 说"收录这个"
- ✅ [审核 Candidate](review-candidates.md) - 决定哪些进入知识库
- 🔍 [召回知识](recall.md) - Agent 自动注入，或手动召回
- 💡 [最佳实践](best-practices.md) - 三个阶段，三个原则

**进阶**：
- 📊 [上下文注入机制](usage/context-injection.md)
- 🎯 [配置 Goal 和 Profile](usage/profiles.md)

---

### 路径 3: 遇到问题？这里排查

| 问题 | 解决 |
|------|------|
| 装不上 | [安装故障](reference/troubleshooting.md#安装) |
| 召回不准 | [召回调优](best-practices.md#阶段-3召回-recall) |
| Agent 报错 | [验证 OKS 状态](verify.md) |

---

## 📚 深入了解

<details>
<summary><strong>概念和原理</strong>（点击展开）</summary>

- [设计哲学](concepts/philosophy.md) - 为什么这样设计
- [记忆模型](concepts/memory-model.md) - Raw vs Wiki
- [Triple-Layer Recall](algorithms/recall-engine.md) - R@1=82.5%
- [文件系统范式](concepts/file-system-paradigm.md)

</details>

<details>
<summary><strong>真实案例</strong>（点击展开）</summary>

| 场景 | 你在托管什么 |
|------|-------------|
| [托管你的学习](../examples/oh-my-research/) | 文章、视频、课程 |
| [托管你的 GitHub](../examples/oh-my-github/) | 技术决策、踩坑记录 |
| [托管你的飞书](../examples/oh-my-feishu/) | 手机表单 + IM 审核 |

[更多案例](examples.md)

</details>

<details>
<summary><strong>技术参考</strong>（点击展开）</summary>

- [CLI 命令](reference/cli.md)
- [Ingest 协议](reference/ingest.md)
- [召回评估数据](algorithms/recall-evaluation.md)

</details>

---

## 🎯 OKS 核心边界

> Agent-native、文件系统优先的知识工作台

**OKS 做什么**：
- ✅ 保留来源（Raw + 可追溯证据）
- ✅ 提出知识（Agent 生成 Candidate）
- ✅ 人工审核（Candidate → Wiki）
- ✅ 自动召回（Hook 注入会话）

**OKS 不做什么**：
- ❌ Core 不调用 AI API
- ❌ 不包装失败为成功
- ❌ 不由模型自行声明 `[verified]`

---

**流程**：`资料 → Candidate → 人工审核 → Wiki → Recall 注入`
```

---

## 问题 3：截图质量问题

### 现状分析

**问题截图审查**：

#### 1. `06-design-solution.png` (53 KB)
- ❌ **问题**：HTML 渲染的假截图
- ❌ **内容**：表格、颜色、Badge 都是我生成的
- ❌ **不真实**：不是真实的 Agent 对话

#### 2. `07-comparison-table.png` (237 KB)
- ❌ **问题**：纯表格，没有上下文
- ❌ **视觉**：渐变色卡片式，太"设计感"
- ❌ **不协调**：与其他截图风格不一致

#### 3. `01-before-status.png` (25 KB)
- ✅ **可以接受**：真实的终端输出
- ⚠️ **可改进**：缺少标注

#### 4. `05-recall.png` (43 KB)
- ✅ **可以接受**：真实的召回结果
- ⚠️ **可改进**：关键数字（0.84）需要高亮

---

### 优化方案

#### A. 需要重新截图的（你来做）

**优先级 1：Agent 对话截图**

1. **技术方案设计对话**
   - 替代：`06-design-solution.png`
   - **怎么截**：
     ```
     你: "我要设计智能文档分析系统，Kimi K3 适合吗？"
     
     Agent: 
     🔍 召回了 1 个相关知识
     
     [显示召回的 Wiki 内容]
     
     基于你的知识库，Kimi K3 不适合...
     成本：20元/次 × 100文档/天 = 2000元/天
     
     建议：Claude Opus / GPT-4
     ```
   - **截图内容**：
     - 完整的对话窗口（你的问题 + Agent 回答）
     - 显示 "🔍 召回" 标记
     - 显示具体数字和结论
   - **格式**：真实的 Claude Code / Codex 界面
   - **标注**：用红框标注关键部分（成本数字、结论）

2. **收录过程截图**
   - 替代：缺失的入库步骤
   - **怎么截**：
     ```
     你: "收录这个 B 站视频：https://..."
     
     Agent:
     ✓ 读取视频元数据
     ✓ 提取字幕（220 段）
     ✓ 生成 Draft: kimi-k3-实测
     
     → Draft 已保存，请审核
     ```
   - **截图内容**：Agent 执行过程
   - **标注**：3 个步骤用数字标注

3. **审核 Draft 截图**
   - 替代：缺失的审核过程
   - **怎么截**：
     ```
     你: "看看 Draft 内容"
     
     [Agent 显示 Draft 内容]
     
     你: "可以，晋升"
     
     Agent: ✓ 已晋升到 wiki/
     ```

**优先级 2：终端截图优化**

4. **召回结果 - 添加标注**
   - 现有：`05-recall.png`
   - **优化**：
     - 用红框标注 `score=0.84`
     - 用箭头指向关键信息（成本数据）
     - 添加文字说明："相关性评分"

5. **对比图 - 简化**
   - 现有：`07-comparison-table.png`
   - **问题**：太"设计感"，不真实
   - **替代方案**：
     - 方案 1：Markdown 表格（不需要截图）
     - 方案 2：简单的文字对比（左右分栏）
     - 方案 3：删除这张图，用文字说明

---

#### B. 可以保留的（需要微调）

保留但添加标注：
- `01-before-status.png` - 添加"入库前状态"标题
- `04-wiki-list.png` - 用红框标注新增条目
- `04-promote-success.png` - 用红框标注行数变化（7→8）

---

#### C. 标注工具推荐

**Windows**:
- **Snagit** (付费，专业)
- **ShareX** (免费，功能强大)
- **画图 3D** (系统自带)

**标注元素**：
- 🔴 红色矩形框 - 标注关键区域
- ➡️ 箭头 - 指向重点
- 📝 文字说明 - 简短解释
- 🔢 数字标记 - 标注步骤顺序

---

## 📋 执行计划

### 阶段 1: 重写 Agent 原生指引（我来做）
- [ ] 重写 `start-here.md`（Agent 原生版）
- [ ] 重写 `first-knowledge-loop.md`（对话示例）
- [ ] 更新 `best-practices.md` 的链接

**预期**：2 小时

---

### 阶段 2: 优化首页布局（我来做）
- [ ] 重写 `index.md`（3 条路径 + 折叠区）
- [ ] 测试 GitHub Pages 效果

**预期**：1 小时

---

### 阶段 3: 重新截图（你来做）
- [ ] Agent 对话截图（3 张）
- [ ] 终端截图标注（2 张）
- [ ] 删除/替换假截图（2 张）

**预期**：30 分钟

---

## 📊 预期效果

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| **Agent 原生感** | 30% | **90%** |
| **首页可读性** | 40% | **85%** |
| **截图真实性** | 50% | **95%** |
| **新手友好度** | 50% | **90%** |

---

## 下一步

你希望我：
**A. 立即重写 Agent 原生指引（阶段 1）**  
**B. 立即优化首页布局（阶段 2）**  
**C. 先给你一个完整的截图清单和标注规范（阶段 3 准备）**  
**D. 全部一起做**
