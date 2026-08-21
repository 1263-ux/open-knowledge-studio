# Screenshots for oh-my-kimi Demo

这个目录存放 `oh-my-kimi` 案例的演示截图。

## 截图清单

按演示流程顺序：

### 入库前（Before）
- `01-before-ingest.png` - 入库前的 OKS 状态（空知识库或无 Kimi 相关内容）
- `01-before-query.png` - 入库前询问 Kimi 相关问题的回答（无召回）

### 入库过程（Ingestion）
- `02-start-ingest.png` - 开始入库命令/对话
- `03-ingest-processing.png` - 入库进行中的日志/进度
- `03-raw-bundle.png` - 生成的 Raw Bundle 文件结构

### 审核阶段（Review）
- `04-review-draft.png` - 查看 Draft 命令
- `05-draft-list.png` - Draft 列表展示
- `05-draft-content.png` - Draft 具体内容展示

### 晋升到 Wiki（Promotion）
- `06-promote.png` - 晋升命令
- `07-promote-success.png` - 晋升成功确认
- `07-wiki-file.png` - 晋升后的 Wiki 文件

### 召回与应用（Recall & Application）
- `08-recall.png` - 召回命令和结果
- `09-recall-result.png` - 召回到的知识条目详情
- `10-technical-design.png` - 基于召回知识设计的技术方案

### 对比效果（Comparison）
- `11-comparison.png` - Before/After 对比图（并排或上下）
- `11-comparison-table.png` - 对比表格（有 OKS vs 无 OKS）

## 截图规范

为了保持演示的专业性和一致性：

### 技术要求
- **分辨率**：至少 1920x1080
- **格式**：PNG（保证文字清晰）
- **文件大小**：单张不超过 2MB（用 pngquant 压缩）

### 内容要求
- **隐私保护**：遮挡个人信息（用户名、路径、IP）
- **聚焦重点**：裁剪掉无关的界面元素
- **标注清晰**：用红框/箭头标注关键信息
- **终端主题**：使用统一的终端配色（建议 Dracula 或 One Dark）

### 命名规范
- 按流程顺序编号：`01-`, `02-`, `03-` ...
- 描述性文件名：`before-ingest`, `draft-content`, `recall-result`
- 同一步骤的多张图：`05-draft-list.png`, `05-draft-content.png`

## 生成截图的步骤

### 1. 准备环境
```bash
# 清理终端历史
clear

# 设置统一的终端宽度
# 建议：120 列 x 30 行

# 启动截图工具（Windows: Snipping Tool, macOS: Shift+Cmd+4）
```

### 2. 执行演示流程

按 `README.md` 中的步骤执行，每一步截图：
- 命令输入 + 输出结果
- 关键文件内容
- Agent 对话过程

### 3. 后期处理

```bash
# 压缩 PNG（可选）
pngquant --quality=80-95 *.png

# 添加标注（推荐工具）
# - Windows: Snagit, ShareX
# - macOS: Skitch, CleanShot X
# - Linux: Flameshot
```

### 4. 验证清单

- [ ] 所有截图都清晰可读
- [ ] 没有暴露敏感信息
- [ ] 文件名符合规范
- [ ] 文件大小合理（< 2MB）
- [ ] 在 README.md 中引用正确

## 示例：标注风格

推荐的标注元素：

1. **红色矩形框**：标注关键命令或输出
2. **黄色高亮**：标注重要文本
3. **箭头 + 文字**：解释关键步骤
4. **序号标记**：多步骤流程

示例（伪代码）：
```
┌─────────────────────────────────────┐
│ $ oks ingest run video.mp4          │ ← ① 入库命令
│                                     │
│ ✓ Extracted transcript              │ ← ② 提取字幕
│ ✓ Created raw bundle                │ ← ③ 生成 Bundle
│ ✓ Generated draft: kimi-ki3-intro  │ ← ④ 生成 Draft
└─────────────────────────────────────┘
```

## 占位符

在截图未生成前，可以使用占位符：

```markdown
![入库前状态](assets/screenshots/01-before-ingest.png)
<!-- 占位符：将展示空白的 wiki/ 目录或 oks status 输出 -->
```

## 相关资源

- [GitHub 中图片的最佳实践](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#images)
- [如何制作高质量的技术演示](https://www.screentogif.com/)
