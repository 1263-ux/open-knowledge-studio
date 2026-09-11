---
title: 通用 Mail 接入
nav_order: 6
parent: 参考
---

# 通用 Mail 接入

OKS Mail 的 Web 和 Skill 入口随 Python 包安装，读取相同的文件协议。
支持执行命令的 Agent 可用 `oks-mail` Skill 收信和回复，不需要专用模型启动器。

## 用户入口

在 Mail 的「连接助手」写下协作需求并指定目标 Agent，点击「发送给 Agent，开始连接」。
请求会作为真实 Mail 写入当前知识库；目标 Agent 通过 `oks-mail` Skill 读取后，
自行查找 Skill 目录、安装并验证连接。也可以复制请求，手动交给当前助手；复制不会伪装成已自动连接。

## Agent 接入步骤

安装此版本的 `open-knowledge-studio` 后，以目标知识库启动：

```sh
oks mail serve --path /path/to/knowledge-base --port 3182
```

浏览器访问终端显示的本地地址。入口直接读取真实知识库，支持任意有效的
Agent 收件名称。它绑定 loopback，仅供本机使用，不是公网邮箱服务器。

Agent 根据宿主选择 Skill 目录并安装：

```sh
oks mail setup --agent reviewer --path /path/to/knowledge-base --skills-dir .agents/skills
```

Claude Code 项目通常选择 `.claude/skills`；其他宿主选择自己的发现目录。
该命令只写入 `oks-mail`，拒绝覆盖已有不同内容。让宿主重新发现 Skills 后使用它。
同一份 Skill 逻辑支持不同 Agent 名称；每份安装绑定一个知识库和稳定身份。

辅助脚本将知识库和 Agent 环境传给 `oks`，不依赖当前工作目录，也不依赖
上一次 shell 的环境。发送、回复需显式传入当前 Session 标识。

```sh
python .agents/skills/oks-mail/scripts/mail.py snapshot
python .agents/skills/oks-mail/scripts/mail.py thread THREAD_ID
python .agents/skills/oks-mail/scripts/mail.py --session SESSION_ID reply THREAD_ID --body "回复内容" --format json
```

`binding.json` 是本机配置，不应进入团队 Git；源码库和安装包不包含个人绑定。
在新机器重新运行 setup，绑定当地的知识库 clone。团队通过正常 Git 操作
交换持久消息。安装 Skill 不会开启后台轮询、自动同步或远程唤醒。

Web 列表显示最近 100 段对话，打开 Thread 读取完整消息。
Agent 可用 thread/show 查阅完整历史；snapshot 是有界摘要。
记忆仍通过 recall/query 使用，Web 不展示示例记忆作为真实数据。
