---
name: oks-feedback
description: 在真实 OKS 任务形成可评价体验后，把用户主观体验与 Agent 客观运行事实关联成一个统一产品验证 Sample。可由用户主动输入 /oks-feedback 触发；生成可复制的 Receipt，若当前环境已有可用且已授权的 lark-cli，询问用户并写入独立飞书反馈表，否则提供同一份 Receipt 和公开表单链接。适用于真实完整、部分完成、失败或用户放弃的 OKS 任务，不适用于演示、纯问答和机械重试。
---

# OKS 产品验证反馈

这是一个独立、可删除的产品验证 Skill，不是 OKS Core 能力。

本 Skill 收集的是“本轮已经发生了什么 + 用户如何感受”，不是重新评估、诊断或解释本轮任务。Agent Receipt 只记录观察事实，用户表单回答只记录用户判断，后续样本分析才属于研究推断。

## 主动调用

安装后，用户可以在真实 OKS 任务结束时主动输入：

```text
/oks-feedback
```

也可以直接说“记录这轮 OKS 产品体验”或“提交这次 OKS 实验反馈”。`/oks-feedback` 是 Skill 的调用名，不是 `oks feedback` CLI 命令；它只收集本轮已经发生的事实和用户体验，不重新运行任务。

对外只交付这个 Skill 文件夹。飞书 Base、表单、权限和反馈数据由研究负责人维护；推广用户不需要建表，也不需要知道 Base token。若用户环境本来就有可用的 `lark-cli`，Skill 可以使用它提交一条反馈；否则走公开表单路径。两条路径都使用同一份 Receipt 和同一组用户问题。

## 何时触发

每个真实 OKS 任务最多触发一次，且本轮必须已经形成可评价体验：

- 任务可以是 `complete`、`partial`、`failed` 或用户主动 `abandoned`；失败不等于没有研究价值。
- 演示、纯问答、未形成实际体验的尝试不触发。
- 同一任务的机械失败重试不重复触发；如果重试后形成了新的真实体验，作为新的 Sample 处理。

反馈收集失败、用户跳过、没有授权或表单不可用，都不能改变主任务结果、退出码或 OKS 后续流程。

## 固定流程

1. 先完成、交付或明确结束 OKS 主任务；不要为了反馈重新运行任务、重新调用 Provider 或改变任务状态。
2. 从当前会话、OKS 输出和本轮已经发生的动作中提取客观事实。不要猜测缺失值，也不得为了补全 Receipt 额外执行 OKS、Provider、依赖探测或性能测试；自然不可获得的信息写 `unknown`。
3. 生成一份 `OKS_FEEDBACK_RECEIPT`，把本轮运行事实、Guided Decision、Review 客观动作和 Recall 事实放进同一份 Sample。
4. 如果当前环境有可用且已授权的 `lark-cli`，并且环境中存在已经配置、实际可写且已验证的独立反馈目标：
   - 向用户询问表单中的用户判断；
   - 用户回答后，使用该环境中已验证的写入方式，把这些回答和同一份 Receipt 写入独立反馈表的一条记录；
   - 不得假设公开表单 `share token` 本身支持 CLI 匿名提交；公开链接不是“已验证可写目标”的证明；
   - 写入失败时转到公开表单路径，不影响主任务。
5. 如果没有可用的 `lark-cli`、没有授权、用户不愿授权或自动写入失败：
   - 不要尝试安装 CLI 或引导用户配置 Base；
   - 给用户公开表单链接；
   - 要求用户回答表单问题，并把完整 Receipt 粘贴到“Agent 运行信息”字段。

## 公开表单

`PUBLIC_FEEDBACK_FORM_URL = https://ncnopqg1t7jk.feishu.cn/share/base/form/shrcn9zM2xqzzLXXjLzIPjinu2e`

收集者维护的表单固定为 7 项：

1. 本次希望 OKS 完成什么（必填）
2. Agent 运行信息（可选，粘贴完整 Receipt）
3. 最终结果是否符合预期（必填）
4. Candidate Review 是否可判断（必填）
5. Guided Decision 体验（必填）
6. Recall 结果（必填）
7. 其他反馈（可选）

