# 阶段历史与验收简报

> 截止日期：2026-07-23
> 目的：用这一份报告说明项目做过什么、真实通过了什么、仍缺什么。详细事实保存在 Base、Raw Bundle、Wiki、测试和 Git 历史中，不再维护重复的逐日 Run 文档。

## 1. 已形成的系统边界

- Studio 负责 Capture 编排、Candidate、人工审核、Wiki、召回和反馈。
- 独立 `oks-connector` 负责文件/链接获取后的机械解析、证据、质量和逐模态状态。
- Raw、AI 理解和 Wiki 分层保存；未经人工审核不得自动晋升。
- 当前协议事实源是 `oks-connector/schemas/`、`capabilities/` 和 `docs/protocols-v0.1.md`。
- 个人知识与代码仓库已经分离：运行实例位于 `D:\knowledge\oks-personal-knowledge`。

## 2. 已真实验证的解析能力

| 输入 | 复用能力 | 真实边界 |
|---|---|---|
| DOCX/PPTX | MarkItDown | 能生成 Markdown 与页/幻灯片 evidence，定位粒度有限 |
| 数字/扫描 PDF | MinerU | 能生成正文、版面和图片证据；公式/OCR 未人工逐项校对 |
| 图片 | RapidOCR | 保存文字、置信度、bbox 和原图；不等于 AI 视觉理解 |
| 音频 | faster-whisper | 正常语速可形成时间戳 ASR；困难样本可能真实失败 |
| 视频 | Watch、yt-dlp、OCR、ASR | 已取得的本地媒体可生成字幕/帧证据；平台 URL 获取仍受风控限制 |
| 公开 HTML | HTTP/浏览器快照、Trafilatura | 静态和受控浏览器样本已通过；登录、验证码和付费墙不保证成功 |

`valid=true` 只表示 Bundle 结构与证据一致，不表示 OCR、ASR、公式或语义百分之百正确。真实成功产物仍可能是 `partial`。

## 3. 飞书 Base 主 Loop 实验

测试 Base：

- 名称：`Open Knowledge Studio Raw Pipeline Test`
- Base token：`STeHbEo5lalFR9soQWIcuZAunxg`
- Table：`tblOtwfofnnSwL3f`
- Base 是采集、运行状态和人工审核的控制面，不替代 Raw 文件与 Wiki。

真实闭环样本：

| 决策 | Base record | Run | 结果 |
|---|---|---|---|
| `reject` | `recvq1fpIyaVS9` | `run-20260721T224656-c88cddfa` | Obsidian Clipper Candidate 因价值低、方向偏离被拒绝；没有 Wiki |
| `accept` | `recvq6nZfwztXx` | `run-20260722T195226-7db4031f` | 晋升 `wiki/computing/strategies/20260722-base.md` |
| `accept` | `recvq6Yr6qZGiX` | `run-20260722T222212-284bc2c7` | 个人飞书回复后晋升 `wiki/computing/strategies/20260722-feishu-review-return-provenance.md` |

第二个接受样本实际走过：

```text
Base Capture
  → web.trafilatura
  → Raw Bundle v0.2（421 条 evidence，总状态 partial）
  → Agent Teach-back Candidate
  → 个人飞书审核通知
  → 用户回复 “accept，有研究价值”
  → 审核事实写回 Base
  → Wiki 晋升
  → OKS recall
```

飞书 P2P 消息 API 没有为该 UI 回复暴露 `parent_id/root_id`。系统没有伪造原生引用，而是在“同一私聊、指定审核人、恰好一个待审 Candidate、相邻消息、单一明确动作”的约束下使用 `p2p_sequence_fallback`，并在状态中留痕。

## 4. 2026-07-23 收口验收

- `oks-connector`：33 项测试通过。
- Studio：96 项测试通过。
- 两个全新 Worker 进程连续运行 `review-once`，均返回 `no_pending_reviews`。
- 两次重复消费前后共 75 个 Candidate/Wiki/Draft 文件，数量与 SHA-256 全部不变。
- Base 当前可回读 2 条 `promoted`、1 条 `rejected`；失败、需授权和 `partial` 状态仍如实保留。
- OKS 全局 `knowledge_base_path` 已设置为 `D:\knowledge\oks-personal-knowledge`。
- 从代码仓库目录执行真实 recall，命中两篇个人 Wiki，并能继续回到 Raw evidence。

## 5. 私有备份与恢复

私有仓库：`1263-ux/oks-personal-knowledge`。

首轮备份包含：

- 2 篇已晋升 Wiki；
- 2 个对应 Raw Bundle v0.2；
- 1 个历史批准的口播 Raw 样本；
- Capture、晋升与迁移索引。

全新克隆恢复验证已通过：JSON/JSONL 可解析、两个来源快照 SHA-256 匹配、Wiki/Raw 索引可解析、召回与 evidence trace 命中、敏感信息和本机绝对路径扫描为零。原始大媒体、凭据、临时消息映射、`.venv` 和模型缓存不进入 Git。

## 6. 仍未完成

- 平台 URL 获取没有通用成功保证；登录浏览器、官方接口和付费兜底仍需按平台实践。
- 飞书审核监听器尚未部署为常驻服务。
- 当前改进尚未整理成面向上游的小范围 PR，也没有 Merge。
- GitHub Pages 未修改、未发布。
- 旧 worktree 尚未清理；必须等目标改进通过授权后的 PR/Merge 与最终恢复复核。
- `.venv` 和模型缓存继续保留，是否删除另行决定。

## 7. 下一门禁

1. 以个人知识仓库作为后续 Worker 的 `output_root`，代码仓库不再积累个人 Raw/Wiki。
2. 从现有宽分支中提取最小上游改进，先在本地展示 diff、测试和回退方式。
3. 只有用户明确授权后，才 Push、创建 PR、Merge 或发布 Pages。
4. PR 合并且个人仓库再次恢复验证通过后，才提出旧 worktree 清理清单。
