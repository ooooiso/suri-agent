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

内置服务由 mcp_framework 插件在初始化时自动注册到 Tool Registry。

### 三清单联动

内置服务注册时自动同步到三清单体系：

```
mcp_framework 初始化
    │
    ├─ 1. 注册工具到 Tool Registry（名称、schema、source_plugin）
    ├─ 2. 发布 tool.registered 事件
    ├─ 3. suri 接收事件 → 更新自身认知
    ├─ 4. 所有角色接收事件 → 评估是否需要使用新工具
    └─ 5. 广播完成
```

### 工具调用上下文

所有内置服务工具调用时自动携带 `_meta` 上下文：

```python
tool_call = {
    "name": "filesystem.read_file",
    "params": {
        "path": "/path/to/file",
        "_meta": {
            "role_id": "developer",
            "project_id": "ecommerce_app",
            "task_id": "T-001",
            "session_id": "dev_session_01"
        }
    }
}
```

`_meta` 用于：
1. 审计日志记录（谁在什么项目什么任务中调用了什么工具）
2. 权限校验（角色在当前项目中是否有权操作此路径）
3. 归因统计（按角色/项目/任务维度统计工具使用量）