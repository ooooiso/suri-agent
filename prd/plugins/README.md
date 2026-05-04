# Suri Agent 插件目录 PRD 总览

> 本文档汇总所有插件 PRD，描述插件体系全景。
>
> **核心原则**：
> 1. 一切功能基于插件调用，无硬编码耦合
> 2. 一切任务基于角色协同，和程序无关
> 3. **所有插件概念统一，按功能分 6 层**

## 插件清单（23 个，含实现状态）

> 📗 = 代码已实现  📕 = 占位待开发  📘 = PRD 有定义代码未实现

```
23 个插件分 6 层：
├─ 内核层（1）     核心 ↪  core/
├─ 基础服务层（3）  服务 ↪  service/
├─ 执行层（6）     执行 ↪  execution/
├─ 能力层（7）     能力 ↪  capability/
├─ 接入层（1）     接入 ↪  access/（含 7 子组件）
└─ 扩展层（5）     扩展 ↪  extension/
```

### 内核层 `core/`

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| **suri_core** | `core/suri_core.md` | 内核核心。EventBus + PluginManager。自举注册 | 📗 已实现 |

### 基础服务层 `service/`

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| config_service | `service/config_service.md` | 统一配置中心 | 📗 已实现 |
| log_service | `service/log_service.md` | 分级日志、分类归档 | 📗 已实现 |
| security_service | `service/security_service.md` | 权限校验、审批流程 | 📗 已实现 |

### 执行层 `execution/`

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| task_scheduler | `execution/task_scheduler.md` | 任务优先级队列、并发控制、超时重试 | 📗 已实现 |
| task_planner | `execution/task_planner.md` | 任务分解、DAG 依赖管理、预设模板 | 📗 已实现 |
| agent_registry | `execution/agent_registry.md` | Agent 生命周期、状态跟踪、进度查询 | 📗 已实现 |
| interrupt_handler | `execution/interrupt_handler.md` | 中断分类、自动重试、用户决策 | 📗 已实现 |
| code_tool | `execution/code_tool.md` | 文件读写、搜索、统计 | 📗 已实现 |
| role_comm | `execution/role_comm.md` | 角色间通信、持久化队列 | 📘 文档就绪待开发 |

### 能力层 `capability/`

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| llm_gateway | `capability/llm_gateway.md` | 大模型统一网关 | 📗 已实现 |
| role_manager | `capability/role_manager.md` | 角色生命周期、Soul 管理 | 📗 已实现 |
| memory_service | `capability/memory_service.md` | 角色级 SQLite 记忆存储 | 📘 文档就绪待开发 |
| role_learner | `capability/role_learner.md` | 角色自学习、技能检测 | 📘 文档就绪待开发 |
| wiki_service | `capability/wiki_service.md` | ⭐ Wiki 知识库(LLM驱动) | 📘 文档就绪待开发 |
| mcp_framework | `capability/mcp_framework.md` | MCP 协议、工具注册发现 | 📘 文档就绪待开发（V2.0） |
| upgrade_manager | `capability/upgrade_manager.md` | 升级报告状态机、回滚管理 | 📘 文档就绪待开发 |

### 接入层 `access/`

| 组件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| **session-hub** | `access/session-hub.md` | ★ 会话中枢。会话管理、统一协议、事件路由、通道注册/发现、能力协商 | 📗 已实现 |
| **CLI 通道** | `access/channels/cli.md` | 终端交互通道 | 📗 已实现 |
| **Telegram 通道** | `access/channels/telegram.md` | Telegram Bot 通道 | 📗 已实现 |
| **Web 通道** | `access/channels/web.md` | Web 端交互通道 | 📕 占位待开发 |
| **桌面端通道** | `access/channels/desktop.md` | 桌面端原生通道 | 📕 占位待开发 |
| config_editor | `access/config_editor.md` | 配置编辑器 | 📗 已实现 |
| wizard | `access/wizard.md` | 引导式配置器 | 📗 已实现 |

### 扩展层 `extension/`

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| test_framework | `extension/test_framework.md` | 自动化测试框架 | 📗 已实现 |
| doc_sync | `extension/doc_sync.md` | 文档同步、代码变更监控 | 📗 已实现 |
| hooks_service | `extension/hooks_service.md` | 事件钩子、拦截扩展 | 📗 已实现 |
| cron_service | `extension/cron_service.md` | 定时触发事件 | 📘 文档就绪待开发 |
| monitor | `extension/monitor.md` | ⭐ 系统监控与运维 | 📘 文档就绪待开发 |


