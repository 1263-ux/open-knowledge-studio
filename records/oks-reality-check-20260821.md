# OKS 真实使用体验分析报告

**汇报时间**: 2026-08-21  
**分析对象**: OKS 实际部署与使用流程  
**触发**: 新 Agent 使用时暴露的问题

---

## 🔴 核心问题：我完全理解错了

### 我犯的最大错误

**我以为**：
- 用户需要手动 `pipx install`
- 用户需要阅读文档
- 用户需要学习命令

**实际上**：
- ✅ Agent 读取 `SKILL.md` 自动部署
- ✅ 用户只说一句话："帮我安装 OKS"
- ✅ Agent 自动完成所有步骤

**我优化的文档**（start-here.md, installation.md 等）**对 Agent 部署流程毫无帮助**。

---

## 📋 真实的 OKS 部署流程

### 上游设计的正确流程

```
用户: "帮我安装并开始使用 OKS。请先阅读并按照这个 Skill 操作：
      https://raw.githubusercontent.com/open-agent-power/open-knowledge-studio/main/SKILL.md"

↓

Agent 读取 SKILL.md
  1. 检查 Python ≥ 3.12
  2. 检查 pipx
  3. pipx install open-knowledge-studio
  4. oks init my-knowledge-base
  5. cd my-knowledge-base
  6. oks skills-install
  7. oks hook install --editor claude
  8. oks status
  9. oks recall "test query"

↓

完成！用户甚至不需要看文档
```

### SKILL.md 的设计哲学

```markdown
# Open Knowledge Studio Connect Skill

**Canonical URL**: https://raw.githubusercontent.com/.../SKILL.md
**Audience**: AI coding agents
**Purpose**: One URL. The agent reads this, installs OKS, and wires 
            the agent into a local knowledge base.

Three boundaries:

1. **One source of truth for install.**
2. **Agent does every safe step it can.**
3. **Verification is part of setup.**
```

**关键点**：
- ✅ SKILL.md 是 **machine-readable install contract**
- ✅ Agent 是执行者，不是文档阅读者
- ✅ 用户只需要一个 URL

---

## 🎯 新 Agent 遇到的问题暴露了什么

### 问题回顾

新 Agent 在使用 OKS 时：
1. 发现 `yt-dlp: unavailable`
2. 未报告就直接 `pip install yt-dlp`
3. 绕过了 `oks capability install watch`

### 这不是文档问题，是什么问题？

**根本原因**：
- ❌ **不是文档不够详细**
- ✅ **是 SKILL.md 没有覆盖 capability 管理**

看 SKILL.md 的内容：
```bash
1. oks init
2. oks skills-install
3. oks hook install
4. oks status
5. oks recall "test"
```

**缺失的步骤**：
```bash
6. oks capability status        # ❌ 没有这一步
7. oks capability install watch # ❌ 没有这一步
```

---

## 💡 我之前为什么测试那么顺利？

### 两个原因

#### 1. 我使用的是子 Agent（受控环境）

```python
Agent(
  description="测试 OKS",
  prompt="收录这个视频，测试完整流程"
)
```

- 子 Agent 在**我的控制下**
- 我明确告诉它"如果遇到能力缺失，报告给我"
- 它遵守了

#### 2. 我可能跳过了视频收录

回顾我的测试：
- ✅ 测试了 `oks recall`（文本召回）
- ✅ 测试了 Candidate 审核（文本内容）
- ⚠️ **可能没有真正测试视频收录**

如果我当时测试的是**文章收录**（不需要 yt-dlp），当然不会遇到 capability 缺失。

---

## 🔍 重新审视我们优化的文档

### 问题 1: 文档受众错了

**我优化的文档**（start-here.md, installation.md）：
- 受众：**人类用户**
- 假设：用户会阅读文档，手动执行命令
- 风格：对话式、教程式

**实际受众应该是**：
- 受众：**Agent**（通过 SKILL.md）
- 假设：Agent 自动执行，用户不看文档
- 风格：机器可读、清晰的成功/失败信号

### 问题 2: 我们优化的是"错误的入口"

**OKS 的两个入口**：

1. **Agent 部署入口**（主入口）
   - URL: `SKILL.md`
   - 受众: Agent
   - 用户行为：说一句话
   - 我们的优化：❌ **完全没碰这个**

2. **人类阅读入口**（次要）
   - URL: `docs/index.md`
   - 受众: 人类（开发者、研究者）
   - 用户行为：GitHub Pages 浏览
   - 我们的优化：✅ **花了大量时间在这**

### 问题 3: 我们的优化对 Agent 部署没有帮助

**Agent 部署时根本不看**：
- ❌ start-here.md
- ❌ installation.md
- ❌ first-knowledge-loop.md

**Agent 只看**：
- ✅ SKILL.md

---

## 📊 对比：上游 vs 我们的改进

### 上游的重点

