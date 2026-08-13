---
title: 收录资料
nav_order: 2
parent: 参考
has_children: true
---

# 收录资料

Agent-native 摄入链路：Agent 收集证据并自己写 Manifest，CLI 只做机械校验。

- 操作手册讲**怎么跑一遍**。
- 协议对象关系讲**每个 JSON 对象之间怎么衔接**。

## 多模态记忆

OKS 的 `raw/` 支持多模态——`image.ocr` / `speech.transcribe` / `video` 等能力把非文本转成文字 excerpt + 保留原始文件。存储走“原始多模态 + 文本描述索引”思路：

- **原始文件**：图片 / 音频 / 视频存 `raw/{date}/{source}/`，frontmatter 记 `mime_type` + 原始路径
- **文本索引**：OCR / 转写结果写 frontmatter `excerpt` 或同名 `.txt`，参与召回（token overlap + 子串）
- **召回命中**：返回 excerpt 文本 + 指向原始文件路径，Agent 需要时按需读原始多模态

这是多模态记忆三思路里最轻的一条——不做“嵌入压缩到上下文”（要 embedding 模型）或“写入模型参数”（要 Engram 预训练模型）。OKS 用文件 + 文本索引，零模型依赖，契合 P4。
