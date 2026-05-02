# Suri Agent 插件目录 PRD 总览

> 本文档汇总所有插件 PRD，描述插件体系全景。
>
> **核心原则**：
> 1. 一切功能基于插件调用，无硬编码耦合
> 2. 一切任务基于角色协同，和程序无关
> 3. **所有插件（包括 suri_core）概念统一，无特殊分类**

## 插件清单（20 个）

### 内核层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| **suri_core** | `suri_core.md` | **内核插件**。EventBus（含分发）+ PluginManager。启动时自举注册 | 核心 |

### 基础服务层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| config_service | `config_service.md` | 统一配置中心 | 核心 |
| log_service | `log_service.md` | 分级日志、分类归档 | 核心 |
| security_service | `security_service.md` | 权限校验、审批流程 | 核心 |

### 执行层（新增）

| 插件 | 文件 | 职责 | 优先级 |
|------|------|------|--------|
| **task_scheduler** | `task_scheduler.md` | 任务优先级队列、并发控制、超时重试、LLM 响应等待 | **P0** |
| **task_planner** | `task_planner.md` | 任务分解、DAG 依赖管理、预设模板、LLM 辅助规划 | **P0** |
| **agent_registry** | `agent_registry.md` | Agent 生命周期、子 Agent、状态跟踪、进度查询、父子关系 | **P0** |
| **role_comm** | `role_comm.md` | 角色间点对点/广播消息、权限规则、持久化队列、留存策略 | **P0** |
| **interrupt_handler** | `interrupt_handler.md` | 受阻原因分类、用户建议生成、升级通道 | **P1** |

### 能力层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| llm_gateway | `llm_gateway.md` | 大模型统一网关 | 必备 |
| memory_service | `memory_service.md` | 角色级 SQLite 记忆存储 | 必备 |
| role_manager | `role_manager.md` | 角色生命周期、Soul 管理 | 必备 |
| role_learner | `role_learner.md` | 角色自学习 + ProgramLearner 全局分析 | 成长 |
| mcp_framework | `mcp_framework.md` | MCP 协议 + 工具注册中心 + 内置服务 | 必备 |
| upgrade_manager | `upgrade_manager.md` | 升级报告状态机、闭环检查、Finding/UpgradeReport 模型 | **P1** |

### 接入层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| access | `access.md` | 统一接入（CLI/Web/Telegram/Lark/API） | 默认启用 |

### 扩展层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| cron_service | `cron_service.md` | 定时触发事件（只触发，不执行） | 运维 |
| hooks_service | `hooks_service.md` | 事件钩子、拦截扩展 | 扩展 |
| test_framework | `test_framework.md` | 自动化测试框架 | 质量 |
| doc_sync | `doc_sync.md` | 文件变更监控、LLM 生成文档更新建议、用户确认写入 | **P2** |

### 工具层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| code_tool | `code_tool.md` | 安全文件读写、代码搜索、测试执行 | **P1** |

---

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
          │  suri   │     │suri_dev │     │suri_hr  │
          │（调度）  │     │（开发）  │     │（人事）  │
          └────┬────┘     └────┬────┘     └────┬────┘
               │               │               │
               ▼               ▼               ▼
          调用插件能力     调用插件能力     调用插件能力
          llm_gateway     mcp_framework   role_manager
          memory_service  security_service
          task_scheduler  task_planner    agent_registry
          role_comm       interrupt_handler
