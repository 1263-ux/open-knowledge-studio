# 阶段报告：仓库合并 + 健壮性修复

日期：2026-07-25
分支：`codex/upstream-v0.2.3-integration`

## 目标

将 `oks-connector` 合并到 `open-knowledge-studio` 单仓库，消除子进程调用带来的版本同步、错误传播和部署复杂度问题。

## 修改清单

### 核心合并（6 个已修改文件 + 2 个新增目录）

| 文件 | 改动 | 行数变化 |
|---|---|---|
| `scripts/raw_bundle_adapter.py` | connector 新版覆盖 Studio 旧版（2286→3701行） | +1527 |
| `scripts/tests/test_raw_bundle_adapter.py` | 新版覆盖，测试路径适配 | +545 |
| `cli/knowledge_studio/cli.py` | `oks ingest` 子进程→直接 import；`_CAPABILITIES` 移除 connector | 87 |
| `cli/pyproject.toml` | 合并 connector extras；添加 `oks-connector` 入口点 | 31 |
| `scripts/feishu_base_worker.py` | 移除 `connector_repo`/`connector_python` 硬编码 | 35 |
| `scripts/*_extract_requirements.txt` | 同步 connector 新版依赖声明 | 6 |
| `capabilities/` | 新增目录（从 connector 复制） | 8 files |
| `schemas/` | 新增目录（从 connector 复制） | 5 files |

### 合入的 connector 修复（P0-P2）

已在 `raw_bundle_adapter.py` 中合入：
- **P0-A**: 子进程错误不再沉默——非零退出码抛出 RuntimeError 携带 stderr
- **P0-B**: 解释器健康验证——`_validate_extractor_python()` 三重检查（启动+版本+模块导入）
- **P0-C**: 路由诊断——`route_plan()` 返回 `diagnostics` 字段，`run_ingest()` 展开中文报错
- **P1-A**: Progress 阶段标签——quick 模式下自动映射为准确标签
- **P1-B**: watch-skill 接口契约——monkey-patch 前验证目标函数存在
- **P2-A**: `oks-connector check` 自检命令

### 安装命令变化

```
# 之前（三步）
pipx install "git+...studio...#subdirectory=cli"
pipx inject open-knowledge-studio "git+...connector..."
pipx inject open-knowledge-studio ".\\connector[watch]" --force

# 现在（一步）
pipx install "git+...studio...#subdirectory=cli[watch]"
```

### 架构变化

```
# 之前
oks → subprocess(oks-connector ingest) → subprocess(python adapter.py watch)

# 现在  
oks → import run_ingest() → subprocess(python adapter.py watch)
      ^^^^^^^^^^^^^^^^^^       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      同进程直接调用              重型提取器仍走隔离解释器（依赖冲突）
```

## 回归测试结果

| 测试项 | 结果 |
|---|---|
| `scripts/tests/test_raw_bundle_adapter.py` | 39/39 通过 |
| `oks --version` | 0.2.4 |
| `oks capability list` | watch/document/pdf/formula/feishu（connector 已内置） |
| `oks-connector check` | watch 可用，markitdown/mineru 不可用（正确，未安装对应 extras） |
| `oks-connector check --minimal` | 版本兼容性检查通过 |
| `oks ingest <YouTube URL> --mode quick` | 正常输出 Raw Bundle（686 条字幕段） |
| `oks-connector` CLI 入口点 | 保留可用 |

## 已知限制

1. **重型提取器的隔离子进程保留**——watch-skill（faster-whisper+RapidOCR+yt-dlp）、MinerU、PaddleOCR 依赖冲突，必须各自独立解释器，子进程调用不变
2. **watch-skill 仍为外部 git 依赖**——不归我们维护，进度标签字符串可能随版本变化
3. **中文字幕 429**——YouTube IP 级限流，已写入 `%APPDATA%/yt-dlp/config.txt`（sleep/retry 参数），根治需 watch-skill 支持 `--cookies-from-browser`
4. **飞书 worker 未做全链路测试**——需要飞书租户、Base token、lark-cli 配置
5. **上游 diff 大**——与 `open-agent-power/open-knowledge-studio` main 分支差异 68 文件/10000+ 行，后续上游合并需人工处理冲突
6. **未做 forensic 模式测试**——只测了 quick，forensic（字幕锚点帧+OCR）需要 10-15 分钟

## 下一步建议

1. 跑一次 `oks ingest --mode forensic` 完整取证测试
2. 安装 document 和 pdf extras，测试本地文件路由
3. 配置飞书环境，跑一次飞书全链路
4. 确认后 commit + push + PR（需要授权）
