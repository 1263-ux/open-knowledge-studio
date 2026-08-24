# 截图方案分析

**需求**: 补充 OKS 真实使用流程的截图

---

## 🎯 目标截图清单

### 1. Agent 对话截图（最重要）
**需要展示**:
- 用户: "收录这个 B站视频"
- Agent: 执行步骤（提取、生成 Candidate）
- Agent: 召回知识并给出建议

**问题**: 
- Playwright 只能操作浏览器
- Claude Code 是桌面应用，无法自动化

---

## 💡 可行方案

### 方案 A: 混合方案（推荐）

**Playwright 部分**（我来做）:
1. ✅ GitHub Pages 文档效果图
2. ✅ OKS 项目主页截图
3. ✅ 对比表格渲染效果

**手动截图部分**（你来做）:
1. ⚠️ Claude Code 对话截图（3 张）
   - 收录视频对话
   - 审核 Draft 对话  
   - 召回知识对话

**CLI 截图部分**（我可以做）:
1. ✅ `oks status` 输出
2. ✅ `oks capability status` 输出
3. ✅ `oks recall` 结果

---

### 方案 B: 纯 CLI 演示（备选）

**优点**: 完全自动化
**缺点**: 不够直观，缺少 Agent 对话感

用终端截图工具截取：
```bash
# 1. 状态检查
oks status

# 2. 能力检查
oks capability status

# 3. 召回演示
oks recall "Kimi K3 适合用来做文档分析吗？" --explain
```

---

### 方案 C: 使用 DSH (Claude Design + OKS)

你提到的 **dsh-oks 插件** - 这个我不太了解。

**如果 DSH 能**:
- ✅ 在设计工具中展示 OKS 流程
- ✅ 自动化 Agent 对话截图
- ✅ 生成高质量的演示图

那这是最好的方案！

**你能告诉我**:
1. dsh-oks 插件在哪？
2. 它能做什么？
3. 如何使用它来截图？

---

## 🤔 我的建议

**立即可做**（我来）:
1. 用 CLI 截图补充技术细节
2. 用 Playwright 截 GitHub Pages 效果
3. 整理现有的好截图

**需要你协助**（手动或 DSH）:
1. Agent 对话截图（最重要的 3 张）
2. 如果 DSH 能做，教我怎么用

---

你希望：
**A. 我先用 CLI 做一批终端截图**（技术演示）  
**B. 你教我 DSH-OKS 插件怎么用**（如果能自动化 Agent 对话）  
**C. 你手动截 Agent 对话，我做其他部分**

选哪个？