## 架构原则

### 1. 程序无关 — 框架不执行业务

```
用户输入
    │
    ▼
┌─────────────┐     ┌─────────────────────────────┐
│   access    │────▶│   event_bus（suri_core）    │
│  （接入）    │     │   内核插件，只做路由         │
└─────────────┘     └─────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
          ┌─────────┐     ┌─────────┐     ┌─────────┐
          │  suri   │     │ 角色 A  │     │ 角色 B  │
          │（调度）  │     │(Agent)  │     │(Agent)  │
          └────┬────┘     └────┬────┘     └────┬────┘
               │               │               │
               ▼               ▼               ▼
          调用插件能力      调用插件能力       调用插件能力
```

**框架（程序）只提供**：
- 事件总线（消息投递）
- 插件生命周期管理
- 配置/日志/安全等基础服务

**suri 角色负责**：
- 调度 — 将任务分配给合适的角色
- 角色管理 — 创建/删除角色
- 系统维护 — 管理插件和配置
- 升级自身 — 申请增加新技能

**普通角色（Agent）负责**：
- 接收任务
- 分析需求
- 调用插件能力执行
- 自学、自增技能
- 与其他角色协作

### 2. 插件被动 — 能力提供者，不主动决策

| 插件 | 正确行为 | 禁止行为 |
|------|---------|---------|
| llm_gateway | 接收 `llm.request` 事件，返回模型响应 | 主动决定何时调用模型 |
| memory_service | 接收读写请求，操作 SQLite | 主动分析记忆内容 |
| mcp_framework | 接收 `tool.call` 事件，执行工具 | 主动决定调用哪个工具 |
| role_learner | 被事件触发，分析该角色记忆 | 主动扫描所有角色记忆 |
| cron_service | 按时触发 `cron.*` 事件 | 定义事件内容或执行任务 |
| task_scheduler | 接收调度请求，按优先级执行 | 主动决定任务优先级 |
| task_planner | 被调用时生成任务规划 | 主动分解未请求的任务 |
| agent_registry | 响应 CRUD 和状态查询 | 主动创建或销毁 Agent |
| role_comm | 接收消息，存储并投递 | 主动发送消息 |

---

## 插件自修改流程（所有插件统一）

**任何插件（包括 suri_core）运行时修改自身代码，必须走以下流程**：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  1. 自分析   │────▶│ 2. 生成方案  │────▶│ 3. suri呈现 │
│ (PluginSelf │     │ (变更原因/   │     │ (向用户说明  │
│  Learning)  │     │  策略/回滚)  │     │  升级理由)   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                          用户确认
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 7. 生效     │◀────│ 6. 验证     │◀────│ 5. 执行变更 │
│ (热更新/    │     │ (健康检查/  │     │ (IDE 模式/  │
│  重启)      │     │  冒烟测试)  │     │  代码补丁)   │
└─────────────┘     └─────────────┘     └─────────────┘
```

**关键规则**：
1. **无插件可私自修改代码** — 所有代码变更必须经过用户确认
2. **suri_core 升级特殊约束** — 变更后必须通过冒烟测试（EventBus + PluginManager 基础功能验证）
3. **热更新限制** — 涉及 EventBus 核心逻辑的变更可能需要重启，不能纯热更新
4. **回滚保障** — 所有升级方案必须包含回滚策略

---

## 插件依赖图

```
suri_core（内核插件，自举注册）
├── config_service
│   └── 所有需要配置的插件
├── log_service
│   └── 所有需要日志的插件
├── security_service
│   ├── mcp_framework
│   ├── role_manager
│   └── doc_sync（如启用审批）
├── task_scheduler
│   ├── llm_gateway（等待 LLM 响应）
│   ├── agent_registry（更新 Agent 状态）
│   └── task_planner（获取任务规划）
├── task_planner
│   ├── llm_gateway（LLM 辅助规划）
│   └── role_manager（获取角色信息）
├── agent_registry
│   ├── memory_service（持久化 Agent 状态）
│   └── task_scheduler（调度执行）
├── role_comm
│   └── 所有角色（消息消费者）
├── interrupt_handler
│   ├── role_comm（发送升级消息）
│   └── agent_registry（获取 Agent 状态）
├── memory_service
│   ├── role_manager
│   ├── security_service
│   ├── role_learner
│   └── agent_registry
├── llm_gateway
│   ├── role_learner
│   ├── task_planner
│   ├── task_scheduler
│   └── doc_sync
├── role_manager
│   └── access（用户创建角色）
├── role_learner
│   ├── memory_service（读取记忆）
│   ├── role_manager（技能建议）
│   └── upgrade_manager（报告保存）
├── mcp_framework
│   ├── filesystem（内置服务）
│   ├── shell_exec（内置服务）
│   └── web_search（内置服务）
├── upgrade_manager
│   └── suri 角色（汇总决策）
├── hooks_service
│   ├── security_service
│   └── doc_sync（文件变更钩子）
├── cron_service
│   └── 无（事件由角色订阅）
├── access
│   └── 所有角色（消息接收）
├── test_framework
│   └── 所有插件（单元/集成/插件测试）
├── doc_sync
│   ├── hooks_service（文件变更钩子）
│   └── llm_gateway（生成文档建议）
└── code_tool
    ├── security_service（沙箱权限检查）
    └── 所有角色（文件读写操作）
