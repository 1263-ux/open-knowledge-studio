# 可组合能力架构

## 目标

Open Knowledge Studio 的核心包只提供知识库初始化、配置、生命周期编排、审核和召回。获取、解析、模型和第三方平台能力均作为可选组件安装，避免新机器默认下载 PDF、ASR、OCR 或私有平台依赖。

```text
oks core
  ├─ oks ingest <source>           orchestration entry point
  ├─ oks capability install <name> explicit component selection
  ├─ oks-connector                 independent mechanical extraction CLI
  │    ├─ document                 Office / HTML / text
  │    ├─ pdf                      MinerU layout evidence
  │    ├─ watch                    video/audio captions, ASR, frames, OCR
  │    └─ formula                  formula OCR candidates
  └─ oks feishu                    optional private deployment component
       ├─ form / submit             human or CLI intake
       ├─ run-once                  Base capture to Raw/Candidate
       └─ listen                    bounded review-event consumption
```

## 安装原则

```powershell
pipx install open-knowledge-studio
oks init <knowledge-root>
oks capability install connector
oks capability install watch
```

默认 `oks capability install` 只展示对应的 `oks capability install` 命令。用户确认本机环境和模型体积后，使用 `--yes` 执行。核心包永远不自动安装模型、不会登录第三方平台、不会创建远端资源。

| Capability | 独立 CLI / Provider | 用户选择后安装 | 主要输入 |
|---|---|---|---|
| connector | `oks-connector` | `oks-connector` | URL 与本地文件路由 |
| watch | `oks-connector watch` | `oks-connector[watch]` | 视频、音频、平台 URL |
| document | `oks-connector markitdown` | `oks-connector[document]` | DOCX/PPTX/XLSX/HTML/文本 |
| pdf | `oks-connector mineru` | `oks-connector[pdf]` | PDF |
| formula | `formula_candidates.py` | `oks-connector[formula]` | 公式图片候选 |
| feishu | `oks feishu` + Worker | 用户批准的 `lark-cli` | 私有 Base、表单、消息审核 |

## 统一生命周期

无飞书时，用户将 URL 或文件传给 `oks ingest`；有飞书时，表单和 `oks feishu submit` 都进入同一 Worker 状态机。两条路径都必须保留：

```text
Capture → Processing Run → Raw Bundle → Candidate → human review → Wiki → wiki use
```

Connector 仅负责机械获取与证据。AI 可以生成 Candidate，但不能绕过人工审核提升到 Wiki。`partial`、`failed`、`skipped` 必须保留在 Run 和 Raw 中。

## 私有飞书边界

飞书能力不携带 App ID、App Secret、Base token、用户身份、权限或机器人配置。启用者按私有部署说明填写这些值、完成组织批准与扫码授权。CLI 只检查并调用已配置能力；缺失配置时返回明确诊断，不使用隐藏默认值或绕过认证。
