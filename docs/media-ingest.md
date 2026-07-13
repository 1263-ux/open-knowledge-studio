# 多模态录入：口播视频MVP

## 边界

第一版只处理本地口播视频，目标是生成可审查、可追溯的Raw Markdown候选。它不调用LLM，不总结内容，不写`drafts/`或`wiki/`。

为遵守“`raw/`由人类收集”的约束，流程分成两步：

```text
本地视频
  ↓ prepare
.oks/intake/<capture-id>/
  ├── candidate.md
  ├── quality-report.md
  ├── transcript.txt/json
  └── assets/*.jpg
  ↓ 人工查看并显式确认
raw/misc/<date>-<slug>.md
  ↓ 项目已有 /ingest
drafts/ → 人工 /promote → wiki/
```

`.oks/`已被Git忽略，未经审核的机器输出不会污染知识仓库。

## 安装

```powershell
python -m pip install -r scripts/media_ingest_requirements.txt
```

## 准备待审证据包

```powershell
python scripts/media_ingest.py prepare "D:\videos\oral.mp4" `
  --title "口播表达样本" `
  --source-url "https://example.com/video" `
  --source-author "作者名" `
  --save-reason "想学习口播表达" `
  --question "作者如何组织观点" `
  --relation "个人表达训练" `
  --tags 口播 表达
```

默认使用`faster-whisper small`、CPU int8，并每30秒抽取一张证据帧。结果只包含来源事实、人类采集注释、未经改写的ASR和视觉证据，不生成知识结论。

## 人工审核并写入Raw

先打开`.oks/intake/<capture-id>/candidate.md`和`quality-report.md`。确认后执行：

```powershell
python scripts/media_ingest.py approve <capture-id> `
  --confirm-human-review `
  --review-note "已核对来源和主要观点，允许进入Raw"
```

没有`--confirm-human-review`时命令会拒绝写入。相同视频哈希已经存在于`raw/`时也会拒绝重复录入。

## 当前限制

- 只支持口播型视频；
- 只做ASR，不做烧录字幕OCR；
- 不支持数学公式和IDE代码恢复；
- 不自动判断内容质量等级；
- 不自动调用`/ingest`；
- 来源片段默认标记为不完整。
