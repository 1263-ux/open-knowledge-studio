---
title: 确认 OKS 正在工作
nav_order: 3
parent: 从这里开始
---

# 确认 OKS 正在工作

依次验证，不要用“页面看起来正常”代替真实结果。

## 1. CLI 与实例

```bash
oks --help
oks status
```

`oks status` 应该指向你创建的知识库实例，而不是 OKS 源码仓库。若路径不对，运行 `oks config show` 检查默认知识库。

## 2. 审核门存在

```bash
oks drafts list
oks wiki list
```

新收录内容应先出现在 Draft 列表。没有人工操作时，它不应该自动出现在 Wiki。

## 3. Recall 可解释

```bash
oks recall "<刚审核的主题>" --explain
```

检查命中页面、来源标签与相关性解释。命中 Raw 只能证明材料存在；只有带人工审核记录的 Wiki 才能作为已审核知识使用。

## 4. Hook（可选）

```bash
oks hook status
```

Hook 是显式安装的可选注入入口。没有安装 Hook 时，CLI Recall 仍然可用；不要把“没有自动注入”误判为整个 OKS 失败。

## 按失败层排查

| 现象 | 先检查 |
|---|---|
| 找不到 `oks` | [安装](installation.html)与 PATH |
| 收录没有 Raw | Provider 结果、Evidence Manifest 与 `result.json` 状态 |
| 没有 Candidate | `/ingest` 报告的缺失证据与降级状态 |
| Promote 失败 | `oks drafts get <slug>`、frontmatter 与目标路径 |
| Recall 无结果 | `oks wiki list`、查询词、scope 与 goal |
| Agent 没自动引用 | `oks hook status` 与宿主重启状态 |

仍无法定位时，使用[故障排除](reference/troubleshooting.html)，并保留原始错误输出，不要只记录“失败了”。
