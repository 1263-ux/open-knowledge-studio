# RapidOCR Provider

轻量 OCR。46 blocks/5.5s 已验证。

## 最佳组合

RapidOCR (mechanical, bbox) + Agent Vision (agent_observed, 页面语义) = 混合最优。

## 调用

```bash
python scripts/raw_bundle_adapter.py image --source screenshot.png --output /tmp/bundle
```
