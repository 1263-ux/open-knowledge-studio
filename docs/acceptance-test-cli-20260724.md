# CLI 组合能力验收测试手册

日期：2026-07-24（更新 2026-07-25）。适用分支：`codex/upstream-v0.2.3-integration`。

> **2026-07-25 更新**：`oks-connector` 已合并入 `open-knowledge-studio` 单仓库。不再需要 `pipx inject`。

本手册的目标是让一台新机器验证本次交付，而不是要求预先配置飞书或下载所有模态模型。每一步都给出应达到的效果；任一步失败时，请保留终端输出、`--progress` 的 stderr 日志，以及生成的 Raw 路径。

## 0. 前置条件

- Windows：Python 3.12+、Git、可访问 GitHub；macOS/Linux 将 `py` 换为 `python3`。
- 只测试 CLI 主链路时，不需要飞书账号、Base、机器人或模型 API Key。
- 测试目录必须是明确的新目录；`oks init` 不会默默初始化当前目录。

## 1. 从 GitHub 安装指定交付版本

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
# 关闭并重新打开 PowerShell 后：

# 基础安装（不含重型依赖，仅核心命令）
pipx install “git+https://github.com/1263-ux/open-knowledge-studio.git@codex/upstream-v0.2.3-integration#subdirectory=cli”

# 或带 watch 能力（视频/音频提取）
pipx install “git+https://github.com/1263-ux/open-knowledge-studio.git@codex/upstream-v0.2.3-integration#subdirectory=cli[watch]”

oks --version
oks capability list
```

验收效果：`oks --version` 成功；`capability list` 列出 `watch`、`document`、`pdf`、`formula`、`feishu`（`connector` 已内置，不再单独列出）。注意：`pipx install` 的 `[watch]` extras 语法可能需要 `--pip-args` 或分两步；如遇到问题，先执行基础安装，再用 `oks capability install watch --yes`。

## 2. 初始化与只读 CLI 安全性

```powershell
oks init D:\oks-acceptance
oks ingest --help
oks feishu --help
```

验收效果：`D:\oks-acceptance` 被初始化为知识库；两条 `--help` 命令正常显示帮助，不应因为读取帮助而创建新的 `.oks` 目录。对非空且不是知识库的目录执行 `oks init <path>` 时，应拒绝而非写入。

## 3. URL 快速知识提取（无需飞书）

选择一个公开、可访问且具有字幕的 YouTube 视频：

```powershell
oks ingest "https://www.youtube.com/watch?v=<video-id>" --mode quick --progress
```

验收效果：

- stdout 给出 Connector 的结构化最终结果或 Raw 路径；stderr 有阶段进度 JSONL。
- 视频优先使用平台字幕；默认不扫描整段视频，不产生证据帧/OCR 工作。
- 成功、字幕缺失、反爬、网络失败或超时都必须是可区分的状态；不允许把不完整结果报告为成功。
- 此步只产生 Raw 采集证据，不会自动生成 Wiki 条目。

## 4. 完整多模态取证档位

```powershell
oks ingest "https://www.youtube.com/watch?v=<video-id>" --mode forensic --timeout-seconds 900 --progress
```

验收效果：当字幕可用时，取证帧由字幕主题起点、语音停顿和最长 45 秒间距选择，而不是默认扫描整段视频；只有这些锚点帧才进行 OCR。若字幕不可用，结果必须明确记录回退到旧全视频路径或受限失败/部分完成。达到 900 秒期限时，输出应为可机读 `partial` 超时状态。

## 5. 按需安装一个重型模态组件

先查看将要执行的命令：

```powershell
oks capability install watch
```

验收效果：只显示安装建议，不修改本机环境。确认下载体积和依赖后才执行：

```powershell
oks capability install watch --yes
```

验收效果：仅安装视频/音频相关 extra。对于本次 GitHub 分支验证，若需严格固定 Connector 分支，改用：

```powershell
git clone --branch codex/raw-poc-validation https://github.com/1263-ux/oks-connector.git
pipx inject open-knowledge-studio ".\oks-connector[watch]"
```

随后重复第 4 步；验收重点是提取器按需要安装，而核心 `oks` 安装不携带它们。

## 6. PDF 与文档路由（可选）

```powershell
oks capability install pdf
oks capability install document
```

验收效果：默认仅展示安装建议。确认后以 `--yes` 安装对应能力，再执行：

```powershell
oks ingest "D:\fixtures\sample.pdf" --mode quick
oks ingest "D:\fixtures\sample.docx" --mode quick
```

验收效果：CLI 为 PDF 推荐 `pdf` 能力，为 Office/HTML/文本推荐 `document` 能力；未安装时给出准确的 `pipx inject` 下一步，而不静默安装或产生虚假成功。

## 7. 飞书私有扩展（需要用户租户授权）

本节不是主链路的前置条件。只有部署者已通过组织审批、配置自己的 `lark-cli`、Base 与机器人权限时才执行。

```powershell
oks feishu auth
oks feishu form --url "<your-feishu-base-form-url>"
$env:OKS_FEISHU_BASE_TOKEN = "<your-base-token>"
$env:OKS_FEISHU_TABLE_ID = "<your-table-id>"
oks feishu submit "https://example.com/article" --thought "acceptance capture"
oks feishu run-once
oks feishu listen --max-events 1 --timeout 5m
```

验收效果：

- `auth` 只显示用户管理的 `lark-cli` 身份状态，不发起隐式登录。
- `form` 明显显示用户自己的表单链接；提交仍在认证浏览器会话中完成。
- `submit` 与表单数据进入同一 Base/审核状态机；`run-once` 处理有限批次；`listen` 有明确事件数和超时上限。
- 未安装 `lark-cli`、未填 Base 坐标或权限不足时，CLI 必须给出明确诊断，不能绕过扫码、CAPTCHA、管理员审批或创建隐藏远端资源。
- 真实写入前必须由拥有租户权限的部署者确认；本交付未执行真实租户 E2E。

## 8. 交付通过标准

本次验收通过，至少应同时满足：

1. 可从两个 GitHub 分支用 `pipx` 安装 `oks` 与 Connector，且 `oks --version`、`oks capability list` 可用。
2. `pipx inject` 后，`oks ingest` 自己能发现同一 pipx 环境内的 `oks-connector`；不要求 Connector 额外存在于系统 PATH。
3. 未安装重型 extra 的情况下，公开 URL 的 `quick` 路径能给出真实的 Raw 结果或真实的受限状态。
4. `forensic` 是显式档位，字幕存在时使用主题锚点，而非默认全片扫描；进度、预计期限和超时结果可观察。
5. 视频、PDF、Office/HTML、公式、飞书均能被清楚识别为独立可安装组件；核心包不偷偷安装它们。
6. 无飞书时 CLI 主链路仍可运行；有飞书时仅在用户完成私有配置和授权后接入同一审核闭环。
7. 任一采集都不会绕过人工审核直接提升为 Wiki；`partial`、`failed`、`skipped` 状态保持可追踪。

## 当前已知限制

- 真实飞书租户写入、扫码授权和机器人后台权限未在本交付中执行；需要部署者自己的租户和明确授权。
- 动态、需登录或反爬网页仍可能要求浏览器/人工快照；系统应报告受限状态。
- Windows 原生自动 recall Hook 仍需要 Bash/WSL；不影响上述 CLI 采集测试。
