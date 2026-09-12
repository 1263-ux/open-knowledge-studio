---
title: 接入你的 Agent
nav_order: 4
parent: 指南
---

# 接入你的 Agent

OKS 的设计前提是：**`oks` CLI 是 Agent-native 的核心入口，宿主（Claude Code、Codex、Qoder、Pi……）只是适配器。** 安装后不需要你记住命令——把任务说给你正在使用的编码 Agent，由它调用 OKS 完成收集、审核辅助、召回和交付。

这一页回答一个问题：**怎样让我的 Agent 在每次任务里自动用上 OKS？**

## 一条命令接入（自动召回 hook）

```bash
oks hook install --editor claude    # 或 codex | qoder | both
```

这一步把**自动召回**接入你的宿主：

| 宿主 | 接入方式 | 说明 |
|---|---|---|
| Claude Code | `.claude/settings.json` + `.claude/hooks/` | `UserPromptSubmit` 触发召回，把已审核知识注入上下文 |
| Codex | `.codex/hooks.json` | 同上；原生 Windows 直接绑定 Python hook，不依赖 Bash/WSL |
| Qoder | `.qoder/settings.json` | 共享 `.claude/hooks/` |
| Pi | `.pi/extensions/*.ts` | TS extension 模板（[上游模板](https://github.com/open-agent-power/open-knowledge-studio/tree/main/.pi)） |

原理与排障：

- hook 每次收到你的 prompt 时调用 `oks recall`，把命中的已审核 Wiki/Raw 摘要注入上下文；没有命中就不注入（fails open，不会卡住你的提问）。
- `oks hook status` 检查接线是否完好、解释器是否能导入 `knowledge_studio`。升级 `oks` 后重新执行一次 `oks hook install` 即可刷新。
- Windows 原生运行时，`UserPromptSubmit`/`PostToolUse` 由 `_hook_runner.py` 兜底解析器路径；Codex 的 `PreToolUse`、`PreCompact` 等其余生命周期 hook 仍是 Bash 脚本，需要 Git Bash。

## 安装 Skills（教会 Agent 使用 OKS 的流程）

```bash
oks skills-install
```

把 Agent Skills 打包进宿主的技能目录：`.claude/`、`.codex/`、`.qoder/`、`.pi/`（Skill 源文件见仓库 [assets/skills](https://github.com/1263-ux/open-knowledge-studio/tree/main/assets/skills)）。安装后你的 Agent 直接获得这些能力（以 `/` 命令或自动触发方式）：

| Skill | 何时用 |
|---|---|
| `/ingest` | 把文章、文件、视频、对话变成可追溯来源 |
| `/query` | Triple-Layer 召回 → 注入 → 带引用回答 |
| `/promote` | 审核 Agent 提出的 Candidate（晋升/拒绝都必须由人决定） |
| `/compile` | 从来源重编译概念页 → drafts |
| `/lint` | 扫 wiki/ 一致性、孤儿页、断链 |
| `/status` | wiki 数量、tier 分布、质量概览 |
| `/archive` | 归档对话并沉淀 Q&A 为 drafts |
| `/assess` | 建立 profile 与活跃 Goal，验证召回加成 |

## Agent 间协作与任务交接

Agent 交接任务优先使用意图级命令 `oks mail delegate`，由 CLI 自动构造 handoff Thread：

```bash
oks mail delegate --to codex --task "检查登录模块" \
  --context "重点看 src/auth" \
  --acceptance "输出问题清单和修改建议" \
  --format json
```

普通用户不需要学习 `@agent-id`、`thread_id` 或 `ack`——这些是协议层的路由键，由 Host 或 Agent 在后台填充。跨 Session、跨机器继续同一段工作，靠的是 Mail 的持久 Thread 与 Session Receipt。协议细节见[参考 → Mail 协议](../reference/mail-protocol.html)。

## 验证接入成功

1. 重启宿主，问一句和已审核知识相关的话——召回应自动注入，Agent 回答能说出依据页。
2. 跑 `oks hook status`，全部显示 wired/importable。
3. 跑 `oks status`，确认实例有内容、tier 分布正常。

什么都没发生时，从[故障排除](troubleshooting.html)的"召回层"一节查起。
