# Suri Agent 事件注册表

> 本文档是 suri-agent 所有事件类型的权威索引。包含事件 schema、发布者、订阅者、路由规则和版本信息。

---

## 事件分类

| 前缀 | 类别 | 数量 |
|------|------|------|
| `system.*` | 系统级 | 7 |
| `user.*` | 用户输入 | 3 |
| `task.*` | 任务生命周期 | 10 |
| `agent.*` | Agent 生命周期 | 6 |
| `role.*` | 角色通信 | 10（含 role_comm 完整事件链） |
| `llm.*` | LLM 网关 | 2 |
| `tool.*` / `error.tool` | MCP 工具 | 2 |
| `interrupt.*` | 中断处理 | 5 |
| `cron.*` | 定时任务 | 1+ |
| `security.*` / `error.security` | 安全 | 2 |
| `plugin.*` / `error.plugin` | 插件 | 2 |
| `doc_sync.*` | 文档同步 | 3 |
| `test.*` / `error.test` | 测试 | 2 |
| `upgrade.*` | 升级管理 | 4 |
| `hooks.*` | 事件钩子 | 5 |
| `error.*` | 通用错误 | 3 |

---

## 完整事件矩阵

### 系统事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `system.start` | suri_core | 所有插件 | CRITICAL | ✅ |
| `system.shutdown` | suri_core / access | 所有插件 | CRITICAL | ✅ |
| `system.heartbeat` | 所有插件 | suri_core | NORMAL | ❌ |
| `system.plugin_loaded` | suri_core | log_service / test_framework | NORMAL | ❌ |
| `system.plugin_unloaded` | suri_core | log_service | NORMAL | ❌ |
| `system.config_changed` | config_service | test_framework / 相关插件 | NORMAL | ❌ |
| `error.system` | suri_core | log_service / access | CRITICAL | ✅ |

### 用户输入事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `user.input` | access | task_scheduler / role_manager / 目标角色 | HIGH | ✅ |
| `user.command` | access | 各插件（按 command 路由） | HIGH | ✅ |
| `user.decision` | access | interrupt_handler | HIGH | ✅ |

### 任务事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `task.created` | 角色 / access | task_scheduler / role_learner | HIGH | ✅ |
| `task.plan_ready` | task_planner | task_scheduler | HIGH | ✅ |
| `task.planned` | task_planner | 角色 | NORMAL | ❌ |
| `task.step_ready` | task_planner | task_scheduler | HIGH | ❌ |
| `task.plan_updated` | task_planner | 角色 | NORMAL | ❌ |
| `task.queued` | task_scheduler | log_service | NORMAL | ❌ |
| `task.started` | task_scheduler | log_service / 角色 | NORMAL | ❌ |
| `task.completed` | task_scheduler | log_service / role_learner / 角色 / agent_registry | NORMAL | ✅ |
| `task.failed` | task_scheduler | log_service / interrupt_handler / 角色 / agent_registry | HIGH | ✅ |
| `task.timeout` | task_scheduler | log_service / interrupt_handler / agent_registry | HIGH | ✅ |
| `task.cancelled` | task_scheduler | log_service / 角色 | NORMAL | ✅ |
| `task.retried` | task_scheduler | log_service | NORMAL | ❌ |
| `task.priority_changed` | 角色 / 系统 | task_scheduler | NORMAL | ❌ |
| `task.cancel_requested` | 角色 / 用户 | task_scheduler | NORMAL | ❌ |

