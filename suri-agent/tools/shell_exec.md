---
tool_id: shell_exec
description: 执行 shell 命令
permission: suri-dev
---

# shell_exec

执行 shell 命令。仅限 suri-dev 使用。

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| command | str | 是 | 要执行的命令 |

## 安全限制

- 禁止执行删除系统文件的命令
- 禁止执行网络下载命令
- 所有命令记录在审计日志中
