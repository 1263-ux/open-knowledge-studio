---
title: 故障排除
nav_order: 3
parent: 参考
---
# 故障排除

## `oks` 命令找不到

`pipx ensurepath` 后重新打开终端（PATH 需重载）。

## `oks --version` 过旧

```bash
pipx upgrade open-knowledge-studio
```

## `oks recall` 返回空

`wiki/` 空是正常的——新实例没有知识。先 `oks ingest run <file>` 存材料到 `raw/`，或写一个 wiki 页（`oks wiki create`），再 recall。

## hook 不注入会话

`oks hook status` 确认安装路径；重启 Agent host（hook 在启动时读配置）。

## `oks ingest run` 报缺能力

重提取器是 opt-in：

```bash
oks capability install <watch|document|pdf|formula> --yes
```

纯 `.md` / `.txt` 只需 `document`；URL 取决于来源。

## pip 拒绝安装（externally-managed）

PEP 668：用 `pipx`，不要裸 `pip`。

## 镜像滞后于 PyPI

`pipx install open-knowledge-studio --pip-args="-i https://pypi.org/simple"`
