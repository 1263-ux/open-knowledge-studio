---
title: 安装
nav_order: 1
parent: 从这里开始
---

# 安装 OKS

OKS 需要 Python 3.12 或更高版本。推荐用 pipx 隔离安装 CLI。

## 安装并创建实例

```bash
pipx install open-knowledge-studio
pipx ensurepath
oks init ./my-knowledge
cd ./my-knowledge
oks status
```

重新打开终端后，`oks --help` 应显示当前命令树，`oks status` 应指向刚创建的实例。

个人知识应该保存在独立实例中，不要长期写进 OKS 源码仓库。

## 团队实例

```bash
oks team init ./team-knowledge-studio --name "Platform Knowledge Team"
cd ./team-knowledge-studio
oks status
```

初始化只创建结构和模板。请人工审阅 `profiles/team.md` 与 `profiles/goals/team.md`，再把它们当作团队事实使用。

## 安装 pipx

macOS：

```bash
brew install pipx
pipx ensurepath
```

Ubuntu：

```bash
sudo apt install pipx
pipx ensurepath
```

Windows：

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
```

若终端仍找不到 `pipx` 或 `oks`，先重新打开终端，再检查 PATH 和 Python 版本。

## 从源码开发

```bash
pipx install ./cli --force
oks --help
```

这条路径用于维护者验证当前 checkout，不是普通用户的默认安装方式。

## 下一步

- [完成第一次学习循环](first-knowledge-loop.html)
- [确认 OKS 正在工作](verify.html)
