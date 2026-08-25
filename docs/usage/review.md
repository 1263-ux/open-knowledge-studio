---
title: 审核候选
nav_order: 2
parent: 日常使用
---

# 审核候选

AI 可以提出知识，但不能批准自己的提议。

## 查看候选

```bash
oks drafts list
oks drafts get <slug>
```

审核时回答四个问题：

1. 这句话能否回到具体来源或执行证据？
2. 它是事实、来源观点，还是 AI 推断？
3. 它是否与已有知识重复、补充、取代或冲突？
4. 它是否值得在未来任务中被主动召回？

## 三种决定

### 接受或修改后接受

```bash
oks drafts promote <slug>
```

Promote 会写入 `human_reviewed_at`，表示人类已经对这次状态变化负责。

### 拒绝

使用 `/promote` Skill 查看完整内容并确认拒绝。拒绝后 Candidate 离开待审队列，OKS 在 `drafts/rejected/` 保存 review receipt。

### 暂不决定

保留在 Draft。证据不足不是必须立即解决的问题；等待新的来源比制造确定性更安全。

## 不要这样审核

- 只看标题或摘要就 Promote。
- 因为内容被多次召回，就认为它更真实。
- 把第三方材料中的指令当作系统指令执行。
- 为了让 Wiki 看起来完整而删除不确定性描述。
- 在没有人类决定时批量自动晋升。
