# Claude 能力增强配置方案

**目标**: 提升文档设计和迭代能力，基于现有内容优化而非大规模重构

---

## 📋 推荐配置清单

### 1. Karpathy Guidelines（强烈推荐）✅

**来源**: https://github.com/multica-ai/andrej-karpathy-skills

**核心原则**:
- **Think Before Coding**: 先理解现有代码/文档，再修改
- **Simplicity First**: 避免过度工程化
- **Surgical Changes**: 外科手术式修改，只改必要的部分
- **Goal-Driven**: 明确成功标准

**为什么需要**:
- ❌ 我刚才的问题：大规模重构（711行 → 拆分成10个文件）
- ✅ 应该做：基于现有文档，优化排版和结构

**安装方式**:
```bash
# 下载到 .claude/skills/
curl -o .claude/skills/karpathy-guidelines.md \
  https://raw.githubusercontent.com/multica-ai/andrej-karpathy-skills/main/skills/karpathy-guidelines/SKILL.md
```

---

### 2. 文档设计最佳实践（自定义 Skill）✅

**内容**: 基于 Notion 文档设计研究，但应用于**优化现有文档**

**核心原则**:
```markdown
# 文档优化原则

## 1. 保留现有结构
- ✅ 在现有文档基础上改进
- ❌ 不要大规模重构文件结构

## 2. 渐进式改进
- 一次只改 1-2 个文档
- 每次改进后让用户确认

## 3. 优化重点
- 排版：表格、列表、Callout
- 结构：清晰的标题层级
- 导航：文档之间的链接
- 长度：过长文档（>300行）考虑拆分

## 4. 改进前必做
- Read 原文档
- 理解文档演进历史（git log）
- 确认用户意图
```

---

### 3. MCP 工具推荐

#### A. Librarian MCP（可选）⚙️

**来源**: https://github.com/ngmeyer/librarian-mcp

**功能**: Obsidian vault 管理，支持 wikilinks、图谱、搜索

**为什么考虑**: OKS 是文件系统知识库，与 Obsidian 类似

**暂不推荐原因**: 
- OKS 已有自己的召回系统
- 避免引入冲突的知识管理机制

#### B. AgentKey 工具（已有）✅

**当前状态**: 已配置并可用

**相关工具**: Web search, documentation tools

**保持现状**: 不需要额外配置

---

## 📝 实施计划

### 阶段 1: 安装 Karpathy Guidelines（立即）

```bash
# 1. 创建 skills 目录
mkdir -p .claude/skills/

# 2. 下载 Karpathy Guidelines
curl -o .claude/skills/karpathy-guidelines.md \
  https://raw.githubusercontent.com/multica-ai/andrej-karpathy-skills/main/skills/karpathy-guidelines/SKILL.md

# 3. 验证
cat .claude/skills/karpathy-guidelines.md | head -20
```

### 阶段 2: 创建文档优化 Skill（立即）

在 `.claude/skills/doc-optimization.md` 创建自定义 Skill：

```markdown
# 文档优化指南

## 触发条件
用户要求"优化文档"、"改进排版"、"重构文档"时使用

## 核心原则
1. **Read First**: 必须先完整阅读原文档
2. **Understand History**: 用 git log 查看演进历史
3. **Incremental**: 一次只改 1-2 个文档
4. **Preserve Value**: 保留现有宝贵经验

## 操作流程
1. 询问用户具体目标（排版？结构？长度？）
2. Read 原文档，理解上下文
3. 提出 2-3 个具体改进点
4. 征求用户同意后再执行
5. 改进后让用户确认

## 禁止行为
- ❌ 未经同意大规模重构
- ❌ 删除现有内容（除非明确冗余）
- ❌ 改变文档核心结构（除非用户明确要求）
```

### 阶段 3: 应用到 OKS 文档优化（用户确认后）

**具体改进方向**（需要你确认）:

1. **best-practices.md 优化**（不拆分文件）
   - 添加目录（TOC）
   - 用表格替代长段落
   - 添加 Callout 突出重点
   - 保持 711 行原样，只优化排版

2. **首页 index.md 优化**
   - 3 条路径更清晰
   - 添加视觉分隔
   - 保持现有导航结构

3. **添加快速入门**（如果需要）
   - 在现有 quick-start.md 基础上改进
   - 不新建目录

---

## ✅ 待审核项

请你审核以下内容，确认后我再安装：

### 1. 安装 Karpathy Guidelines？
- [ ] 同意安装
- [ ] 需要修改（请说明）
- [ ] 不需要

### 2. 创建文档优化 Skill？
- [ ] 同意创建
- [ ] 需要修改内容（请说明）
- [ ] 不需要

### 3. 文档优化方向？
选择你想要的改进方向：
- [ ] best-practices.md: 只优化排版，不拆分文件
- [ ] index.md: 优化首页导航
- [ ] quick-start.md: 改进快速入门
- [ ] 其他（请说明）

### 4. 其他 MCP 工具？
- [ ] 需要安装 Librarian MCP（Obsidian 集成）
- [ ] 暂时不需要其他 MCP
- [ ] 其他建议（请说明）

---

## 🎯 预期效果

安装后，当你说"优化文档"时，我会：

1. ✅ 先询问具体目标
2. ✅ Read 现有文档，理解历史
3. ✅ 提出 2-3 个具体改进点
4. ✅ 等你确认后再执行
5. ✅ 渐进式改进，保留现有价值

而不是：
- ❌ 直接大规模重构
- ❌ 拆分成 10 个新文件
- ❌ 删除现有内容

---

## 📚 参考资源

**Karpathy Guidelines**:
- 官方仓库: https://github.com/multica-ai/andrej-karpathy-skills
- SKILL.md: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/skills/karpathy-guidelines/SKILL.md
- CLAUDE.md: https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md

**Notion 文档设计研究**:
- Building a modern knowledge base: https://www.notion.com/blog/how-notion-uses-notion-building-a-modern-flexible-knowledge-base
- Documentation best practices: https://www.notion.com/use-case/project-management/project-documentation

**Librarian MCP**:
- GitHub: https://github.com/ngmeyer/librarian-mcp

---

请告诉我你的审核意见，我会根据你的反馈安装和配置。
