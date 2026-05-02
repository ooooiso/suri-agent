# access 插件 PRD

## 定位

统一接入插件，是系统的**唯一用户交互入口**。负责接收所有渠道的用户输入（终端/Web/Telegram/飞书/API），转换为标准事件发送到 event_bus；同时将系统输出按原通道返回给用户。

所有接入通道共享用户身份管理、会话管理和消息格式转换逻辑。

## 功能需求

### 1. 接入通道管理
插件内部包含多个可独立启用的接入通道：

#### CLI 通道
- 非阻塞终端输入（`asyncio.run_in_executor` + `input()`）
- 命令支持：`/help`、`/status`、`/model`、`/reload`、`/logs`、`/learn`、`/reports`、`/quit`
- 命令历史记录（`.cli_history`，保留 500 条）
- 输出美化（带框格式化）
- 非 TTY 环境自动降级为纯事件消费者

#### Web 通道
- RESTful API：`POST /api/chat`、`GET /api/status`、`GET /api/tasks/{id}`
- SSE 流式输出（Server-Sent Events）
- 会话 Cookie / Header 管理
- CORS 支持
- 静态资源托管

#### Telegram 通道
- Bot 轮询或 Webhook 模式
- 命令：`/start`、`/status`、`/help`、`/create_role`
- 私聊：与 suri 直接对话，用于创建角色、查看状态
- **项目群组（核心功能）**：
  - 动态创建/绑定项目群组（项目创建时自动执行）
  - 群组内 @角色名 路由：直接路由给对应角色
  - 角色回复通过 Bot 发回群组，带角色身份标识
  - 项目总监在群中主动播报进度
  - Markdown 格式输出、长消息分片
- 群组映射表：`project_groups.yaml`（project_id → chat_id）

#### Lark（飞书）通道（预留）
- 框架与 Telegram 统一抽象，预留飞书实现
- 事件订阅接收消息
- URL 验证（挑战码响应）
- 请求签名验证
- 富文本消息解析
- 预留：项目群、@角色路由、进度播报

#### API 通道
- RESTful API（`POST /v1/tasks`、`GET /v1/tasks/{id}/result`）
- API Key / JWT 认证
- 速率限制（令牌桶，默认 60 req/min）
- Webhook 回调通知
- OpenAPI 文档自动生成（`/docs`）

### 2. 统一事件转换
所有通道的输入统一转换为：
- `user.input` — 普通消息（含 user_id、content、channel、session_id）
- `user.command` — 命令消息（含 command、args、user_id、channel）

### 3. 统一输出路由
- 订阅 `llm.response`、`task.completed`、`task.failed`
- 根据消息的 `channel` / `session_id` 路由回对应通道
- CLI 直接打印、Web 通过 SSE 推送、Telegram/Lark 调用 Bot API 发送

### 4. 会话管理
- 跨通道会话隔离（session_id）
- 多用户并发支持
- 会话超时自动清理（预留）

## 接口定义

### 订阅事件
- `llm.response` → 按原通道返回给用户
- `task.completed` → 输出结果到对应通道
- `task.failed` → 输出失败原因到对应通道
- `task.completed` / `task.failed` → 输出结果/失败原因到对应通道
- `system.shutdown` → 关闭所有通道
- `interrupt.user_decision_needed` → 向用户呈现决策选项
- `security.approval_required` → 向用户呈现安全审批请求

### 发布事件
- `user.input` — 所有通道的普通消息
- `user.command` — 所有通道的命令消息
- `system.shutdown` — 用户主动退出
- `user.decision` — 用户对决策单的回复

## 事件 Payload Schema

### 订阅事件

#### `llm.response`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 请求 ID |
| `content` | string | 是 | 响应内容 |
| `channel` | string | 是 | 目标通道 |
| `session_id` | string | 是 | 会话 ID |

#### `task.completed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `result` | string | 是 | 结果 |
| `channel` | string | 是 | 目标通道 |

#### `task.failed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `error_message` | string | 是 | 失败原因 |
| `channel` | string | 是 | 目标通道 |

#### `system.shutdown`
触发关闭，无特定 payload。

#### `interrupt.user_decision_needed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `decision_id` | string | 是 | 决策单 ID |
| `question` | string | 是 | 问题 |
| `options` | array | 是 | 选项 |
| `channel` | string | 是 | 目标通道 |

### 发布事件

#### `user.input`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户 ID |
| `content` | string | 是 | 消息内容 |
| `channel` | string | 是 | 通道：cli / web / telegram / lark / api |
| `session_id` | string | 是 | 会话 ID |
| `project_id` | string | 否 | 所属项目 |
| `mention_target` | string | 否 | @提及的目标角色 |

#### `user.command`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户 ID |
| `command` | string | 是 | 命令名 |
| `args` | object | 是 | 参数 |
| `channel` | string | 是 | 通道 |
| `session_id` | string | 是 | 会话 ID |

## 配置项

```yaml
access:
  channels:
    cli:
      enabled: true
      history_file: ".cli_history"
      history_limit: 500
    web:
      enabled: false
      host: "127.0.0.1"
      port: 8080
      cors_origins: ["*"]
    telegram:
      enabled: false
      bot_token: ""  # 从 .env 读取
      project_groups: {}     # project_id → chat_id 映射
      enable_mention_route: true  # @角色路由
    lark:
      enabled: false
      app_id: ""
      app_secret: ""
      encrypt_key: ""
      # 预留：project_groups、enable_mention_route
    api:
      enabled: false
      host: "127.0.0.1"
      port: 8082
      api_keys: []
      rate_limit: 60
```

## 依赖关系

- 上游：suri_core
- 下游：task_scheduler（传递用户输入）、config_service（处理 /reload）、interrupt_handler（呈现用户决策选项）

### 与 role_comm 的边界

见 role_comm.md「与 access 的边界」。简要概括：
- **access 是「外部投影」**：将 Telegram/CLI/Web 等外部通道的消息转换为系统事件
- **role_comm 是「内部通信」**：角色间通过 EventBus + SQLite 队列通信
- **映射**：用户在 Telegram 群 @角色 → access 发布 user.input → 角色处理 → 角色回复通过 access 返回群。此过程可在 role_comm 中生成 message 记录用于审计。

## 内部模块结构

```
access/
├── plugin.py              # 插件主入口，通道生命周期管理
├── base.py                # 接入通道基类（AbstractAccessChannel）
├── cli.py                 # 终端通道
├── web.py                 # Web 通道（HTTP + SSE）
├── telegram.py            # Telegram Bot 通道
├── lark.py                # 飞书通道
└── api.py                 # API 通道
```

## 生命周期

1. `init()` → 加载各通道配置
2. `register_events()` → 订阅系统输出事件
3. `start()` → 启动所有 `enabled: true` 的通道
4. `pause()` → 暂停所有通道的新消息接收
5. `resume()` → 恢复
6. `stop()` → 按顺序关闭所有通道
7. `cleanup()` → 保存 CLI 历史、释放连接

## 安全边界

- 所有通道输入只转事件，不直接执行业务逻辑
- API 通道认证失败返回 401，不暴露内部状态
- Telegram/Lark Token 从环境变量读取，不硬编码
- 请求体大小限制（防内存炸弹）