### Agent 事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `agent.create_requested` | 角色 / task_scheduler | agent_registry | HIGH | ✅ |
| `agent.step_update` | 角色 | agent_registry | NORMAL | ❌ |
| `agent.block_requested` | interrupt_handler | agent_registry | HIGH | ✅ |
| `agent.destroy_requested` | 角色 / 系统 | agent_registry | NORMAL | ❌ |
| `agent.created` | agent_registry | log_service / 角色 | NORMAL | ❌ |
| `agent.status_changed` | agent_registry | log_service / task_scheduler | NORMAL | ❌ |
| `agent.completed` | agent_registry | log_service / role_learner / 角色 | NORMAL | ✅ |
| `agent.blocked` | agent_registry | log_service / interrupt_handler | HIGH | ✅ |
| `agent.destroyed` | agent_registry | log_service | NORMAL | ❌ |

### 角色事件

#### 角色生命周期（role_manager）

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `role.create_requested` | access / 角色 | role_manager | HIGH | ✅ |
| `role.created` | role_manager | 所有角色 / agent_registry | NORMAL | ✅ |
| `role.destroyed` | role_manager | 所有角色 | NORMAL | ✅ |
| `role.skill_suggested` | role_learner | role_manager | NORMAL | ✅ |
| `role.skill_invoked` | role_manager | 角色 | NORMAL | ❌ |

#### 角色通信事件链（role_comm — 完整的事件驱动流程）

角色通信采用**链式事件**设计，分三步完成：

```
1. 发送方角色发布 role.message（输入事件）
    ↓
2. role_comm 内部处理：存储 → 按 session_id 分组
    ↓
3. role_comm 发布 role.message_received（通知事件）
    ↓
   接收方角色下次空闲时处理
```

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 | 说明 |
|------|--------|--------|--------|--------|------|
| `role.message` | 角色（发送方） | role_comm | HIGH | ✅ | **输入事件**。发送方角色发布消息到 role_comm |
| `role.message_received` | role_comm | 目标角色 | HIGH | ✅ | **通知事件**。告诉接收方"你有新消息" |
| `role.messages_batch` | role_comm | 目标角色 | HIGH | ✅ | 批量投递。接收方一次处理多条消息 |
| `role.messages_query` | 角色 | role_comm | NORMAL | ❌ | 查询某 session 的未读消息/历史 |
| `role.messages_consume` | 角色 | role_comm | NORMAL | ❌ | 消费某 session 的消息（标记已读） |
| `role.message_delivered` | role_comm | 发送方角色 | NORMAL | ❌ | 消息已成功投递通知 |
| `role.message_rejected` | role_comm | 发送方角色 / log_service | NORMAL | ✅ | 消息接收失败（如角色不存在） |

**事件路由规则**：
- `role.message`：`payload.to_role` 指定接收方，`payload.session_id` 指定会话
- `role.message_received`：`payload.to_role` 指向接收方角色 ID
- `role.messages_query`：`payload.session_id` 指定会话

**关键设计**：
- 一条 `role.message` 只对应一条 `role.message_received`（点对点通知）
- 角色在空闲时通过 `role.messages_query` 批量拉取，不实时响应
- 消息通过 session_id 隔离，不同 session 互不干扰

### LLM 事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `llm.request` | 角色 | llm_gateway | HIGH | ❌ |
| `llm.response` | llm_gateway | 角色 / access | HIGH | ❌ |
| `llm.error` | llm_gateway | 角色 / access | HIGH | ✅ |

### 工具事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `tool.call` | 角色 / mcp_framework | mcp_framework | HIGH | ❌ |
| `tool.result` | mcp_framework / code_tool | 角色 | HIGH | ❌ |
| `error.tool` | mcp_framework / code_tool | 角色 / log_service | HIGH | ✅ |

### 中断事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `interrupt.handled` | interrupt_handler | log_service / 角色 | NORMAL | ❌ |
| `interrupt.escalated` | interrupt_handler | role_comm / 目标角色 | HIGH | ✅ |
| `interrupt.user_decision_needed` | interrupt_handler | access | HIGH | ✅ |
| `interrupt.cancelled` | interrupt_handler | agent_registry | NORMAL | ❌ |
| `interrupt.retry_requested` | interrupt_handler | task_scheduler | NORMAL | ❌ |