推广用户只看到 Skill 提供的链接，不接触表单管理页面。表单链接如果失效，只提示反馈入口暂不可用；不要猜测、拼接或伪造新链接。

## 自动提交路径的用户提问

只有在 `lark-cli` 已经可用、存在已验证可写目标且用户明确愿意由当前 Agent 提交时，才在对话中询问以下问题。Agent 不得从任务结果推断或代选答案：

1. 这次你想让 OKS 帮你完成什么？
2. 最终结果符合你的预期吗？选：符合预期 / 部分符合预期 / 不符合预期。
3. Review Candidate 时，你能判断它是否值得保留吗？选：能判断 / 有点拿不准 / 不能判断 / 本轮没有 Review。
4. 当 OKS 让你决定安装能力、付出成本或接受部分结果时，这个过程怎么样？选：有帮助 / 一般 / 有点打扰 / 更困惑 / 本轮没遇到。
5. 这次 Recall 的结果怎么样？选：找到且有帮助 / 找到但帮助不大 / 部分找到 / 没找到 / 本轮未使用。
6. 这次最不舒服、最困惑，或者最希望改进的是什么？可选。

用户没有完成所有必填问题前，不提交；可选问题允许留空，不得使用默认值替用户回答。自动提交不得把 Base token、凭据或用户权限写入 Skill；具体写入方式必须来自环境中已配置并验证过的目标。无法确认目标或权限时，立即使用公开表单路径。

## 统一 Receipt

Receipt 是同一轮实验的客观运行事实，供研究负责人把用户判断和工程上下文关联分析。它不是 OKS 运行时协议，不写入 Raw、Candidate、Wiki、trace 或 OKS 实例目录。

生成 JSON，用户可以整段复制。实际值必须来自当前轮次；无法可靠知道的值写字符串 `unknown`，没有事件写空数组 `[]`。

```json
{
  "type": "oks_feedback_receipt",
  "version": "v1",
  "sample": {
    "id": "oks-YYYYMMDD-xxxx",
    "timestamp": "unknown",
    "oks_version": "unknown",
    "harness": "unknown"
  },
  "task": {
    "source_type": "unknown",
    "system_result": "unknown"
  },
  "strategy": {
    "configured": "unknown"
  },
  "execution": {
    "capabilities": {
      "required": [],
      "used": []
    },
    "providers": {
      "attempted": [],
      "succeeded": []
    },
    "dependency": {
      "required": [],
      "installed": [],
      "outcome": "unknown"
    },
    "fallback": {
      "occurred": "unknown",
      "summary": "unknown"
    }
  },
  "decisions": [],
  "cost": {
    "new_install": "unknown",
    "install_size": "unknown",
    "install_time": "unknown",
    "remote_service_used": "unknown",
    "paid_service_used": "unknown",
    "monetary_amount": "unknown",
    "processing": "unknown",
    "source_uploaded": "unknown",
    "elapsed": "unknown"
  },
  "review": {
    "occurred": "unknown",
    "action": "unknown"
  },
  "recall": {
    "occurred": "unknown",
    "query_raw": "unknown",
    "result_count": "unknown",
    "mechanical_result": "unknown"
  },
  "errors": []
}
```

### Receipt 填写规则