**文件重要性排序**：
1. **SKILL.md** - 最重要（Agent 部署合同）
2. **README.md** - 重要（GitHub 首页）
3. **docs/** - 次要（深入理解）

**上游最近的改进**：
```
f073475 feat(skills): replace /start with /assess
2e3398a feat(cli): add oks skills-install command
44d42e8 feat(docs,cli): nowledge-inspired connect contract
```

关键词：**skills**, **cli**, **connect contract**（不是 docs 优化）

### 我们的改进重点

**文件改动**：
1. docs/start-here.md - 214 行
2. docs/first-knowledge-loop.md - 372 行
3. docs/best-practices.md - 166 行
4. docs/installation.md - 125 行
5. docs/verify.md - 202 行
6. docs/index.md - 121 行

**总计**：1,200+ 行文档优化

**问题**：
- ❌ 都是人类阅读的文档
- ❌ Agent 部署时根本不会看
- ❌ 没有触及核心问题

---

## 🎯 真正需要改进的地方

### 改进 1: SKILL.md 需要加 capability 检查

**当前 SKILL.md**：
```bash
oks skills-install
oks hook install
oks status  # ✅ 结束
```

**应该加入**：
```bash
oks skills-install
oks hook install
oks capability status           # ⚠️ 新增
# 检查 watch, local-asr 等能力
# 如果 unavailable，提示用户是否安装
oks status
```

### 改进 2: oks capability status 应该更智能

**当前行为**：
```
yt-dlp: unavailable
local-asr: unavailable
```

**应该改进为**：
```
⚠️ 检测到缺失能力：

1. watch (yt-dlp) - unavailable
   用途：下载视频和字幕
   安装：oks capability install watch
   
2. local-asr - unavailable
   用途：本地语音转文字（可选，可用远程API替代）
   安装：oks capability install local-asr

是否立即安装 watch？[Y/n]
```

### 改进 3: 首次使用向导

**在 oks init 后自动运行**：
```bash
oks init my-kb
# 自动触发
✓ 初始化完成
→ 正在检查能力...

发现常用能力未安装：
  - watch (视频收录)
  
是否安装？[Y/n]
```

---

## 🤔 我的深刻反思

### 1. 我完全误判了 OKS 的使用方式

**我以为**：
- 用户是"手动安装 OKS"的人
- 用户需要阅读文档学习
- 文档是主要入口

**实际上**：
- 用户是"对 Agent 说一句话"的人
- Agent 通过 SKILL.md 自动部署
- SKILL.md 是主要入口，文档是参考

### 2. 我优化了错误的东西

**我花了 5+ 小时优化**：
- start-here.md - Agent 不看
- installation.md - Agent 不看
- first-knowledge-loop.md - Agent 不看

**我应该优化的**：
- SKILL.md - Agent 部署合同
- oks capability 系统的用户体验
- 首次使用的自动化向导

### 3. 那个新 Agent 的问题不是"它做得差"

**问题根源**：
- ✅ SKILL.md 没告诉它检查 capability
- ✅ `oks capability status` 输出不够友好
- ✅ 没有自动提示安装缺失能力

**不是**：
- ❌ 文档不够详细
- ❌ Agent 不听话

---

## ✅ 正确的改进方向

### 立即行动（给上游提 PR）

1. **增强 SKILL.md**
   ```markdown
   ## Step 2.5: Check capabilities (for video/audio)
   
   ```bash
   oks capability status
   ```
   
   If `watch` is unavailable and user needs video ingestion:
   ```bash
   oks capability install watch
   ```
   ```

2. **改进 oks capability status 输出**
   - 友好的错误提示
   - 明确的安装命令
   - 用途说明

3. **首次使用向导**
   - oks init 后自动检查
   - 交互式安装建议

### 次要行动（文档维护）

我们优化的文档**不是没用**，但优先级很低：
- ✅ 对深入研究 OKS 的人有价值
- ✅ 对贡献者理解设计有帮助
- ❌ 对 Agent 自动部署没有帮助
- ❌ 对普通用户（"帮我装 OKS"）没有帮助

---

## 📝 给你的建议

### 关于文档优化

**当前状态**：
- ✅ 文档质量提升了（对人类阅读）
- ❌ 但没有解决核心问题（Agent 部署体验）

**建议**：
1. 保留我们的文档优化（对深入了解有价值）
2. 但**不要作为主推送内容**
3. 重点应该放在**改进 SKILL.md 和 capability 系统**

### 关于 PR 策略

**不推荐**：
- ❌ 推送我们的 1,200 行文档优化

**推荐**：
1. **PR #1**: 增强 SKILL.md（加 capability 检查）
2. **PR #2**: 改进 oks capability status 输出
3. **PR #3**: 首次使用向导
4. **PR #4**: （可选）部分文档优化作为补充

---

## 🎓 我学到的教训

1. **理解真实使用场景**
   - OKS 是 Agent-native，不是 human-manual
   - SKILL.md 是核心，不是 docs/

2. **找准优化目标**
   - 优化用户体验 ≠ 优化文档
   - 优化 Agent 部署体验 > 优化人类阅读体验

3. **测试要覆盖真实场景**
   - 我应该测试"新 Agent 从零开始部署"
   - 不是"我手动执行命令"

---

**总结**：我们花了大量时间优化文档，但优化错了重点。OKS 的核心使用方式是"Agent 自动部署"，我们应该优化 SKILL.md 和 capability 系统，而不是 docs/。

这是一个深刻的教训。
