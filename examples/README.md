# examples/ — 真实案例与最佳实践

这里放**可复制的样例**，不是框架的一部分：

- `assets/` 是产品（打包给每个用户的实例模板）
- `examples/` 是示范（想用就 copy 到你自己的实例里改）

分开的好处是框架仓保持干净，示例可以放心迭代——加一个案例不影响任何人的安装。

## 目录

| 路径 | 是什么 | 怎么用 |
|---|---|---|
| `feishu-loop/` | **飞书采集审核闭环**：手机提交 → 异步采集 → IM 里审核 | 读 [`feishu-loop.md`](feishu-loop/feishu-loop.md)，把 [`goal.md`](feishu-loop/goal.md) 复制到 `profiles/goals/` |
| `goals/oss-contribution.md` | 真实 goal 范例：OSS 贡献（含 KR、ODD、召回加权说明） | 复制到 `profiles/goals/`，改 `owner` 与 `status: active` |
| `projects/open-knowledge-studio.md` | 项目画像范例（技术栈、约定、历史 PR 表） | 复制到 `profiles/projects/` |
| `users/example-profile.md` | 个人画像范例（偏好、技术栈、工作习惯） | 复制到 `profiles/users/<你的 id>/profile.md` |
| `datasets/recall-v1.example.yaml` | 召回评测数据集**格式示例** | 复制后换成你自己的真实查询，再跑 `oks eval recall` |
| `raw-bundles/` | 一个真实的 Raw Bundle 采集产物（含关键帧） | 用来理解 connector 的输出长什么样 |

## 关于评测数据集

`datasets/recall-v1.example.yaml` **只是格式示例，不能当真值集用**。
有意义的评测需要你自己的查询和你自己知识库里的正确答案——
别人的数据集测不出你的召回质量。

```bash
cp examples/datasets/recall-v1.example.yaml eval/datasets/mine.yaml
# 编辑：query 换成你真的会问的问题，relevant 换成你知道的正确页面
oks eval recall eval/datasets/mine.yaml --output eval/runs/baseline.json
```

## 关于个人画像与 goal

`goals/`、`projects/`、`users/` 下的内容是**维护者的真实使用记录**，
留在这里当范例——展示一个用了几个月的 goal / 画像长什么样，比空模板有参考价值。

空模板在 `assets/profiles/` 里，`oks init` 会自动物化到你的实例。
