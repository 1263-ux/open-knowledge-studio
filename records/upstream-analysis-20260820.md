# 上游文档演进分析报告

**分析时间**: 2026-08-20  
**分析对象**: open-agent-power/open-knowledge-studio upstream/main

---

## 🔍 关键发现

### 1. best-practices.md **不存在于上游**
```bash
git show upstream/main:docs/best-practices.md
# ❌ 文件不存在
```

**结论**: 
- ✅ **best-practices.md 是我们今天新创建的**
- ✅ 不会与上游冲突
- ⚠️ 但需要确认是否符合上游文档风格

---

### 2. 上游文档演进特点

#### 高频修正（过去 2 个月）
```
f6fc26c docs: 纠正 6+1 过时描述——recall-engine 重写 + 8 文件 14 处修正
72a0d4c docs: 修正残留过时 P@3=96% → 真实消融 R@1=0.825 (11 处)
966c229 docs: delete orphan effectiveness page; fix stale IDF/BM25/decay/bundle claims
```

**模式**: 
- 频繁修正过时描述
- 删除孤立页面
- 修正技术指标（P@3 → R@1）

**启示**: 
- ⚠️ **上游文档在快速迭代中**
- ⚠️ 算法描述经常需要对齐实现
- ⚠️ 评估指标可能变化

---

#### 重大重构（过去 3 个月）

```
bedcf5c docs: reorganize per nowledge structure, drop unimplemented features
76c7986 docs(algorithms): keep only real algorithms, rewrite per depth template
356033f docs: align concepts with AI Agent Book ch3, add tradeoff rationale
```

**模式**:
- 删除未实现功能的文档
- 按 nowledge 结构重组
- 与 AI Agent Book 对齐

**启示**:
- ⚠️ **文档结构已经过深思熟虑的重组**
- ⚠️ 有明确的参考标准（nowledge, AI Agent Book）
- ❌ **不应该再次大规模重构**

---

### 3. 上游文档维护原则（从 commit 历史推断）

#### A. 准确性优先
```
ceaa555 docs: recall-evaluation 加 embedding backend 对比（语义召回反不如字面 BM25）
935ed5e docs: 最后一处 cli.md fusion P@3=90% → R@1=0.805
```

**原则**: 文档必须与实现精确对齐

#### B. 删除优于保留
```
966c229 docs: delete orphan effectiveness page; fix stale IDF/BM25/decay/bundle claims
bedcf5c docs: reorganize per nowledge structure, drop unimplemented features
```

**原则**: 宁可删除过时/孤立内容，不保留误导信息

#### C. 结构稳定性
```
d88b7f9 docs: restore cases nav on index
6fe0447 docs: separate published docs from reusable examples
```

**原则**: 导航结构经过多次恢复/调整，现在相对稳定

---

## ⚠️ 我们的问题

### 已做的事（需要重新评估）

1. **✅ 创建 best-practices.md** (711 → 488 行)
   - 上游没有这个文件
   - ✅ 不冲突
   - ⚠️ 但需要确认是否符合上游风格

2. **❌ 创建 getting-started/ 和 guides/ 目录**
   - 上游刚刚完成 "reorganize per nowledge structure"
   - ❌ **与上游重组方向可能冲突**
   - ❌ **不应该引入新的目录结构**

3. **❌ 创建 RESTRUCTURE-REPORT.md**
   - 记录了我们的大规模重构
   - ❌ **这本身就违反了上游的稳定性原则**

---

## 🎯 修正建议

### 立即行动

#### 1. **撤销不当重构**
```bash
# 删除我们创建的新目录和文件
git rm -r docs/getting-started/
git rm -r docs/guides/
git rm docs/index-v2.md
git rm docs/best-practices-v2.md
git rm docs/RESTRUCTURE-REPORT.md
```

#### 2. **保留有价值的内容**
- ✅ **best-practices.md** (优化后的 488 行版本)
  - 这是新增内容，不与上游冲突
  - 但需要精简到符合上游风格

- ✅ **examples/oh-my-research/demo/** (Kimi 演示)
  - 这是 examples/ 内容，上游鼓励
  - 截图和演示文档都保留

#### 3. **对齐上游风格**

基于上游最近的 commit 模式，best-practices.md 应该：

**当前问题**:
- ❌ 488 行仍然偏长
- ❌ 包含大量"如何使用"内容（可能与现有文档重复）

**对齐方向**:
- ✅ 精简到 150-200 行
- ✅ 聚焦"核心原则"，不是"详细教程"
- ✅ 链接到现有文档（start-here.md, first-knowledge-loop.md）
- ✅ 避免与现有文档重复

---

## 📋 正确的优化策略

### 原则（基于上游历史）

1. **不创建新目录结构**
   - 上游刚完成重组，结构已稳定

2. **不大规模重写现有文档**
   - 上游文档经过多次对齐和修正
   - 每次修改都有明确的对齐目标（实现、指标、参考书）

3. **只做外科手术式优化**
   - 修正过时信息
   - 优化排版（表格、列表、Callout）
   - 精简冗余说明

4. **新增内容需要明确价值**
   - best-practices.md 可以保留，但需要精简
   - 确保不与现有文档重复

---

## ✅ 修正后的计划

### 阶段 1: 清理不当内容（立即）
1. 删除新创建的目录（getting-started/, guides/）
2. 删除重构报告
3. 删除备选版本（index-v2.md, best-practices-v2.md）

### 阶段 2: 精简 best-practices.md（今天）
- 从 488 行精简到 150-200 行
- 聚焦核心原则（三阶段）
- 大量链接到现有文档
- 删除与现有文档重复的内容

### 阶段 3: 外科手术式优化现有文档（明天）
- 只优化排版（表格、Callout）
- 不改变结构
- 不重写内容
- 每次修改 < 20 行

---

## 🚨 教训

1. **应该先查看上游历史再行动**
   - 我们违反了这一点

2. **文档是项目根基，改动要慎重**
   - 你的提醒非常正确

3. **理解上游的演进方向**
   - 上游正在删除和精简，不是扩展

4. **Karpathy Guidelines 的价值**
   - "Think Before Coding" - 我们没做到
   - "Surgical Changes" - 我们做过头了

---

## 下一步

请确认修正方案：
- [ ] **同意删除不当的新目录和文件**
- [ ] **保留 best-practices.md，但进一步精简到 150-200 行**
- [ ] **保留 examples/oh-my-research/demo/**（演示内容）
- [ ] **暂停其他文档优化，等待进一步指示**

我现在的理解对吗？