```

**框架（程序）只提供**：
- 事件总线（消息投递）
- 插件生命周期管理
- 配置/日志/安全等基础服务

**角色负责**：
- 接收用户输入
- 分析需求
- 调用插件能力（包括执行层插件）
- 分派子任务给其他角色
- 汇总结果返回用户

**项目组模式（复杂项目）**：
- suri 只在项目组创建和缺少角色时介入
- 项目总监（项目附带角色）负责项目群内日常调度
- 用户直接在项目 Telegram 群 @项目总监 或 @实现角色 交互
- 项目总监调用 task_planner / task_scheduler / agent_registry 完成调度

### 2. 插件被动 — 能力提供者，不主动决策

| 插件 | 正确行为 | 禁止行为 |
|------|---------|---------|
| llm_gateway | 接收 `llm.request` 事件，返回模型响应 | 主动决定何时调用模型 |
| memory_service | 接收读写请求，操作 SQLite | 主动分析记忆内容 |
| mcp_framework | 接收 `tool.call` 事件，执行工具 | 主动决定调用哪个工具 |
| role_learner | 被角色调用，分析该角色记忆 | 主动扫描所有角色记忆 |
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
| `system.start` | suri_core | 所有插件 | 系统启动完成 |
| `system.shutdown` | suri_core / access | 所有插件 | 系统关闭信号 |
| `system.config_changed` | config_service | 各插件 | 配置变更 |
| `user.input` | access | suri（或其他角色） | 用户普通消息 |
| `user.command` | access | 各插件 | 用户命令 |
| `llm.request` | 角色 / task_scheduler | llm_gateway | LLM 调用请求 |
| `llm.response` | llm_gateway | 角色 / task_scheduler | LLM 响应 |
| `llm.error` | llm_gateway | 角色 | LLM 调用失败 |
| `tool.call` | 角色 | mcp_framework | 工具调用请求 |
| `tool.result` | mcp_framework | 角色 | 工具返回结果 |
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
| `role.message_received` | role_comm | receiver 角色 | 新消息到达 |
| `role.skill_suggested` | role_learner | role_manager | 技能建议 |
| `cron.{rule_id}` | cron_service | 角色 | 定时事件（由角色处理） |
| `error.*` | 任意插件 | log_service | 错误事件 |
| `test.completed` | test_framework | log_service | 测试完成 |
| `plugin.upgrade_proposed` | 任意插件 | suri_core / suri 角色 | 插件升级方案 |
| `upgrade.report_saved` | upgrade_manager | log_service | 报告已保存 |
| `upgrade.reports_pending` | upgrade_manager | suri 角色 | 有待处理报告 |
| `interrupt.escalated` | interrupt_handler | role_comm / 目标角色 | 中断已升级 |
| `doc_sync.suggestion_created` | doc_sync | access / suri 角色 | 文档更新建议 |

**注意**：所有 `task.*`、`llm.*`、`tool.*`、`agent.*` 事件的发布者和消费者都是**角色或插件能力层**，suri_core 作为框架不发布也不消费这些业务事件。

---

## 开发规范

1. **所有插件必须实现 PluginInterface**
2. **所有插件通过事件总线通信，禁止直接方法调用**
3. **每个插件 PRD 需包含：定位、功能需求、接口定义、配置项、依赖关系、生命周期、安全边界**
4. **插件加载前必须经过 AST 安全扫描**
5. **新增插件需同步更新本 README 和 [`prd/README.md`](../README.md)**
6. **插件不主动决策，只响应事件或响应角色调用**
7. **suri_core 不发布业务事件（task/llm/tool/agent），只发布 system/error 事件**
8. **所有插件代码自修改必须走统一流程：分析→方案→suri呈现→用户确认→验证→生效**

---

## 框架共享模块（非独立插件）

以下能力作为共享模块/基类存在，由插件内部调用，不表现为独立插件：

| 模块 | 使用者 | 说明 |
|------|--------|------|
| **PluginSelfLearning** | 各插件（可选集成） | 插件自学习基类。启发式统计 + LLM 深度分析，生成模块级升级建议（Finding/UpgradeReport）。 |
| **EventBusFixture** | test_framework | 事件总线 mock，供测试使用 |
| **PluginTestHarness** | test_framework | 插件生命周期 mock，供测试使用 |
| **AgentContext** | agent_registry | Agent 独立上下文管理，消息隔离 |
| **TaskStep** | task_planner / agent_registry | 任务步骤数据模型，含依赖关系 |
