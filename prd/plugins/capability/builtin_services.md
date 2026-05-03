# 内置 MCP 服务

> 系统内置的 MCP 服务，开箱即用。

---

## 服务列表

| 服务 | 工具 | 说明 |
|------|------|------|
| **filesystem** | `filesystem.read_file` | 读取文件内容 |
| | `filesystem.write_file` | 写入文件 |
| | `filesystem.list_files` | 列出目录文件 |
| | `filesystem.search_files` | 搜索文件内容 |
| **shell_exec** | `shell_exec.run_command` | 执行 CLI 命令 |
| **web_search** | `web_search.search` | 网络搜索 |

## 安全约束

| 服务 | 限制 |
|------|------|
| filesystem | 仅允许操作白名单目录 |
| shell_exec | 仅允许执行白名单命令 |
| web_search | 受 API 速率限制 |

## 注册方式

内置服务由 mcp_framework 插件在初始化时自动注册。
