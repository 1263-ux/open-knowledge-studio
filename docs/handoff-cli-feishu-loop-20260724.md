# CLI、Connector 与飞书审核闭环交接

日期：2026-07-24。状态：本地集成，未提交、未推送、未发布。

## 背景

Studio 已合入上游 v0.2.4（轻量 `pipx` 安装、路径安全、非破坏性升级和 Hook 修复）。Connector 仍是独立的 Level-1 机械采集工具：它获取、解析并写入 Raw 证据，不总结、不生成 Wiki 结论。Studio 负责 Capture、Processing Run、审核、Wiki promotion、recall 与显式 `oks wiki use`。

## 最短使用路径

```powershell
pipx install open-knowledge-studio
oks init <knowledge-root>
pipx inject open-knowledge-studio oks-connector
oks ingest <URL> --mode quick
oks ingest <URL> --mode forensic --timeout-seconds 900
```

`quick` 只走字幕/低成本文本证据；`forensic` 使用字幕主题时间点选取证据帧和 OCR。Connector 的视频、PDF、OCR 模型均为可选能力，不能加入 Studio 核心依赖。`oks ingest` 缺少 Connector 时会显示醒目的 `pipx inject` 命令；只有显式传入 `--install` 才会执行该本地环境变更。

按模态安装而不是一次安装全部：

```powershell
oks capability list
oks capability install connector
oks capability install watch       # video/audio/frames/OCR
oks capability install document    # Office/HTML/text
oks capability install pdf         # MinerU
oks capability install formula     # PaddleOCR
```

以上命令默认只显示实际 `pipx inject` 命令；加 `--yes` 才执行。这样新机器核心包保持轻量，只有用户选择的模态才下载模型或重依赖。

## 飞书扩展

飞书不是核心安装依赖。它复用 `scripts/feishu_base_worker.py` 的 Base 状态机与审核闭环：

```powershell
oks feishu auth
oks feishu form --url <Base-form-url>
$env:OKS_FEISHU_WORKER = '<studio-root>\\scripts\\feishu_base_worker.py'
$env:OKS_FEISHU_BASE_TOKEN = '<base-token>'
$env:OKS_FEISHU_TABLE_ID = '<table-id>'
oks feishu submit <URL-or-text> --thought <context>
oks feishu run-once
oks feishu listen --max-events 1 --timeout 5m
```

表单在用户已登录浏览器中填写；`auth` 只显示 `lark-cli` 身份状态；Worker 不会绕过登录、CAPTCHA、权限或平台限制。`listen` 是有界事件消费，连续监听应由用户选择的任务计划器或服务托管。缺失 Worker、lark-cli、Base 坐标或 Connector 时，命令必须失败并给出下一步，不得伪造完成状态。

## 产物边界

- Connector：来源获取后的机械 Raw、证据、质量和 `partial/failed/skipped` 状态。
- Studio：Capture Envelope、Processing Run、Raw Bundle v0.2、Candidate、人工审核、Wiki promotion、recall。
- AI：可生成 Candidate/Teach-back；不得跳过审核直接把 Raw 写为 Wiki。
- 用户：飞书登录、表单提交、授权、最终审核及任何外部发送/发布。

## 已知问题与下一步

1. 当前 `oks feishu` 是 Worker 门面；要让 PyPI wheel 完全自带飞书能力，需将已验证的 Worker 从 `scripts/` 提炼为 `knowledge_studio` 内的可选包，不能在未经测试的情况下复制 2000+ 行实现。
2. `oks ingest` 调用 Connector 并保留其结构化结果；将 v0.2 Capture/Run finalization 完全收敛到 Studio CLI 前，应先以真实 URL 与隔离知识库做一轮验收，避免复制 Worker 已有编排逻辑。
3. 真正飞书 E2E 需要用户已授权的 `lark-cli`、Base token、table id、Connector Python 与明确的外部操作授权。
4. Windows 原生 Hook 仍依赖 Bash/WSL；CLI 主链路可运行，但自动 recall Hook 需要 WSL 或 Git Bash。

## 回归检查

```powershell
cd <studio-root>\\cli
python -m pytest tests -q
oks ingest --help
oks feishu --help
```

完成后检查：无 Connector 时提示 `pipx inject`；`quick/forensic` 参数透传；飞书 Worker 缺失时显示 `OKS_FEISHU_WORKER`；不创建 `.oks/` 于只读命令；没有人工审核不晋升 Wiki。
