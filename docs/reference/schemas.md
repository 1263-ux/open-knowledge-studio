---
title: Schema 参考
nav_order: 4
parent: 参考
---

# Schema 参考

Agent 向 `oks raw-commit` 提交证据前必须按协议形状书写文档。本页镜像 `oks schema show` 支持的五种协议对象——**摄入协议的对象模型**。查看权威示例：

```bash
oks schema show raw-bundle     # 支持: evidence-fragment | evidence-manifest | locator | raw-bundle | source-envelope
```

对象关系图：

```text
Source (文章/文件/视频/网页)
  └─ source-envelope      来源封装：出处、采集时间、采集方式
       └─ locator          定位符：来源内的一次具体定位（URL/路径/时间戳）
            └─ evidence-fragment    证据片段：机械提取的最小知识单元
                 └─ evidence-manifest   清单：一次采集产生的全部片段 + 校验
                      └─ raw-bundle      Raw Bundle v0.2：raw-commit 的提交单元
```

## source-envelope

来源封装。回答"这份材料从哪里来"：原始出处、采集时间、采集工具与方式。它是 A/B/C 来源分级和指纹去重的载体。

## locator

一次具体定位。同一个来源可以产出多个 locator（一个网页的多个段落、一个视频的多个时间段）。机械提取只转换格式，不改变知识——fragment 必须能通过 locator 回溯到原文。

## evidence-fragment

最小证据单元。由 Provider 机械提取产生，保留最大保真度；`partial`、`failed`、`skipped` 状态必须原样保留，不得由 AI 改写或补全。

## evidence-manifest

一次采集的清单：声明的全部 fragment、完整性校验和指纹。Agent 只能基于 manifest 提出 Candidate——能不能成为 Wiki 仍由人审（[审核候选](../usage/review.html)）。

## raw-bundle

`oks raw-commit` 的提交单元，v0.2 形状。manifest 校验通过后落盘到 `raw/{YYYY}/{MM}/{DD}/{source}/`，成为可召回的 episodic 材料。

## 边界

- Schema 层只约束"形状"，不判断"内容对错"——事实校准由人审完成。
- `oks schema show <name>` 的输出是可执行的校验示例，与本页冲突时以它为准。
