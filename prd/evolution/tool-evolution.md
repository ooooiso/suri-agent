# 工具进化（Tool Evolution）

> 定义 suri-agent 中 MCP 工具和插件工具的进化机制。工具进化包括工具的注册、版本管理、废弃和迁移。

---

## 一、工具定义

在 suri-agent 中，"工具"指角色可通过 mcp_framework 调用的一切能力：

| 工具类型 | 提供方 | 示例 |
|---------|--------|------|
| MCP 工具 | 外部 MCP 服务器 | 搜索、计算器、API 调用 |
| 插件工具 | 插件声明的 expose.tools | code_tool 的文件操作 |
| 内建工具 | suri_core 自带 | 事件总线查询、插件注册表查询 |
| skill 工具 | 角色自身的 skill | 自动化脚本、模板引擎 |

## 二、工具版本管理

```
工具注册时声明：
  name: string           # 工具名（全局唯一）
  version: string        # semver 格式
  api_version: string    # 接口版本（向后兼容检查用）
  provider: string       # 提供方标识（plugin_id / mcp_server_id）

版本兼容规则：
  major 相同 → 向前兼容，直接升级
  major 不同 → 不兼容，需要迁移
```

## 三、工具进化触发条件

| 触发条件 | 触发方 | 说明 |
|---------|--------|------|
| 插件升级 | plugin_manager | 插件升级时更新声明工具 |
| MCP 服务变更 | mcp_framework | 外部 MCP 服务版本变更 |
| 工具废弃 | 管理员/suri | 工具不再维护，标记为 DEPRECATED |
| 新工具注册 | 插件/MCP | 提供新的工具能力 |

## 四、工具注册流程

```
新工具准备就绪
    │
    ▼
发布 tool.registered 事件（含完整 tool_catalog）
    │
    ▼
mcp_framework 更新工具注册表
    │
    ▼
通知所有插件（system.config_changed 或 tool.registered）
    │
    ▼
插件刷新可用工具列表
```

## 五、工具废弃流程

```
工具被标记为 DEPRECATED
    │
    ▼
发布 tool.deprecated 事件（含替代工具名）
    │
    ▼
mcp_framework 保留但标记 DEPRECATED
    │
    ▼
通知所有订阅者

版本迁移周期：
  1. DEPRECATED 标记保留 2 个主版本
  2. 2 个主版本后自动移除
  3. 移除前通知所有已知调用方
```

## 六、工具发现机制

```
角色需要某工具时：
  1. 查询 mcp_framework 能力索引
  2. 按 name、tags、capability 过滤
  3. 获取匹配的工具元数据（参数 schema、描述）

mcp_framework 提供以下查询接口：
  list_tools():                  # 列出所有可用工具
  find_tool(name):               # 按名称查找
  search_tools(keywords):        # 按关键词搜索
  get_tool_schema(tool_name):    # 获取工具参数 schema
```

## 七、工具与 code_tool 的边界

| 维度 | code_tool | mcp_framework 工具 |
|------|-----------|-------------------|
| 用途 | 文件系统操作 | 通用能力调用 |
| 调用方式 | 插件内部方法 | 事件驱动 tool.call |
| 注册方式 | 插件内固定 | 动态注册/发现 |
| 版本管理 | 随插件版本 | 独立版本 |
| 外部依赖 | 无 | 可依赖外部 MCP 服务 |

> code_tool 是 mcp_framework 的特殊实现：它是文件系统操作的内建工具，注册到 mcp_framework 的工具注册表中，因此角色可通过统一的 tool.call 事件调用 code_tool。