# MCP 和 Skills 调研报告

**调研时间**: 2026-08-20  
**目标**: 找到适合文档优化的 MCP 服务器和 Skills

---

## ✅ 已安装

### 1. Karpathy Guidelines
- **路径**: `.claude/skills/karpathy-guidelines.md`
- **功能**: 避免过度工程化、外科手术式修改
- **状态**: ✅ 已安装

### 2. 文档优化 Skill
- **路径**: `.claude/skills/doc-optimization.md`
- **功能**: 渐进式文档优化指南
- **状态**: ✅ 已创建

---

## 🔍 调研发现的推荐工具

### A. MCP 服务器

#### 1. **Docs MCP Server** （推荐）⭐
- **来源**: https://skywork.ai/blog/docs-mcp-server-ultimate-guide/
- **功能**: 
  - 文档语义搜索
  - 引用和章节查找
  - 文档作为 Resources 暴露
- **适用场景**: 大型文档库的搜索和引用
- **评估**: OKS 已有自己的 recall 系统，可能不需要

#### 2. **Gemini MCP** （可选）
- **来源**: https://ai.google.dev/gemini-api/docs/coding-agents
- **功能**: 访问最新 API 文档
- **评估**: 不适合 OKS（我们是文档优化，不是 API 集成）

#### 3. **Librarian MCP** （已调研）
- **来源**: https://github.com/ngmeyer/librarian-mcp
- **功能**: Obsidian vault 管理、图谱、wikilinks
- **评估**: 与 OKS 功能重叠，暂不推荐

### B. Skills

#### 4. **Technical Writing Best Practices** （需要创建）⚙️
- **功能**: 
  - 技术术语通俗化指南
  - 复杂概念拆解技巧
  - 代码示例编写规范
- **状态**: 可以基于调研创建

#### 5. **Markdown Linting Skill** （可选）
- **功能**: 
  - 检查 Markdown 格式
  - 链接有效性验证
  - 标题层级检查
- **状态**: 可以集成到 doc-optimization.md

---

## 📊 工具对比

| 工具 | 类型 | 成本 | 适用性 | 推荐度 |
|------|------|------|--------|--------|
| Karpathy Guidelines | Skill | 免费 | ✅ 高 | ⭐⭐⭐⭐⭐ |
| Doc Optimization | Skill | 免费 | ✅ 高 | ⭐⭐⭐⭐⭐ |
| Docs MCP Server | MCP | 免费 | ⚠️ 中 | ⭐⭐⭐ |
| Librarian MCP | MCP | 免费 | ❌ 低（冲突） | ⭐⭐ |
| Technical Writing | Skill | 免费 | ✅ 高 | ⭐⭐⭐⭐ |

---

## 🎯 推荐配置

### 当前阶段（已完成）✅
1. ✅ Karpathy Guidelines
2. ✅ Doc Optimization Skill

### 下一步（可选）⚙️
3. 创建 Technical Writing Skill
4. 集成 Markdown Linting 到现有 Skill

### 暂不推荐 ❌
- Docs MCP Server（OKS 已有 recall）
- Librarian MCP（功能重叠）
- Gemini MCP（不相关）

---

## 📚 参考资源

**MCP 和 Skills 设计**:
- Claude Skills + MCP Servers: https://codersera.com/blog/claude-skills-mcp-servers-practitioner-guide-2026/
- Extending Claude with Skills: https://claude.com/blog/extending-claude-capabilities-with-skills-mcp-servers
- Best Plugins 2026: https://www.turbodocx.com/blog/best-claude-code-skills-plugins-mcp-servers

**文档设计**:
- Docs MCP Ultimate Guide: https://skywork.ai/blog/docs-mcp-server-ultimate-guide/
- Claude MCP Guide: https://www.datacamp.com/tutorial/claude-mcp

---

## 结论

**当前配置已足够**：
- Karpathy Guidelines 解决"过度工程"问题
- Doc Optimization Skill 提供文档优化框架
- 无需额外 MCP（OKS 已有完善功能）

**建议**: 立即用现有配置开始优化文档，根据实际需求再考虑补充工具。