- `sample.id` 使用当天日期和短随机后缀；不要使用姓名、邮箱、文件名或 URL。
- `source_type` 只记录模态，例如 `pdf`、`web`、`markdown`、`image`、`audio`、`video` 或 `mixed`；不记录来源原文或来源 URL。
- `task.system_result` 只允许 `complete`、`partial`、`failed`、`abandoned` 或 `unknown`；它表示系统客观结束状态，不受用户满意度影响。
- `strategy.configured` 记录当前实际配置，例如 `lightweight`、`quality`、`privacy` 或 `ask_each_time`；不知道就写 `unknown`。
- `capabilities`、`providers`、依赖和 fallback 只记录本轮实际观察到的能力、调用、成功和失败。Provider 由 Agent 负责选择和记录，不把 Agent 的 Provider 切换伪装成用户决策。
- `decisions` 只记录真实的用户权衡：是否安装能力、使用远程服务、上传资料、产生费用或接受 Partial。每项至少应能表达 `agent_recommendation`、`user_choice`、`outcome`；没有决策就保持 `[]`。正常情况下 0 或 1 条，多条只如实记录。
- `cost` 只记录可靠可得的安装、远程、付费、隐私和时间事实。不能可靠取得的下载大小、内存、价格或耗时必须写 `unknown`，禁止估算。
- `review.action` 只允许 `approved`、`edited_then_approved`、`rejected`、`deferred`、`not_reached` 或 `unknown`；不要写“Review 成功”等结论。
- `recall.query_raw` 保留本轮实际使用的用户原始查询，不要改写成关键词；若含敏感内容，写 `redacted`。不要上传来源原文、完整私有资料、Cookie、API Key、access token 或其他凭据。
- `recall.mechanical_result` 只能写 `results_returned`、`no_results`、`error` 或 `unknown`；用户是否觉得结果有帮助只能来自表单回答。
- 本 Skill 不生成 Recall Failure Category。前至少 50 条真实 Recall Query 只收集上述事实；Failure Taxonomy 由研究负责人后续离线形成。
- `errors` 只能包含脱敏的 `stage`、`code`、`summary`；`summary` 要简短，不得复制完整 stderr、traceback、HTTP header 或远程响应正文。
- 不生成 `review_quality`、`guided_decision_quality`、`recall_success` 等替用户下结论的字段。

### Guided Decision 的决策事件

如果本轮因能力缺失、安装、远程处理、付费、隐私或接受 Partial 等真实用户权衡触发 Guided Decision，使用类似结构记录当时事实。Provider 的技术选择仍放在 `execution.providers`，不要作为用户决策：

```json
{
  "reason": "ocr capability missing",
  "agent_recommendation": {
    "capability": "image.ocr",
    "approach": "local_install"
  },
  "user_choice": {
    "action": "install"
  },
  "outcome": {
    "success": true,
    "task_effect": "full_extraction_enabled"
  }
}
```

不清楚用户最后如何选择时写 `unknown`，不替用户补全。实际成本仍写在 `cost` 中；不要把推测写进决策事件。

## 用户提示模板

完成 Receipt 后，先交付主任务，再按分支使用以下模板。

自动提交前先问完用户问题；提交成功后只报告“反馈已记录”和本轮 Sample ID，不展示或改写用户答案。

没有自动提交时：

```text
这轮真实 OKS 实验已经形成可评价体验。为了改进 OKS，请花 1–2 分钟填写一次产品反馈：

PUBLIC_FEEDBACK_FORM_URL

请回答表单中的体验问题，并把下面完整的 OKS_FEEDBACK_RECEIPT 原样粘贴到“Agent 运行信息”字段；不需要阅读或修改它。表单不收联系方式。

​```json
{在此粘贴本轮生成的完整 Receipt}
```
```

任务即使是 `partial`、`failed` 或 `abandoned` 也可以使用这个模板，只要已经形成真实可评价体验。机械重试不重复触发。

## 失败与隐私边界

- Feedback 失败绝不能阻塞 OKS 主任务；自动提交失败立即降级为“公开表单 + 同一份 Receipt”。
- 不修改 OKS Core、Raw、Candidate、Wiki、Recall、trace、策略配置或任务退出结果。
- 不为了反馈重新执行任务、调用 Provider、安装能力或上传来源。
- 不自动分析反馈、不自动改策略、不训练推荐逻辑、不建立 telemetry、analytics 或数据库。
- 不上传来源原文、来源 URL、完整私有资料、凭据、Cookie 或 API Key。
- 不替用户填写最终结果、Review 判断、Guided Decision 体验、Recall 体验或其他反馈。
- 反馈 Skill 始终是独立、可删除的实验工具。

```
