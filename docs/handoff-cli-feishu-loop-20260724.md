# CLI、Connector 与飞书可选扩展交接

日期：2026-07-24。状态：已提交并推送到个人 GitHub Fork；尚未发布 PyPI 包、Release 或 Pages。

## 项目关系

这不是两个互相替代的项目，而是两个明确分层的仓库：

```text
open-knowledge-studio（Studio：核心 CLI、知识库编排、审核、Wiki）
  └─ oks ingest / oks feishu / oks capability
       └─ oks-connector（Connector：独立机械采集、模态路由、Raw 证据）
```

Studio 不重复实现视频、PDF、OCR 或来源抓取；它调用已安装的 Connector，并保留 Capture、Candidate、人工审核和 Wiki promotion 的边界。Connector 不生成结论、不绕过审核、也不直接写 Wiki。因此两仓库可独立使用，也可组合为完整 Loop。

项目的交付定位是“轻量、CLI 优先、可组合的个人知识处理系统”，而不是一个默认携带所有模型的万能解析器：核心 `oks` 能初始化和编排知识库；用户、Claude 或 GPT 根据输入类型显式安装提取能力；机械证据与 AI 解读、人工审核、Wiki 知识保持分离。详细组件关系见 [可组合能力架构](capability-architecture.md)，可执行的验证步骤见 [CLI 验收测试手册](acceptance-test-cli-20260724.md)。

已推送的测试分支：

- Studio：`1263-ux/open-knowledge-studio` 的 `codex/upstream-v0.2.3-integration`，提交 `38107f3`。
- Connector：`1263-ux/oks-connector` 的 `codex/raw-poc-validation`，提交 `9cad94c`。

## 新机器：从 GitHub 安装并验证 CLI

先安装 Python 3.12+ 与 `pipx`；Windows PowerShell 示例：

```powershell
py -m pip install --user pipx
py -m pipx ensurepath
# 重新打开 PowerShell 后执行：
pipx install "git+https://github.com/1263-ux/open-knowledge-studio.git@codex/upstream-v0.2.3-integration#subdirectory=cli"
pipx inject open-knowledge-studio "git+https://github.com/1263-ux/oks-connector.git@codex/raw-poc-validation"
oks --version
oks capability list
```

这两条 GitHub 安装命令获取的正是本次分支，不依赖尚未发布的 PyPI 版本。安装 Connector 后，在一个明确的新路径初始化知识库：

```powershell
oks init D:\knowledge-demo
oks ingest "https://www.youtube.com/watch?v=<video-id>" --mode quick
```

`quick` 是默认的轻量知识提取档位：优先平台字幕，不扫描全片。需要证据帧与 OCR 时才显式使用完整取证档：

```powershell
oks ingest "https://www.youtube.com/watch?v=<video-id>" --mode forensic --timeout-seconds 900
```

两档都会在 stderr 输出阶段进度；超时返回可机读的 `partial` 结果，绝不伪造成功。采集只写 Raw 证据；Candidate、人工审核和 Wiki promotion 仍由 Studio 流程处理。

## 按需添加模态能力

核心安装不会下载重型模型。先运行 `oks capability list`；下列命令默认只显示将要执行的安装操作，确认后加 `--yes`：

```powershell
oks capability install watch       # 视频/音频字幕、ASR、证据帧、OCR
oks capability install document    # Office、HTML、文本
oks capability install pdf         # MinerU PDF
oks capability install formula     # 公式 OCR
```

对于本次 GitHub 验证，若需在同一分支上安装某一 Connector extra，使用本地 clone 最稳妥：

```powershell
git clone --branch codex/raw-poc-validation https://github.com/1263-ux/oks-connector.git
pipx inject open-knowledge-studio ".\oks-connector[watch]"
```

将 `watch` 改成 `document`、`pdf` 或 `formula` 即可。`oks ingest <source> --install` 也只会在用户明确传入该参数后执行一次对应的 `pipx inject`。

## 飞书：可选私有部署组件

飞书核心链路已接入 Studio CLI，但它不是默认核心依赖，也没有捆绑任何租户密钥、机器人身份、权限或扫码登录：

```text
oks feishu auth       显示用户管理的 lark-cli 登录状态
oks feishu form       展示用户的 Base 表单入口
oks feishu submit     从 CLI 写入待处理的采集项
oks feishu run-once   运行一次 Base -> Raw/审核状态机
oks feishu listen     有界监听审核回复/事件
```

私有部署前，用户或其 Agent 必须自行安装并授权组织批准的 `lark-cli`，配置自己的 Worker 和 Base 坐标，并在飞书后台为机器人申请与实际功能相符的权限。OKS 不代填 App ID/Secret，不越过扫码、CAPTCHA 或管理员审批，也不会自动创建远端资源。

```powershell
# 用户已完成 lark-cli 登录与组织授权后：
oks feishu auth
oks feishu form --url "<your-feishu-base-form-url>"
$env:OKS_FEISHU_BASE_TOKEN = "<your-base-token>"
$env:OKS_FEISHU_TABLE_ID = "<your-table-id>"
oks feishu submit "https://example.com/article" --thought "capture context"
oks feishu run-once
oks feishu listen --max-events 1 --timeout 5m
```

安装后的 Studio wheel 会携带受审查的 `feishu_base_worker.py`；若需要替换为组织版本，才设置 `OKS_FEISHU_WORKER` 指向该脚本。表单入口与 CLI 提交都进入同一审核状态机；不用飞书时，直接 `oks ingest` 也能完成 Raw 采集链路。

## 能力边界与已验证项

- Studio 负责：配置与路径安全、CLI 门面、知识库生命周期、Capture/Run 编排、Candidate、人工审核、Wiki promotion、召回与 `wiki use`。
- Connector 负责：来源抓取后的机械解析、模态路由、进度、超时和 Raw 证据包；不会总结、批准或发布知识。
- 可选能力负责：按需安装的视频/音频、PDF、Office/HTML、公式 OCR 与飞书私有集成。它们不属于核心包的默认安装内容。
- 用户/组织负责：选择能力、安装重依赖、提供第三方登录与密钥、申请实际所需权限、确认外部写入和最终审核。
- 已验证：Studio CLI 测试 39 项通过；Connector 脚本测试 42 项通过；打包结果包含飞书 Worker，不包含无关 Connector 脚本。
- 已修复：`pipx inject` 的 Connector 脚本不在全局 PATH 时，`oks ingest` 会从运行 `oks` 的同一 pipx 虚拟环境发现它；视频、PDF、文档和公式能力共用此修复。
- 已验证：Connector 对真实 YouTube 资源的快速路径在温热 Watch 缓存中 2.18 秒完成，使用 809 条字幕、0 帧、0 OCR；该时间不是冷网络基准。
- 未做：此分支没有发布到 PyPI、创建 Release、部署 Pages，未进行真实飞书租户的写入或机器人授权。
- 外部网站若要求登录、动态渲染或触发反爬，仍需要浏览器/人工快照采集；这会诚实返回 `partial`、`failed` 或 `skipped`。
- Windows 原生自动 recall Hook 仍依赖 Bash/WSL；CLI 主链路不依赖它。

## 验收清单

```powershell
oks --version
oks capability list
oks ingest --help
oks feishu --help
oks init D:\knowledge-demo
oks ingest "<URL>" --mode quick
```

验收时确认：缺 Connector 时 CLI 会显示安装命令；视频默认走 `quick`；只有 `forensic` 才请求证据帧/OCR；没有人工审核不会 promotion 为 Wiki；飞书未配置时给出缺少配置的明确错误，而不是声称已完成。
