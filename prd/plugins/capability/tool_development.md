# MCP 工具开发规范

> 指导如何为 MCP 框架开发新的工具。

---

## 一、工具开发流程

```
1. 确定工具功能
   └─ 工具做什么？输入/输出是什么？
       │
       ▼
2. 实现工具逻辑
   └─ 独立函数/类，无框架依赖
       │
       ▼
3. 注册到 mcp_framework
   └─ 通过 tool.registered 事件
       │
       ▼
4. 验证工具
   └─ 角色调用测试
```

## 二、工具注册

```python
await self._event_bus.publish(Event(
    event_type="tool.registered",
    source="mcp_framework",
    payload={
        "server_name": "custom_server",
        "tools": [
            {
                "name": "custom_server.my_tool",
                "description": "工具描述",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string"},
                    },
                    "required": ["param1"],
                },
            }
        ],
    },
))
```

## 三、安全要求

1. **输入校验** — 所有参数必须校验
2. **路径安全** — 文件操作使用白名单路径
3. **命令安全** — shell 命令使用白名单命令集
4. **超时控制** — 设置合理的超时时间（默认 30s）
5. **资源限制** — 限制内存、CPU 使用
