# PDF Lite Provider

轻量 PDF 文本层提取。33 页 / 82K 字符 / 6.3s / 成本 0 已验证。

## 调用方式

```bash
# 通过脚本直接调用
python -c "
from capture_adapters.pdf_lite import PdfLiteAdapter
from capture_contract import CaptureRequest
adapter = PdfLiteAdapter()
result = adapter.capture(CaptureRequest('document.pdf'))
# 逐页 evidence: {kind: text, method: pdf_text_layer, locator: {kind: page, page: N}}
"
```

## 输出

- 有文本层 → `status: complete`，evidence 每条对应一页
- 无文本层（扫描件）→ `status: partial`，`failure_disposition: needs_user_action`

## 降级

扫描 PDF → rapidocr (OCR) 或 agent-runtime (视觉) 或 firecrawl (远程 OCR)。
