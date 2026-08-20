---
title: 第一个知识闭环
nav_order: 2
parent: 开始使用
---

# 第一个知识闭环

> 用自己的真实资料跑通完整流程：收录 → 审核 → 召回。

请选择一份你自己的真实资料。不要为了演示专门准备测试 PDF。

---

## 完整流程

```
资料 → Agent 收录 → Draft → 人工审核 → Wiki → 召回验证
```

**时间**：10-15 分钟

---

## 第 1 步：交给 Agent

在知识库目录中，把文件或 URL 交给兼容 Agent（如 Claude Code）：

```
收录这份资料。保留来源证据，生成 Candidate 后停下来让我审核。
```

**或者显式创建工作区**：

```bash
oks ingest prepare <文件或URL>
```

### 成功信号

- ✅ Agent 报告 Run Workspace
- ✅ Agent 报告 Raw Bundle 位置
- ✅ Agent 报告 Candidate 位置

### 可能的错误

**Agent 报错"找不到 Provider"**
- 检查资料类型是否支持
- 常见支持：文章、PDF、视频（配字幕）

**没有生成 Draft**
- 检查 Agent 是否完成执行
- 运行 `oks drafts list` 确认

---

## 第 2 步：审核 Candidate

### 查看 Draft 列表

```bash
oks drafts list
```

**预期输出**：

```
drafts/your-article-title.md  [concept]  2026-08-20
```

### 阅读 Draft 内容

```bash
# 用编辑器打开
code drafts/your-article-title.md

# 或用 cat 查看
cat drafts/your-article-title.md
```

### 审核标准

检查 3 个关键点：

1. ✅ **准确性**：核心信息是否正确
2. ✅ **可复用性**：未来能实际使用
3. ✅ **可追溯性**：能找回原始资料

### 做出决策

| 决策 | 命令 | 何时使用 |
|------|------|---------|
| **晋升** | `oks drafts promote <slug>` | 内容准确、可复用 |
| **编辑** | 手动修改文件后晋升 | 方向正确，需改写 |
| **拒绝** | `oks drafts reject <slug>` | 不值得长期保留 |

### 晋升示例

```bash
oks drafts promote your-article-title
```

**成功信号**：

```
✅ Promoted to wiki/your-article-title.md
```

---

## 第 3 步：召回验证

用你未来真的会问的问题召回：

```bash
oks recall "当时为什么这样决定？"
```

### 成功信号

结果中出现刚晋升的 Wiki 页面，并带路径和分数：

```
[1] Your Article Title (your-article-title)
    score=0.78, relevance=1.65
    
    [内容预览...]
```

### 调试技巧

**找不到 Wiki？**

```bash
# 1. 确认 Wiki 已创建
oks wiki list

# 2. 尝试不同措辞
oks recall "换个说法的问题"

# 3. 查看评分详情
oks recall "你的问题" --explain
```

---

## 完成标准

✅ **所有标准都满足才算完成**：

- [x] Raw 中保留了来源和证据
- [x] Candidate 经过你实际阅读
- [x] Wiki 页面带有 `human_reviewed_at`
- [x] `oks recall` 能用自然问题找回它

---

## 可视化流程

```
┌─────────────┐
│   资料      │ (文章/视频/PDF)
└──────┬──────┘
       │ Agent 收录
       ↓
┌─────────────┐
│ Raw Bundle  │ (保留原始证据)
└──────┬──────┘
       │ Agent 提取
       ↓
┌─────────────┐
│   Draft     │ (知识候选)
└──────┬──────┘
       │ 人工审核
       ↓
┌─────────────┐
│    Wiki     │ (可召回知识)
└──────┬──────┘
       │ oks recall
       ↓
┌─────────────┐
│  Agent 上下文│ (自动注入)
└─────────────┘
```

---

## 真实案例参考

完整演示：从 B 站 Kimi K3 视频到技术方案

**资料**：B 站视频（评测 Kimi K3）

**流程**：
1. yt-dlp 下载视频
2. ffmpeg 提取音频
3. faster-whisper 转写文字
4. Agent 生成 Draft
5. 人工审核晋升
6. 召回验证（score=0.84）
7. 基于知识做技术选型

**时间**：~7 分钟

👉 [查看完整演示（含截图）](../../examples/oh-my-research/demo/kimi-video-walkthrough.md)

---

## 故障排除

### 问题 1：Agent 无法收录资料

**检查**：
- Agent 是否支持该资料类型
- 文件路径是否正确
- 是否有网络连接（URL 资料）

**解决**：
- 查看 Agent 错误信息
- 尝试不同的资料格式
- 查看 [故障排除](../reference/troubleshooting.md)

### 问题 2：Draft 内容不准确

**原因**：AI 提取有误差

**解决**：
- 编辑 Draft 文件
- 修正错误内容
- 然后 promote

### 问题 3：召回找不到 Wiki

**检查清单**：
1. Wiki 是否已创建：`oks wiki list`
2. 尝试不同措辞
3. 检查 Wiki 内容是否包含关键词

**深入调试**：
```bash
oks recall "你的问题" --explain
```

---

## 下一步

完成第一个知识闭环后，选择你的路径：

| 你想要 | 下一步 |
|-------|--------|
| **系统学习** | [最佳实践](../best-practices.md) |
| **快速应用** | [常见工作流](../guides/workflows.md) |
| **深入理解** | [核心概念](../concepts/index.md) |

---

**核心原则**：第一次闭环是最重要的。用真实资料，完整走完流程，建立信心。