### 安全事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `security.approval_required` | security_service | access / interrupt_handler | CRITICAL | ✅ |
| `error.security` | security_service | log_service / access | CRITICAL | ✅ |

### 插件事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `plugin.upgrade_proposed` | 任意插件 / role_learner | suri_core / upgrade_manager | HIGH | ✅ |
| `error.plugin` | suri_core | log_service / access | HIGH | ✅ |

### 定时事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `cron.{rule_id}` | cron_service | 目标角色 | NORMAL | ❌ |
| `upgrade.check_requested` | cron_service | upgrade_manager | NORMAL | ❌ |

### 文档同步事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `doc_sync.suggestion_created` | doc_sync | access | NORMAL | ✅ |
| `doc_sync.applied` | doc_sync | log_service | NORMAL | ✅ |
| `doc_sync.ignored` | doc_sync | log_service | NORMAL | ✅ |

### 测试事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `test.completed` | test_framework | log_service / 角色 | NORMAL | ❌ |
| `error.test` | test_framework | log_service / access | HIGH | ✅ |

### 升级事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `learning.report_generated` | role_learner | upgrade_manager | HIGH | ✅ |
| `upgrade.report_saved` | upgrade_manager | log_service | NORMAL | ✅ |
| `upgrade.status_changed` | upgrade_manager | log_service | NORMAL | ❌ |
| `upgrade.reports_pending` | upgrade_manager | suri 角色 | NORMAL | ❌ |
| `upgrade.implemented` | upgrade_manager | log_service | NORMAL | ✅ |

### 钩子事件

| 事件 | 发布者 | 订阅者 | 优先级 | 持久化 |
|------|--------|--------|--------|--------|
| `hooks.file_changed` | hooks_service | doc_sync / security_service | NORMAL | ❌ |
| `hooks.file_created` | hooks_service | doc_sync | NORMAL | ❌ |
| `hooks.file_deleted` | hooks_service | doc_sync | NORMAL | ❌ |
| `hooks.pre_task_dispatch` | hooks_service | log_service | NORMAL | ❌ |
| `hooks.post_task_complete` | hooks_service | log_service | NORMAL | ❌ |

---

## 事件路由规则

1. **定向路由**：`event.target` 非空时，事件仅投递给 target 指定的插件/角色，同时仍广播给所有匹配的通配订阅者
2. **通配订阅**：`system.*`、`role.*`、`task.*`、`error.*`、`cron.*` 支持通配符匹配
3. **优先级排序**：同一时刻，CRITICAL > HIGH > NORMAL > LOW，同优先级按 FIFO（EventBus 内部使用单调递增 counter 保证顺序）
4. **持久化阈值**：CRITICAL 和 HIGH 优先级事件自动持久化到 SQLite `events` 表
5. **交付语义**：at-most-once（尽力交付），失败不自动重试
6. **事件版本**：事件 schema 变更时，`event_type` 后缀版本号（如 `task.created.v2`），旧版本保留兼容 1 个主版本周期

---

## 统一错误事件基类

所有 `error.*` 事件继承以下基类 schema：

```
error.base:
  error_code    integer  是   错误码（见 framework.md 错误码规范）
  error_type    string   是   错误分类标识
  message       string   是   人类可读错误描述
  source        string   是   错误来源插件/角色
  timestamp     string   是   ISO 8601（由 Event.__post_init__ 自动生成）
  request_id    string   否   关联请求 ID（如有）
  recoverable   boolean  否   是否可恢复，默认 false

**Event 构造约束**：
- `event_type`（string）和 `source`（string）为必填字段
- `timestamp` 由 `Event.__post_init__` 自动生成，调用方无需传入
- `payload` 默认为空 dict，必须符合 JSON 可序列化格式
```

各插件可在此基础上扩展字段（如 `llm.error` 的 `retryable`、`error.tool` 的 `tool_name` 等）。