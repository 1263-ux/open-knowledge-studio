# Local ASR Provider

本地语音识别（faster-whisper）。12 秒短音频已验证。

## 调用

通过 watch capability 调用：
```bash
python scripts/raw_bundle_adapter.py watch --source audio.mp3 --transcript-only
```

## 限制

首次使用需下载模型文件。长音频未在当前环境验证。
