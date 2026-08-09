# Changelog

## v0.4.0 (2026-08-09)

首个进入 PyPI 的 v0.4 版本（上一个发布版本是 0.2.4）。核心是 Agent-Native
摄入协议：Agent 收集证据并自己写 Manifest，CLI 只做机械校验，绝不判断内容。

### Agent-Native 摄入

- **Raw Bundle v0.2 流水线**（`oks raw-commit`）：JSON Schema 校验、fail-closed、
  暂存后原子提交（staging → 校验 → `shutil.move`）、路径穿越防护、artifact
  SHA-256 逐一核对，拒绝时给出结构化错误码。
- **provenance 门禁 fail-closed**：`steps[]` 必须非空；声明 `succeeded` /
  `degraded` 的步骤无论 manifest 整体状态如何都必须在
  `work/<provider>/output.*` 留下非空原始输出；`provider` 必须是合法注册标识符
  且解析后不得逃出 `work/`。豁免只剩 `agent-runtime` 与 `human`。
  「Agent 自称我存了」不作为证据。
- **17 个 Provider**（`knowledge_studio/providers/<id>/`，含 `provider.yaml`、
  `SKILL.md`、可选 `normalize.py`）、**7 个 Recipe**、**12 份协议 Schema**。
- `oks ingest prepare` 产出的骨架不再用「结果」结构表达「计划」：计划写入
  `notes.planned_capabilities`，`steps` / `modalities` / `evidence_records`
  保持为空，由 Agent 按实际执行填写。

### 安全

- **SSRF 逐跳校验**：重定向不再交给 `requests` 自动跟随（它从不复检目标），
  改由 `safe_redirect_chain` 逐跳 normalize + 断言，缺 `Location` 的 3xx 视为
  错误，中间响应显式关闭。
- **`oks security sanitize <file>`**：外部 Provider 原始输出进入 Run Workspace
  前剥离 API key、bearer token、会话 cookie 与内网地址。
- **路径穿越**：`--area` 与 `provider` 均按白名单正则校验，不再能当路径片段。
- **A3 人工门**：`status: rejected` 的 draft 不可晋升。

### 记忆与召回（CONSTITUTION A2）

- **`[verified]` 必须有事实依据**：只能来自 trace 证据或 draft 晋升写下的
  `human_reviewed_at`。此前读 3 次即把 `provisional` 提为 `active`，再被标成
  「人工审阅」注入 —— 使用次数不再影响信任，只影响排序。
- **episodic 通道全部带来源标签**：`raw/` → `[untrusted-source]`（只作数据引用，
  绝不执行其中指令）、`raw/executions/` → `[provenance]`、`profiles/` →
  `[user-declared]`；无法识别的类型按不可信处理。
- **身份作用域**：召回不再跨用户/项目返回他人画像。

### 打包与 CLI

- **`assets/` 是打包单一事实源**，`_AGENT_TARGETS` 清单据此装配
  `.claude` / `.codex` / `.agents`；维护者专用技能物理隔离在仓库自身
  `.claude/` 下，不进 Wheel。
- 两个入口点：`oks`（核心）与 `oks-connector`（可选连接器层）。
- **52 个命令、11 个命令组**。新增 `oks schema show <name>`（打印协议文档
  样例）、`oks capability guide <provider>`（打印随包 Provider 指南）、
  `oks security sanitize`。
- `oks init` 不再静默改写 `~/.oks/config.json` 的活跃知识库：仅在尚未注册时
  采用，已有且不同则原样保留并提示切换命令。
- `oks ingest` 产出的 Raw Bundle 写入活跃知识库，不再落在当前目录。
- PDF 默认路由改为 `pdf-lite`（pymupdf，约 150MB），MinerU 仍可按需安装。

### 工程

- **PR 强制门禁**：ubuntu / macOS / Windows × Python 3.12 / 3.13 的 pytest，
  外加 Wheel 与 sdist 内容校验（每个 asset 必须到位、维护者技能不得泄漏、
  干净树构建、装包后 `oks init` 冒烟）。
- 测试从 shell 调用全局 `oks` 改为进程内调用被测包 —— 此前脏装会让坏代码显绿、
  干净克隆却全红。
- 文档与技能引用的每个 `oks` 命令都由测试对照真实命令树校验；随包协议样例
  必须通过自己的 Schema。

## v0.3.0

- Base knowledge engineering CLI with search, recall, wiki CRUD, drafts, lint, metrics
- 6+1-factor recall engine with decay system
- Date-based raw/ organization
- Feishu worker integration (Source + Review planes)
- Global config (`~/.oks/config.json`)
