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
3. 注册到 Tool Registry
   └─ 通过 tool.registered 事件（三清单联动）
       │
       ▼
4. 广播通知
   └─ 发布 tool.registered → suri 感知 → 角色感知
       │
       ▼
5. 验证工具
   └─ 角色调用测试
```

## 二、工具注册流程（三清单联动）

```python
# 工具注册到 Tool Registry
await self._event_bus.publish(Event(
    event_type="tool.registered",
    source="mcp_framework",
    payload={
        "tool_id": "custom_server.my_tool",
        "name": "custom_server.my_tool",
        "description": "工具描述",
        "version": "1.0.0",
        "source_plugin": "my_plugin",
        "source_type": "local",
        "input_schema": {
            "type": "object",
            "properties": {
                "param1": {"type": "string"},
            },
            "required": ["param1"],
        },
        "status": "active"
    },
))

# 注册后的自动广播：
# 1. Tool Registry 记录新工具
# 2. tool.registered 事件发布
# 3. suri 接收事件 → 更新可用工具列表
# 4. 所有角色接收事件 → 更新 tool_descriptions
# 5. 用户可见通知
```

## 三、工具调用上下文（_meta）

所有工具调用自动携带 `_meta` 上下文：

```python
tool_call = {
    "name": "custom_server.my_tool",
    "params": {
        "param1": "value1",
        "_meta": {
            "role_id": "developer",           # ★ 调用角色
            "project_id": "ecommerce_app",     # ★ 所属项目
            "task_id": "T-001",                # ★ 关联任务
            "session_id": "dev_session_01",    # ★ 所属会话
            "timestamp": "2026-05-04T12:00:00Z"
        }
    }
}
```

### _meta 的作用

| 用途 | 说明 |
|------|------|
| 审计日志 | 记录谁在什么上下文中调用了什么工具 |
| 权限校验 | 角色在当前项目中是否有权使用此工具 |
| 归因统计 | Tool Registry 按角色/项目/任务统计 |
| 上下文隔离 | 事件根据 project_id 过滤，避免跨项目混淆 |
| 费用分摊 | 按角色/项目维度核算 LLM Token 消耗 |

## 四、工具的生命周期

工具从创建到废弃的完整流程：

```
工具创建
    │
    ├─ 注册到 Tool Registry → 状态: active
    │   发布 tool.registered → 广播通知
    │
    ▼
工具升级
    │
    ├─ 更新 Tool Registry 记录
    │   发布 tool.updated → 广播通知
    │
    ▼
工具废弃
    │
    ├─ Tool Registry 标记 → 状态: deprecated
    │   发布 tool.deprecated → 广播通知
    │   保留调用记录（只读）
    │   不再出现在新角色的 tool_descriptions 中
    │
    ▼
工具移除
    │
    ├─ Tool Registry 标记 → 状态: removed
    │   发布 tool.removed → 广播通知
    │   保留历史记录（仅审计用）
```

## 五、安全要求

1. **输入校验** — 所有参数必须校验
2. **路径安全** — 文件操作使用白名单路径
3. **命令安全** — shell 命令使用白名单命令集
4. **超时控制** — 设置合理的超时时间（默认 30s）
5. **资源限制** — 限制内存、CPU 使用