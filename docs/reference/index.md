---
title: 参考
nav_order: 6
has_children: true
---

# 参考

参考页用于准确查命令、协议、参数和 schema，不承担产品叙事，也不含解释——"为什么这样设计"在[概念](../concepts/)里。

- [CLI](cli.html)：按命令组组织的完整命令树和关键契约。
- [参数表](parameters.html)：`recall.yaml` 全部参数、默认值与环境变量覆盖。
- [Schema 参考](schemas.html)：摄入协议五种对象（source-envelope / locator / evidence-fragment / manifest / raw-bundle）。
- [摄入协议](ingest.html)：摄入流程与 Raw Bundle 协议。
- [Mail 协议](mail-protocol.html)：Thread、Message、Receipt 与 Agent 间协作接口。

CLI 行为以当前安装版本的 `oks --help` 为准；Provider 可用性以 `oks capability status` 为准。
