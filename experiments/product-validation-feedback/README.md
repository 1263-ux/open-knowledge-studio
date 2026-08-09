# OKS 产品验证反馈（独立实验）

这是 post-v0.4 的用户研究材料，不是 OKS 功能、Provider、运行时或 telemetry。
它不改动 `oks` 命令、Raw、Candidate Review、Feishu Pull 或知识库数据。

目标是在约 5 位真实用户的端到端使用中，持续收集一次实验对应一条的体验反馈，观察：

- 最终结果是否满足真实任务；
- Candidate Review 是否能做出判断；
- Guided Decision 是否带来帮助或摩擦；
- Recall 是否找到有用内容，以及失败类型。

## 推广方式

1. 研究负责人完成 `lark-cli` 用户授权后，运行 `python setup_base.py` 创建独立表和表单。
2. 在飞书 UI 开启“持链接可填写”，复制完整的 `/share/base/form/...` 链接。
3. 当前公开链接已经写入 [技能文件](skills/oks-feedback/SKILL.md)；如果以后重新生成链接，只需更新该文件的一行。
4. 将整个 `skills/oks-feedback/` 文件夹交给推广用户；他们只需安装该 Skill，并可在任务结束时输入 `/oks-feedback` 主动触发。

Skill 会在每次真实实验结束后，从当前任务已知事实生成统一 Receipt。若用户环境已有可用且已授权的 `lark-cli`，可以询问用户后自动写入独立表单；否则给出同一份 Receipt 和公开链接，由用户填写表单。两条路径的数据语义一致，且都不影响 OKS 主任务。

`setup_base.py` 仅供研究负责人在本机运行一次；它只创建这张 7 字段表和表单，不写入任何用户反馈。

对外只分发 `skills/oks-feedback/` 文件夹；`setup_base.py`、Base token、表单权限和反馈数据留在研究负责人侧。用户不需要建表或配置 Base。

## 边界

- 表单只收集 [form-spec.md](form-spec.md) 里的 7 个字段，不收联系方式。
- 每个真实实验最多提示一次；不是实验就不提示。
- Receipt 记录本轮客观运行事实；保留本轮原始 Recall Query，敏感时脱敏，不记录来源原文、完整私有资料或凭据。
- 不对用户的 Review、Guided Decision 或 Recall 体验代下结论。
- 反馈数据仅供人工产品验证，不自动改策略、不训练推荐逻辑。
