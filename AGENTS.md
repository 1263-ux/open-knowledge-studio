# Open Knowledge Studio

> 面向 Agent 的文件式知识工程工作区：`Source -> Raw -> Candidate -> Human Review -> Wiki -> Search / Recall -> Agent Output`。

## 这是什么

Open Knowledge Studio 是给 Codex / Claude Code / 兼容 Agent 使用的知识工程工作区。它提供：

- **4 个认知桶 + 2 个基础设施层**：`profiles/`、`raw/`、`wiki/`、`drafts/`；以及 `settings/`、`_meta/`。
- **6+1 因子召回引擎**：token overlap、substring、topic trace、type boost、review bonus、memory curve，以及可选 goal boost。
- **Dreaming 循环**：Raw 由 Agent 提炼成 Candidate，经人类审核后晋升 Wiki。
- **可选组件化提取器**：`document`、`pdf`、`formula`、`watch` 按需安装。
- **CLI 工具 `oks`**：init、ingest、drafts、wiki、search、recall、lint、status、capability、feishu。
- **Agent Skills**：`.claude/skills/` 与 `.agents/skills/` 下的 start、ingest、query、lint、compile、status、archive、promote、media-ingest。

## Raw 与 Wiki 的核心区别

| | Raw Material (`raw/`) | Memory (`wiki/`) |
|---|---|---|
| 是什么 | 原始文章、论文、笔记、对话、采集证据 | 经提炼和人工批准的持久知识 |
| 谁写入 | 人或机械采集器写入；Agent 只读和引用 | Agent 可写 Candidate；人类批准后晋升 |
| 是否衰减 | 不衰减 | 按类型和记忆曲线参与召回 |
| 用途 | 保存来源、证据、失败状态 | 支持 search/recall 和 Agent 输出 |

绝不能把 Raw 直接当 Wiki，也不能绕过人工审核自动晋升。

## 快速开始

从当前源码仓库安装：

```bash
pipx install ./cli --force
oks --version
oks capability list
```

初始化隔离知识库：

```bash
oks init ./oks-poc
export OKS_ROOT=./oks-poc
oks status
```

Windows PowerShell：

```powershell
oks init .\oks-poc
$env:OKS_ROOT = ".\oks-poc"
oks status
```

## 核心链路

```text
Source
  -> Capture / Existing Skill
  -> Raw Bundle
  -> Agent Distill
  -> Candidate
  -> Human Review
  -> Wiki
  -> Search / Recall
  -> Agent Output
```

飞书只是 Optional Control Plane，不是这个链路的必要条件。

## 当前仓库结构

```text
open-knowledge-studio/
├── .agents/          # Agent skill 副本
├── .claude/          # Claude Code skills
├── .codex/           # Codex 本地配置、hooks
├── cli/              # Python 包；提供 oks 与 oks-connector 入口
├── docs/             # GitHub Pages 文档
├── drafts/           # 仓库内示例/工作草稿；知识实例中也有 drafts/
├── profiles/         # 画像、目标、配方
├── raw/              # Raw materials
├── schemas/          # Raw/capture 协议 schema
├── scripts/          # connector、extractors、worker、validator
├── settings/         # 路由、输入源、衰减等配置
├── templates/        # Wiki / draft 模板
├── wiki/             # 策展知识
├── _meta/            # frontmatter 与学习 schema
├── AGENTS.md         # 本文件
├── CONSTITUTION.md   # 记忆系统设计
└── README.md
```

运行时目录如 `.oks/`、`.codex-tmp/`、`output/`、`tmp/` 是本地实验或运行产物，不是公开知识结构的核心层。

## Agent Skills

| Skill | 用途 |
|---|---|
| `/start` | 首次初始化和结构扫描 |
| `/ingest` | 读取 Raw，分级并生成 Candidate |
| `/query` | 通过 search/recall 回答并带证据 |
| `/lint` | 检查 wiki frontmatter、孤儿页、坏链等 |
| `/compile` | 从来源重新编译概念页到 drafts |
| `/status` | 查看知识库状态 |
| `/archive` | 抽取对话 Q&A 并形成草稿 |
| `/promote` | 审核 drafts 并晋升或拒绝 |
| `/media-ingest` | 实验性媒体采集适配 |

## CLI 命令

```bash
oks init <path>
oks ingest <source> [--mode quick|forensic] [--progress]
oks capability list
oks capability install document|pdf|formula|watch --yes
oks drafts list
oks drafts promote <slug>
oks drafts reject <slug>
oks wiki list|get|create|pin|archive|use
oks search <query>
oks recall <query>
oks lint
oks status
oks metrics
oks decay
oks feishu auth|form|submit|run-once|listen|setup
```

文档与真实 CLI 冲突时，以 `oks --help`、`oks <command> --help` 和代码为准，并记录文档问题。

## 操作规则

- 生产个人知识库是 `D:\knowledge\oks-personal-knowledge`；本仓库是可复用 Studio 代码，不要误写生产库。
- 所有 push、PR 创建/更新/关闭、Merge、Pages/Release 发布、部署、远端设置变更、外部消息发送，都需要用户对该动作的明确授权。
- 不要自动晋升 Candidate；必须等人类明确 `接受 / 批准 / accept`。
- 保留 `partial`、`failed`、`skipped`、`environment_limited`，不要把不完整结果说成通过。
- 机械提取、Agent 理解、人工审核、Wiki 晋升必须分离并可追溯。
- 不要重建插件市场、Skill Hub、Agent 框架、队列系统或分布式 Worker，除非第一个知识闭环确实需要。
