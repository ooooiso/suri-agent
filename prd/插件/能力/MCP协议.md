# MCP 协议规范

> 定义 MCP（Model Context Protocol）工具调用的统一协议。

---

## 一、协议格式

MCP 工具调用通过事件总线传递，统一格式：

### 请求

```python
Event(
    event_type="tool.call",
    source="role_id",
    payload={
        "tool_name": "filesystem.read_file",
        "arguments": {"path": "/tmp/test.txt"},
        "call_id": "uuid-xxx",
    }
)
```

### 响应

```python
Event(
    event_type="tool.result",
    source="mcp_framework",
    payload={
        "call_id": "uuid-xxx",
        "result": {"content": "文件内容..."},
        "error": None,
    }
)
```

## 二、工具命名

```
格式：{server_name}.{tool_name}
示例：
- filesystem.read_file
- filesystem.write_file
- shell_exec.run_command
- web_search.search
```

## 三、错误处理

| 错误类型 | 说明 |
|----------|------|
| `tool_not_found` | 工具不存在 |
| `invalid_arguments` | 参数校验失败 |
| `execution_error` | 执行时错误（如文件不存在） |
| `timeout` | 工具调用超时（默认 30s） |
| `sandbox_violation` | 违反沙箱安全规则 |

## 四、安全约束

1. **沙箱隔离** — 所有工具在受限安全沙箱中执行
2. **权限校验** — 调用工具时检查角色权限
3. **路径限制** — 文件操作限制在允许的白名单目录
4. **命令限制** — shell 执行限制在白名单命令集