```

---

## 事件总线标准事件

| 事件类型 | 发布者 | 消费者 | 说明 |
|----------|--------|--------|------|
| `system.started` | suri_core | 所有插件 | 系统启动完成 |
| `system.shutdown` | suri_core / access | 所有插件 | 系统关闭信号 |
| `system.config_changed` | config_service | 各插件 | 配置变更 |
| `user.input` | access | suri（或其他角色） | 用户普通消息 |
| `user.command` | access | 各插件 | 用户命令 |
| `llm.request` | 角色 / task_scheduler | llm_gateway | LLM 调用请求 |
| `llm.response` | llm_gateway | 角色 / task_scheduler | LLM 响应 |
| `llm.error` | llm_gateway | 角色 | LLM 调用失败 |
| `tool.call` | 角色 | code_tool / mcp_framework | 工具调用请求 |
| `tool.result` | code_tool / mcp_framework | 角色 | 工具返回结果 |
| `error.tool` | code_tool / mcp_framework | 角色 / log_service | 工具调用失败 |
| `task.created` | 角色 | log_service / task_scheduler | 任务创建 |
| `task.planned` | task_planner | task_scheduler / 角色 | 任务规划完成 |
| `task.step_ready` | task_planner | task_scheduler | 步骤可执行 |
| `task.started` | task_scheduler | log_service / 角色 | 任务开始执行 |
| `task.completed` | task_scheduler / 角色 | log_service / role_learner | 任务完成 |
| `task.failed` | task_scheduler / 角色 | log_service / interrupt_handler | 任务失败 |
| `task.timeout` | task_scheduler | log_service / interrupt_handler | 任务超时 |
| `task.cancelled` | task_scheduler | log_service / 角色 | 任务被取消 |
| `agent.created` | agent_registry | log_service / 角色 | Agent 创建完成 |
| `agent.status_changed` | agent_registry | log_service / task_scheduler | Agent 状态变更 |
| `agent.completed` | agent_registry | log_service / role_learner | Agent 完成 |
| `agent.blocked` | agent_registry | log_service / interrupt_handler | Agent 受阻 |
| `role.context_ready` | role_manager | suri 角色 | 上下文就绪，可开始处理 |
| `role.message` | 角色（发送方） | role_comm | 角色发送消息（输入事件） |
| `role.message_received` | role_comm | 目标角色 | 角色收到新消息通知 |
| `role.messages_batch` | role_comm | 目标角色 | 批量消息投递 |
| `role.messages_query` | 角色 | role_comm | 查询未读消息/历史 |
| `role.messages_consume` | 角色 | role_comm | 消费消息（标记已读） |
| `role.message_delivered` | role_comm | 发送方角色 | 消息投递成功 |
| `role.skill_suggested` | role_learner | role_manager | 技能建议 |
| `cron.{rule_id}` | cron_service | 角色 | 定时事件 |
| `interrupt.handled` | interrupt_handler | log_service / 角色 | 中断已处理 |
| `interrupt.escalated` | interrupt_handler | role_comm / 目标角色 | 中断已升级 |
| `interrupt.user_decision_needed` | interrupt_handler | access | 需要用户决策 |
| `error.*` | 任意插件 | log_service | 错误事件 |
| `error.system` | suri_core | log_service / access | 系统级错误 |
| `error.security` | security_service | log_service / access | 安全相关错误 |
| `error.plugin` | suri_core | log_service / access | 插件错误 |
| `error.test` | test_framework | log_service / access | 测试错误 |
| `test.completed` | test_framework | log_service | 测试完成 |
| `upgrade.report_saved` | upgrade_manager | log_service | 报告已保存 |
| `upgrade.reports_pending` | upgrade_manager | suri 角色 | 有待处理报告 |
| `upgrade.implemented` | upgrade_manager | log_service | 升级已实施 |
| `upgrade.rollback_completed` | upgrade_manager | log_service / suri 角色 | 回滚完成 |
| `doc_sync.suggestion_created` | doc_sync | access / suri 角色 | 文档更新建议 |
| `doc_sync.applied` | doc_sync | log_service | 文档更新已应用 |
| `doc_sync.ignored` | doc_sync | log_service | 文档更新已忽略 |
| `hooks.file_changed` | hooks_service | doc_sync / security_service | 文件变更 |
| `hooks.file_created` | hooks_service | doc_sync | 文件创建 |
| `hooks.file_deleted` | hooks_service | doc_sync | 文件删除 |
| `security.approval_required` | security_service | access / interrupt_handler | 审批请求 |
| `monitor.alert` | monitor | access / log_service | 监控告警 |
| `plugin.upgrade_proposed` | 任意插件 | suri_core / upgrade_manager | 插件升级提议 |
| `role_manager.templates_updated` | role_manager | 相关方 | 模板已更新 |

---

## 六、每层插件暴露了什么（可扫码表）

> 以下汇总每层所有插件在 manifest.json 中声明的暴露能力。事件 = 发布的事件类型，工具 = 暴露的 MCP 工具，命令 = CLI 命令。

### 内核层

| 插件 | 暴露事件 | 暴露工具 | 命令 |
|------|---------|---------|------|
| **suri_core** | `system.started`, `system.shutdown` | 无 | 无 |

### 基础服务层

| 插件 | 暴露事件 | 暴露工具 | 命令 |
|------|---------|---------|------|
| **config_service** | `system.config_changed` | 配置读写 | 无 |
| **log_service** | 无（纯服务插件） | 日志查询、日志归档 | 无 |
| **security_service** | 无 | 权限校验、代码扫描 | 无 |

### 执行层

| 插件 | 暴露事件 | 暴露工具 | 命令 |
|------|---------|---------|------|
| **task_scheduler** | `task.queued`, `task.started`, `task.completed`, `task.failed`, `task.timeout`, `task.cancelled` | 任务调度 | 无 |
| **task_planner** | `task.planned`, `task.plan_updated` | 任务分解、依赖管理 | 无 |
| **agent_registry** | `agent.created`, `agent.status_changed`, `agent.completed`, `agent.blocked` | Agent CRUD、状态查询 | 无 |
| **interrupt_handler** | `interrupt.handled`, `interrupt.escalated` | 中断处理 | 无 |
| **role_comm** | `role.message_received`, `role.message_delivered`, `role.message_rejected` | 消息发送/广播/查询 | 无 |
| **code_tool** | `tool.result`, `error.tool` | `code_tool.read`, `code_tool.write`, `code_tool.search`, `code_tool.stats`, `code_tool.patch`, `code_tool.explorer` | 无 |

### 能力层

| 插件 | 暴露事件 | 暴露工具 | 命令 |
|------|---------|---------|------|
| **llm_gateway** | `llm.response`, `llm.error` | LLM 请求（流式/非流式）、模型状态查询 | `switch`（切换模型） |
| **memory_service** | 无（纯服务插件） | 记忆存储、记忆检索（RAG）、Insight 管理 | 无 |
| **role_manager** | `role.created`, `role.destroyed`, `role.skill_invoked` | 角色 CRUD、Soul 解析、session 管理 | `create_role`, `role.list` |
| **role_learner** | `role.skill_suggested`, `learning.report_generated` | 角色学习、技能检测 | `/learn role` |
| **mcp_framework** | `tool.result`, `error.tool` | MCP 工具路由、工具注册/发现 | 无 |
| **upgrade_manager** | `upgrade.report_saved`, `upgrade.reports_pending` | 升级报告管理 | 无 |
| **wiki_service** | 无 | 知识库检索、知识库更新 | 无 |

### 接入层

| 组件 | 暴露事件 | 暴露工具 | 命令 |
|------|---------|---------|------|
| **session-hub** | `user.input`, `user.command`, `user.attachment`, `session.created`, `session.expired`, `channel.registered` | 会话管理 | 会话命令 |
| **CLI 通道** | `channel.message`, `channel.connected` | 无 | `/exit`, `/help`, `/clear` |
| **Telegram 通道** | `channel.message`, `channel.connected`, `channel.command` | 无 | `/start`, `/help` |
| **Web 通道** | `channel.message`, `channel.connected` | 无 | 无 |
| **桌面端通道** | 无（占位） | 无 | 无 |

### 扩展层

| 插件 | 暴露事件 | 暴露工具 | 命令 |
|------|---------|---------|------|
| **test_framework** | `test.completed` | 测试执行 | 无 |
| **cron_service** | `cron.*`（定时触发） | 定时任务管理 | 无 |
| **hooks_service** | `file.changed`, `file.created`, `file.deleted` | 钩子管理 | 无 |
| **doc_sync** | `doc_sync.suggestion_created` | 文档同步 | 无 |
| **monitor** | 无 | 系统监控、指标查询 | 无 |

### 插件进化声明（manifest.json 扩展）

每个插件 manifest.json 中新增 `notify_on_change` 字段，声明其他维度的变更通知目标：

```json
{
  "name": "task_planner",
  "version": "1.2.0",
  "exposes": {
    "events": ["task.planned", "task.plan_updated"],
    "tools": ["task_planner.decompose", "task_planner.template_match"],
    "commands": [],
    "apis": {}
  },
  "notify_on_change": [
    "skill:role_type:worker",     // worker 型角色的技能变更时通知
    "soul:role_type:worker",      // worker 型角色的 Soul 变更时通知
    "tool:code_tool"              // code_tool 插件暴露的工具变更时通知
  ]
}
```

**notify_on_change 规则**：
- `skill:role_type:{type}` — 某类型角色的技能变更时通知
- `skill:role_id:{id}` — 特定角色的技能变更时通知
- `soul:role_type:{type}` — 某类型角色的 Soul 变更时通知
- `soul:role_id:{id}` — 特定角色的 Soul 变更时通知
- `tool:{plugin_name}` — 某插件的工具变更时通知
- `plugin:{plugin_name}` — 某插件的进化（新增/更新/废弃工具、事件）时通知
- `all` — 所有变更都通知

---

## 七、开发规范

1. **所有插件必须实现 PluginInterface**
2. **所有插件通过事件总线通信，禁止直接方法调用**
3. **每个插件 PRD 需包含：定位、功能需求、接口定义、配置项、依赖关系、生命周期、安全边界**
4. **插件加载前必须经过 AST 安全扫描**
5. **新增插件需按功能分类放入对应子目录，并同步更新本 README 和 [`prd/README.md`](../README.md)**
6. **插件不主动决策，只响应事件或响应角色调用**
7. **所有插件代码自修改必须走统一流程：分析→方案→suri呈现→用户确认→验证→生效**

---

## 框架共享模块（非独立插件）

以下能力作为共享模块/基类存在，由插件内部调用，不表现为独立插件：

| 模块 | 使用者 | 说明 |
|------|--------|------|
| **PluginSelfLearning** | 各插件（可选集成） | 插件自学习基类。启发式统计 + LLM 深度分析，生成模块级升级建议 |
| **EventBusFixture** | test_framework | 事件总线 mock，供测试使用 |
| **PluginTestHarness** | test_framework | 插件生命周期 mock，供测试使用 |
| **AgentContext** | agent_registry | Agent 独立上下文管理，消息隔离 |
| **TaskStep** | task_planner / agent_registry | 任务步骤数据模型，含依赖关系 |
| **TemplateUpdater** | template_updater | 模板自动更新服务，监听事件维护 YAML 文件 |