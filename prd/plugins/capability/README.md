# MCP 工具生态

> 定义 MCP（Model Context Protocol）工具生态：协议、开发、发现和内置服务。

---

## MCP 全景

```
MCP 生态
├── 协议标准 — 工具调用的统一协议
├── 工具开发 — 如何开发 MCP 工具
├── 工具注册发现 — 工具自动注册与发现
├── 内置服务 — 系统内置的 MCP 服务
│   ├── filesystem — 文件系统操作
│   ├── shell_exec — 命令执行
│   └── web_search — 网络搜索
└── 工具市场 — 第三方工具集成（未来）
```

---

## 目录结构

| 文档 | 说明 |
|------|------|
| [`mcp_protocol.md`](mcp_protocol.md) | MCP 协议规范 |
| [`tool_development.md`](tool_development.md) | 工具开发规范 |
| [`builtin_services.md`](builtin_services.md) | 内置 MCP 服务 |

---

## 核心原则

1. **统一协议** — 所有工具通过 MCP 协议调用
2. **插件式加载** — 工具以插件形式注册到 mcp_framework
3. **沙箱隔离** — 工具在安全沙箱中执行
4. **自动发现** — 工具启动时自动注册到 task_templates.yaml
