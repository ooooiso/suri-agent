# 架构全景

> 描述 suri-agent 的整体架构、插件全景、联动关系、角色与插件的关系。

---

## 一、架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                        接入层 (Access Layer)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  CLI     │  │ Telegram │  │ WebSocket│  │  未来通道 (API)  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
└───────┼──────────────┼──────────────┼──────────────────┼──────────┘
        │              │              │                  │
┌───────▼──────────────▼──────────────▼──────────────────▼──────────┐
│                      事件总线 (EventBus)                            │
│              异步发布/订阅，支持通配符，CRITICAL 持久化              │
└──┬──────────┬──────────┬──────────┬──────────┬────────────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────────┐
│suri  │ │role  │ │task  │ │agent │ │interrupt │ │task      │
│core  │ │mgr   │ │plan  │ │reg   │ │handler   │ │scheduler │
└──────┘ └──────┘ └──────┘ └──────┘ └──────────┘ └──────────┘
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ ┌──────────┐
│llm   │ │code  │ │config│ │security│ │role_comm │ │role      │
│gate  │ │tool  │ │svc   │ │service │ │          │ │learner   │
└──────┘ └──────┘ └──────┘ └──────┘ └──────────┘ └──────────┘
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│log   │ │test  │ │doc   │ │upgr  │ │hooks     │
│svc   │ │frame │ │sync  │ │mgr   │ │service   │
└──────┘ └──────┘ └──────┘ └──────┘ └──────────┘
```

## 二、插件全景（21 个）

### 2.1 内核层（1 个）

| 插件 | 目录 | 职责 | 状态 |
|------|------|------|------|
| **suri_core** | `agent_framework/suri_core_plugin/` | 内核插件，自举注册，协调 EventBus 和 PluginManager | 🏗️ 骨架 |

### 2.2 基础服务层（3 个）

| 插件 | 目录 | 职责 | 状态 |
|------|------|------|------|
| **config_service** | `plugins/config_service/` | 配置管理，持久化，热加载 | ✅ 已实现 |
| **log_service** | `plugins/log_service/` | 日志记录，归档，查询 | ✅ 已实现 |
| **security_service** | `plugins/security_service/` | 权限校验，操作审计，代码扫描 | ✅ 已实现 |

### 2.3 执行层（5 个）

| 插件 | 目录 | 职责 | 状态 |
|------|------|------|------|
| **task_planner** | `plugins/task_planner/` | 任务分解，模板匹配，LLM 辅助规划 | ✅ 已实现 |
| **task_scheduler** | `plugins/task_scheduler/` | 任务调度，步骤分发，并发控制，超时重试 | 🏗️ 骨架 |
| **agent_registry** | `plugins/agent_registry/` | Agent 生命周期管理，状态跟踪，进度查询 | ✅ 已实现 |
| **interrupt_handler** | `plugins/interrupt_handler/` | 中断分类，自动重试，用户决策 | ✅ 已实现 |
| **role_comm** | `plugins/role_comm/` | 角色间点对点/广播消息，持久化队列 | 📋 规划中 |

### 2.4 能力层（6 个）

| 插件 | 目录 | 职责 | 状态 |
|------|------|------|------|
| **role_manager** | `plugins/role_manager/` | 角色 CRUD，Soul 解析，能力索引，会话上下文 | ✅ 已实现 |
| **role_learner** | `plugins/role_learner/` | 角色自学习，经验提取，技能检测，全局分析 | 📋 规划中 |
| **llm_gateway** | `plugins/llm_gateway/` | LLM 厂商路由，模型切换，流式响应 | ✅ 已实现 |
| **code_tool** | `plugins/code_tool/` | 文件读写，搜索，统计，RuleProvider | ✅ 已实现 |
| **doc_sync** | `plugins/doc_sync/` | 文档同步，代码变更监控 | 📋 规划中 |
| **upgrade_manager** | `plugins/upgrade_manager/` | 升级报告状态机，备份回滚，闭环验证 | 📋 规划中 |

### 2.5 接入层（1 个）

| 插件 | 目录 | 职责 | 状态 |
|------|------|------|------|
| **access** | `plugins/access/` | 多通道接入（CLI/Telegram），消息路由，命令解析 | ✅ 已实现 |

### 2.6 扩展层（4 个）

| 插件 | 目录 | 职责 | 状态 |
|------|------|------|------|
| **test_framework** | `plugins/test_framework/` | 测试基础设施（EventBusFixture, TestBase, PluginTestHarness） | ✅ 已实现 |
| **hooks_service** | `plugins/hooks_service/` | 文件变更钩子，事件拦截 | 📋 规划中 |
| **cron_service** | `plugins/cron_service/` | 定时任务调度 | 📋 规划中 |
| **mcp_framework** | `plugins/mcp_framework/` | MCP 协议支持，工具注册发现 | 📋 规划中 |

### 2.7 工具层（1 个）

| 插件 | 目录 | 职责 | 状态 |
|------|------|------|------|
| **code_tool** | `plugins/code_tool/` | 文件操作工具集（与能力层共用） | ✅ 已实现 |

---

## 三、插件联动关系

### 3.1 核心事件流

```
用户输入
    │
    ▼
