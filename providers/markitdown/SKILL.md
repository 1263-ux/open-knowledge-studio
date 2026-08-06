# MarkItDown Provider

Office 文档→Markdown 转换。DOCX/PPTX/XLSX 已验证。

## 调用

```bash
python scripts/raw_bundle_adapter.py markitdown --source document.docx --output /tmp/bundle
```

## 输出

- 成功 → `status: complete`，evidence kind=text
- 复杂结构 → `status: partial`，需 firecrawl parse 或 agent-runtime 补充

## 降级

MarkItDown partial → firecrawl (document.text.extract) → agent-runtime (视觉)
