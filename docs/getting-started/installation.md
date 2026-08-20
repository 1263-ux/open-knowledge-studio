---
title: 安装
nav_order: 1
parent: 开始使用
---

# 安装

> 用唯一推荐的方式安装 OKS：pipx。

---

## 快速安装

```bash
# 安装 OKS
pipx install open-knowledge-studio

# 确保路径配置
pipx ensurepath

# 验证安装
oks --version
```

**预期输出**：

```
oks version 0.6.x
```

---

## 为什么用 pipx

pipx 避免 PEP 668 `externally-managed-environment` 错误：
- ✅ Ubuntu 24.04+
- ✅ macOS Homebrew Python
- ✅ 其他现代 Python 环境

**优势**：
- 独立环境，不污染系统 Python
- 自动处理依赖冲突
- 安装后全局可用

---

## 安装 pipx

### Ubuntu / Debian

```bash
sudo apt install pipx
```

### macOS

```bash
brew install pipx
```

### Windows

```bash
py -m pip install --user pipx
py -m pipx ensurepath
```

重启终端后生效。

---

## 初始化知识库

```bash
# 创建新知识库
oks init my-knowledge-base

# 进入目录
cd my-knowledge-base

# 检查状态
oks status
```

**预期输出**：

```
✅ OKS initialized
Wiki pages: 0
Drafts: 0
Raw bundles: 0
```

---

## 开发者安装（从源码）

如果你要贡献代码或使用最新开发版本：

```bash
# 克隆仓库
git clone https://github.com/open-agent-power/open-knowledge-studio.git
cd open-knowledge-studio

# 安装本地版本
pipx install ./cli --force
```

---

## 验证安装

运行完整验证：

```bash
# 查看版本
oks --version

# 查看帮助
oks --help

# 初始化测试库
oks init test-kb
cd test-kb

# 查看状态
oks status
```

如果所有命令都正常执行，安装成功。

---

## 下一步

安装完成后，选择你的路径：

| 你想要 | 下一步 |
|-------|--------|
| **快速体验** | [5 分钟见效](quick-wins.md) |
| **系统学习** | [第一个知识闭环](../first-knowledge-loop.md) |
| **遇到问题** | [故障排除](../reference/troubleshooting.md) |

---

## 常见问题

### Q: 安装后找不到 oks 命令？

**原因**：PATH 配置未生效

**解决**：

```bash
# 重新配置 PATH
pipx ensurepath

# 重启终端
# 或手动加载配置
source ~/.bashrc  # Linux
source ~/.zshrc   # macOS
```

### Q: pipx install 报错？

**常见原因**：Python 版本过低

**要求**：Python 3.8+

**检查版本**：

```bash
python3 --version
```

**升级 Python**：
- Ubuntu: `sudo apt install python3.10`
- macOS: `brew install python@3.10`
- Windows: 下载最新 Python 安装包

### Q: Windows 上安装失败？

**解决方案**：

1. 确认 Python 已安装
2. 使用 `py` 而不是 `python`
3. 确保管理员权限

```bash
# Windows 专用命令
py -m pip install --user pipx
py -m pipx ensurepath
py -m pipx install open-knowledge-studio
```

---

**核心原则**：用 pipx 安装，避免环境污染。一次安装，全局可用。
