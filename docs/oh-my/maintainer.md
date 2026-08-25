---
title: Oh My Maintainer
nav_order: 2
parent: Oh My
---

# Oh My Maintainer：让维护经验回到下一次修改

{: .note }
> **类型：经验案例。** 本页说明一次已经发生过的文档—实现一致性修复；命令和 Skill 数量仍应以当前 `oks --help` 与包内容为准。

一次维护中，安装契约要求 Agent 运行 `oks skills-install`，但当时的 CLI 并不存在该命令。问题不是普通错别字：Skill 是 Agent 会执行的契约，文档与实现不一致会让安装流程在真实环境中中断。

## 学习循环

1. **Observe**：真实命令返回 `No such command 'skills-install'`。
2. **Trace**：检查 `oks --help`、CLI 实现和打包边界。
3. **Candidate**：提出“删除文档承诺”或“增加独立命令”两个方案。
4. **Human Review**：判断 `init --upgrade` 影响过宽，批准轻量独立命令。
5. **Implement**：增加只安装 Skill 的命令，并修正文档中的分发边界。
6. **Recall**：把“文档是 Agent 可执行契约”沉淀为后续维护规则。

## 人类不可委托的判断

- 新命令是否真的有独立语义；
- 是实现错了，还是文档承诺过度；
- maintainer-only 工具是否应该进入用户安装包；
- 修复是否值得扩大公开 API。

## 可复用检查

```bash
oks --help
oks skills-install --help
python -m pytest -q
```

维护工作的产物不只是一个修复。失败证据、取舍和验收结果进入知识循环后，下一位 Agent 才能避免重新踩同一个坑。
