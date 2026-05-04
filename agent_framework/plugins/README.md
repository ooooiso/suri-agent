# 插件清单

> 所有插件的快速索引。suri 通过此清单查询插件能力、工具能力。
> 每个插件一个目录，包含 `manifest.json`（元信息）和 `plugin.py`（入口）。

---

## 插件列表

| 插件 ID | 类型 | 版本 | 描述 | 状态 |
|---------|------|------|------|------|
| `access` | integration | 1.0.0 | 终端 CLI 与 Telegram Bot 访问通道 | active |
| `agent_registry` | capability | 1.0.0 | Agent 生命周期管理 | active |
| `code_tool` | tool | 1.0.0 | 代码读写执行工具 | active |
| `config_service` | service | 1.0.0 | 统一配置中心，支持热重载 | active |
| `interrupt_handler` | capability | 1.0.0 | 任务执行受阻时的系统级处理 | active |
| `llm_gateway` | service | 1.0.0 | 5 家国内大模型路由与多版本管理 | active |
| `log_service` | service | 1.0.0 | 分级日志、分类归档 | active |
| `role_manager` | service | 1.0.0 | 角色管理：核心角色 suri 的创建与 Soul 管理 | active |
| `security_service` | service | 1.0.0 | 安全沙箱与权限管控 | active |
| `task_planner` | capability | 1.0.0 | 任务分解引擎 | active |
| `task_scheduler` | capability | 1.0.0 | 任务调度中心 | active |

---

## 插件类型说明

| 类型 | 说明 | 权限特征 |
|------|------|---------|
| `service` | 基础服务，被其他插件依赖 | 通常有 `system.*` 权限 |
| `tool` | 工具能力，供角色调用 | 通常有 `tool.call` 权限 |
| `capability` | 业务能力，处理特定业务逻辑 | 通常有 `task.*`、`agent.*` 权限 |
| `integration` | 外部集成，连接外部系统 | 通常有 `user.command` 权限 |

---

## 工具索引

> 插件下的 MCP 工具能力。suri 开发工具，所有角色调用工具。

### code_tool — 代码读写执行工具

| 工具名 | 描述 | 参数 |
|--------|------|------|
| `read_file` | 读取文件内容 | `path` |
| `search_files` | 正则搜索文件 | `path`, `regex` |
| `list_files` | 列出目录文件 | `path`, `recursive` |
| `list_code_definition_names` | 列出源代码定义 | `path` |
| `write_to_file` | 写入文件内容 | `path`, `content` |
| `replace_in_file` | 替换文件中的内容 | `path`, `diff` |
| `execute_command` | 执行 CLI 命令 | `command` |

### access — 访问通道

| 工具名 | 描述 | 参数 |
|--------|------|------|
| `cli` | 终端 CLI 交互 | `command` |
| `telegram` | Telegram Bot 交互 | `message`, `chat_id` |

### llm_gateway — 大模型路由

| 工具名 | 描述 | 参数 |
|--------|------|------|
| `chat` | 调用大模型对话 | `provider`, `model`, `messages` |
| `stream_chat` | 流式对话 | `provider`, `model`, `messages` |

---

## 插件依赖关系

```
suri_core（框架核心）
    │
    ├── config_service（配置中心）
    │   └── 被所有插件依赖
    │
    ├── security_service（安全沙箱）
    │   └── 被 code_tool 依赖
    │
    ├── llm_gateway（大模型路由）
    │   ├── 被 task_planner 依赖
    │   └── 被 task_scheduler 依赖
    │
    ├── role_manager（角色管理）
    │   └── 被 task_planner 依赖
    │
    ├── agent_registry（Agent 管理）
    │   ├── 被 interrupt_handler 依赖
    │   └── 被 task_scheduler 依赖
    │
    ├── task_planner（任务分解）
    │   └── 输出给 task_scheduler
    │
    ├── task_scheduler（任务调度）
    │   └── 被 interrupt_handler 依赖
    │
    ├── interrupt_handler（中断处理）
    │
    ├── code_tool（代码工具）
    │
    ├── log_service（日志服务）
    │
    └── access（访问通道）
```

---

## 快速查询

### 按类型查询

```bash
grep -r '"type": "tool"' plugins/*/manifest.json
grep -r '"type": "service"' plugins/*/manifest.json
grep -r '"type": "capability"' plugins/*/manifest.json
grep -r '"type": "integration"' plugins/*/manifest.json
```

### 按依赖查询

```bash
# 查询依赖了某个插件的所有插件
grep -r '"llm_gateway"' plugins/*/manifest.json
```

### 按事件订阅查询

```bash
# 查询订阅了某个事件的所有插件
grep -r '"tool.call"' plugins/*/manifest.json