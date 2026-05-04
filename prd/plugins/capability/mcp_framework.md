# mcp_framework 插件 PRD

## 定位

MCP（Model Context Protocol）服务框架插件，提供工具协议的统一接口规范、服务注册发现、调用路由。是连接大模型与外部能力的标准化协议层。

## 功能需求

### 1. MCP Server
- 统一接收工具调用请求
- 路由到具体工具执行
- 返回标准化响应格式
- 支持同步和异步调用

### 2. MCP Client
- 协议客户端，向 MCP Server 发起工具调用
- 支持本地 Server（同进程）和远程 Server（HTTP/SSE）
- 连接池管理

### 3. Registry 注册发现
- 维护可用工具清单（`mcp/registry.py`）
- 扫描内置工具（`mcp/services/`）和运行时工具
- 服务健康检查
- 按名称/类型/能力查询

### 4. 服务基类
- `BaseMCPService` — 所有 MCP 服务必须继承
- `MCPTool` — 工具定义基类
- 自动注册到 Registry

### 5. 统一工具注册中心

MCP Framework 是系统**唯一的工具注册中心**，所有工具（内置服务 + 外部 MCP 服务）统一在此注册、发现、调用。

#### 注册机制
- 内置服务：启动时自动扫描 `mcp/services/` 目录注册
- 外部服务：通过 MCP Client 连接远程 MCP Server 后注册
- 运行时动态注册/注销（无需重启）
- 注册信息：tool_id、名称、描述、参数 schema、权限级别、服务地址

#### 权限级别
- `public` — 所有角色可用（file_read、file_list、db_query、web_fetch）
- `maintainer` — 仅维护者角色可用（model_manager 管理操作）
- `role:{role_id}` — 仅指定角色可用

#### 参数验证
- JSON Schema 校验（类型、必填、范围）
- 失败返回明确错误，不进入执行阶段

#### 调用路由
- `tool.call` 事件进入 MCP Server
- Server 根据 tool_id 路由到对应服务（本地或远程）
- 超时控制（默认 30s）
- 调用审计日志记录到 `logs/tool_calls/`

### 6. 内置工具服务（框架内部模块）

所有内置服务由 MCP Server 统一托管，通过 Registry 自动注册。

#### filesystem — 文件系统服务
- `file_read(path)` — 读取文件（文本/二进制）
- `file_write(path, content)` — 写入文件（需 security_service 审批）
- `file_list(dir, pattern)` — 列出目录内容
- 路径隔离：禁止 `../` 和系统敏感目录

#### shell_exec — 命令执行服务
- `shell_exec(command, cwd, timeout)` — 执行 shell 命令
- 命令白名单机制（允许 `python/git/ls` 等）
- 黑名单拦截（`rm -rf /`、`format`、`dd` 等）
- 每次执行前需 security_service 审批
- 超时控制（默认 30s，最大 300s）

#### web_search — 网络搜索服务
- `web_fetch(url)` — 获取网页内容（HTML→Markdown）
- `web_search(query, limit)` — DuckDuckGo/Google/Bing 搜索
- 缓存机制（搜索 1h、网页 24h）
- 禁止访问内网地址和 `file://` 协议

## 接口定义

### 订阅事件
- `tool.call` → 路由到 MCP Server
- `system.started` → 扫描并注册所有服务

### 发布事件
- `tool.result`
- `error.tool`

## 事件 Payload Schema

### 订阅事件

#### `tool.call`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tool_name` | string | 是 | 工具名称 |
| `params` | object | 是 | 工具参数（按 schema 校验）|
| `caller_role` | string | 是 | 调用者角色 ID |
| `task_id` | string | 否 | 关联任务 ID |
| `request_id` | string | 是 | 请求唯一标识 |

### 发布事件

#### `tool.result`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 对应请求 ID |
| `tool_name` | string | 是 | 工具名称 |
| `result` | object/string | 是 | 执行结果 |
| `duration_ms` | integer | 否 | 执行耗时 |

#### `tool.error`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 对应请求 ID |
| `tool_name` | string | 是 | 工具名称 |
| `error_code` | integer | 是 | 错误码 |
| `error_message` | string | 是 | 错误描述 |
| `retryable` | boolean | 是 | 是否可重试 |

## 配置项

```yaml
mcp_framework:
  services_dir: "mcp/services/"
  auto_register: true
  remote_servers: []
```

## 依赖关系

- 上游：suri_core
- 下游：各 MCP 服务实现

## 生命周期

1. `init()` → 加载基类、扫描服务目录
2. `start()` → 初始化所有服务、注册到 Registry
3. `stop()` → 关闭所有服务
4. `cleanup()` → 注销注册、释放资源

## 安全边界

- 所有服务继承基类时自动继承安全检查
- 远程 Server 连接需认证
- 工具调用参数 schema 校验