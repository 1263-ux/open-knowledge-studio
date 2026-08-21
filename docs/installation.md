---
title: 安装
nav_order: 1
parent: 从这里开始
---

# 安装 OKS

> 一个命令，2 分钟完成

---

## 推荐方式：pipx

```bash
# 1. 安装 OKS
pipx install open-knowledge-studio

# 2. 初始化知识库
oks init ./my-knowledge

# 3. 进入目录
cd ./my-knowledge

# 4. 验证
oks status
```

✅ **成功信号**：看到状态面板，显示 Wiki / Drafts 数量

---

## 系统要求

| 项目 | 要求 |
|------|------|
| **Python** | 3.12+ |
| **pipx** | 推荐 |
| **磁盘** | 至少 100 MB |
| **Agent** | Claude Code / Codex / Cursor |

---

## 第一次装 pipx？

**macOS**:
```bash
brew install pipx && pipx ensurepath
```

**Ubuntu**:
```bash
sudo apt install pipx && pipx ensurepath
```

**Windows**:
```bash
py -m pip install --user pipx && py -m pipx ensurepath
```

安装后**重启终端**，再运行 `oks --version`。

---

## 验证安装

### 通过 Agent（推荐）

打开 Claude Code / Codex，说：

```
"检查 OKS 是否正常工作"
```

Agent 会自动检查所有组件。

---

### 手动验证

```bash
oks --version  # 返回版本号
oks status     # 显示知识库状态
```

---

## 常见问题

### Q: pipx: command not found

**重启终端**后再试。如果还是不行：

```bash
# 手动添加到 PATH
export PATH="$HOME/.local/bin:$PATH"
```

---

### Q: Permission denied

不要用 `sudo`，改用用户目录：

```bash
oks init ~/my-knowledge
```

---

### Q: Python 版本太低

需要 Python 3.10+：

```bash
python --version  # 检查版本
```

---

## 下一步

✅ **安装完成**：[第一个知识闭环](first-knowledge-loop.md)

⚠️ **遇到问题**：[确认 OKS 正在工作](verify.md)
