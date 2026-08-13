---
title: 备份与导出
nav_order: 8
---
# 备份与导出

## git（主机制）

OKS 实例用 git 跟踪记忆——`git push` / `git pull` 就是多设备同步 + 备份 + 版本。没有数据库，git 是迁移。

## OKF 导出

把 `wiki/` 导出成可移植的知识包，给其他工具读（Obsidian / Logseq / 任何 markdown reader）：

```bash
oks wiki export --format okf --output <dir>        # 开放标准，标准 markdown 链接
oks wiki export --format markdown --output <dir>  # Obsidian [[wikilink]]
```

- `okf` — 标准 markdown 链接 + OKF frontmatter（`type`, `concept-id`）
- `markdown` — Obsidian `[[wikilink]]` + 原始 frontmatter

A4 关系（`relates_to` + `relationship`）改写成正文链接。生成 per-type `index.md` + 顶层 `index.md` + `log.md`（OKF reserved files）。

这是快照，不是双向同步——外部工具的改动不会流回。