access ──► role_manager ──► llm_gateway ──► code_tool
  │            │                │               │
  │            ▼                ▼               │
  │      会话上下文管理     模型切换/流式       文件操作
  │            │                │               │
  ▼            ▼                ▼               ▼
┌─────────────────────────────────────────────────────┐
│                    EventBus                          │
└──┬──────────┬──────────┬──────────┬──────────┬───────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
task_planner  agent_registry  interrupt_handler  task_scheduler
```

### 3.2 事件流详情

```
1. user.input ──────────► access (接收消息)
2. message.routed ──────► role_manager (解析角色，构建 system prompt)
3. llm.request ─────────► llm_gateway (请求 LLM)
4. llm.response ────────► access (返回给用户)
   llm.error ───────────► interrupt_handler (处理错误)

5. task.plan_requested ─► task_planner (分解任务)
6. task.planned ────────► agent_registry (创建 Agent)
7. agent.created ───────► task_scheduler (调度步骤)
8. step.assigned ───────► role_manager (分配执行)
9. step.completed ──────► agent_registry (更新进度)
10. agent.blocked ──────► interrupt_handler (中断处理)
11. interrupt.handled ──► task_scheduler (重试/取消)
```

### 3.3 插件间依赖矩阵

| 插件 | 依赖 | 被依赖 |
|------|------|--------|
| access | role_manager, llm_gateway, config_service | — |
| role_manager | config_service, security_service | access, task_scheduler, task_planner |
| llm_gateway | config_service | access, task_planner, role_manager |
| code_tool | security_service | task_scheduler, role_manager |
| config_service | — | 所有插件 |
| security_service | config_service | code_tool, access, role_manager |
| log_service | — | 所有插件（被动订阅） |
| task_planner | llm_gateway, role_manager | task_scheduler |
| agent_registry | config_service | task_scheduler, interrupt_handler |
| task_scheduler | task_planner, agent_registry | — |
| interrupt_handler | agent_registry | task_scheduler |
| test_framework | — | 所有测试 |
| role_comm | config_service | task_scheduler, interrupt_handler |
| role_learner | llm_gateway, role_manager | upgrade_manager |
| doc_sync | hooks_service, llm_gateway | — |
| upgrade_manager | role_learner, code_tool, test_framework | — |
| hooks_service | — | doc_sync, role_learner |
| cron_service | task_scheduler | — |
| mcp_framework | config_service | code_tool |

### 3.4 角色与插件关系

```
suri（超级角色，role_type=core）
  ├── 直接调用: access, role_manager, llm_gateway, code_tool
  ├── 通过事件: task_planner, agent_registry, task_scheduler
  └── 被通知: interrupt_handler（受阻时升级到 suri）

