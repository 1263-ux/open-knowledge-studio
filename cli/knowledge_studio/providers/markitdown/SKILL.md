# MarkItDown Provider

Office 文档→Markdown 转换。基础提取路径可用；复杂 DOCX/PPTX/XLSX 的结构、
公式、嵌入媒体和真实版式仍应按原文件复核。Word 与 XLSX 的真实样本验收尚未完成，
不得把提取结果宣传为完整 Office 保真。

## 调用

```bash
# Historical: raw_bundle_adapter.py was removed in v0.4.0.
# Use /ingest skill in Agent Host (Claude Code / Codex) or:
# oks raw-commit .oks/runs/{run_id}/manifest/
```

## 输出

- 文本提取成功 → `status: complete`，evidence kind=text；这不等于版式验收
- 复杂结构 → `status: partial`，需原文件复核或 agent-runtime 视觉补充

## 降级

MarkItDown partial → firecrawl (document.text.extract) → agent-runtime (视觉)