worker 角色（role_type=worker）
  ├── 通过 role_manager 注册
  ├── 通过 task_scheduler 分配任务
  ├── 通过 llm_gateway 获取 AI 能力
  └── 通过 code_tool 执行文件操作

admin 角色（role_type=admin）
  ├── 管理角色: role_manager
  ├── 管理配置: config_service
  └── 管理安全: security_service

project_director 角色（role_type=project_director）
  ├── 项目创建: role_manager
  ├── 任务分解: task_planner
  ├── 任务调度: task_scheduler
  ├── 角色通信: role_comm
  └── 进度播报: access
```

---

## 四、数据流全景

### 4.1 用户请求处理流

```
用户输入 "帮我写一个 Python 脚本"
    │
    ▼
access.CLI ──► user.input 事件
    │
    ▼
role_manager._on_user_input()
    ├── 读取 suri/soul.md
    ├── 构建 system prompt（含工具调用说明）
    ├── 追加会话历史
    └── 发布 llm.request
    │
    ▼
llm_gateway 调用模型
    ├── 返回文本响应 → llm.response → access 显示
    └── 返回工具调用 → role_manager 解析 → 执行工具
```

### 4.2 任务执行流

```
用户输入 "分析项目代码结构"
    │
    ▼
role_manager → llm.request → LLM 返回规划请求
    │
    ▼
task_planner.plan()
    ├── 规则匹配 → 模板转换
    ├── LLM 规划 → JSON 解析
    └── 降级 generic_plan
    │
    ▼
task.planned 事件
    │
    ▼
agent_registry.create_agent()
    ├── 生成 agent_id
    ├── 创建步骤列表
    └── 发布 agent.created
    │
    ▼
task_scheduler 调度步骤
    ├── 按依赖顺序分发
    ├── 每个步骤 → role_manager 分配角色
    └── 步骤完成 → agent_registry 更新进度
```

### 4.3 中断处理流

```
Agent 执行受阻
    │
    ▼
agent.blocked 事件
    │
    ▼
interrupt_handler.handle()
    ├── _classify_reason() → 分类
    ├── 判断自动重试
    │   ├── 是 → 发布 retry_requested
    │   └── 否 → 发布 user_decision_needed
    └── 用户决策
        ├── continue → 重试
        ├── escalate → 升级到 suri
        └── cancel → 取消任务
```

### 4.4 自我进化流

```
定时/手动触发
    │
    ▼
role_learner.ProgramLearner 全局分析
    ├── 读取事件日志
    ├── 分析性能瓶颈
    └── 生成 Finding 列表
    │
    ▼
upgrade_manager.create_report()
    ├── 状态机: PENDING → PRESENTED
    └── 向用户呈现升级方案
    │
    ▼
用户确认 → APPROVED
    │
    ▼
upgrade_manager.implement()
    ├── 备份代码
    ├── code_tool 应用变更
    ├── test_framework 验证
    ├── 成功 → IMPLEMENTED
    └── 失败 → ROLLED_BACK
```

---

## 五、热更新机制

详见 `prd/hot_reload_rules.md`。

核心原则：
1. **所有硬编码数据必须外部化** — Soul 模板、工具说明、任务模板、关键词等
2. **配置热更新通过事件驱动** — config_service 发布 `config.updated` 事件
3. **插件版本协商** — manifest.json 声明兼容版本，启动时校验
4. **运行时自修改** — 通过 upgrade_manager 统一管理，禁止插件私自改代码

---

## 六、解耦设计原则

详见 `prd/decoupling_principles.md`。

核心原则：
1. **插件间仅通过 EventBus 通信** — 禁止直接调用其他插件的方法
2. **数据与逻辑分离** — 配置/模板/关键词等数据外部化，逻辑只处理数据
3. **每个插件可独立迭代** — 通过 manifest.json 版本声明 + 事件契约保证兼容
4. **迭代通知机制** — 插件升级后发布 `plugin.upgraded` 事件，框架自动协调
