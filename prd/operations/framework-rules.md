# 框架核心规则

> 定义 suri-agent 的核心架构原则、存储设计、启动流程、插件体系和四维协同进化规则。

---

## 一、核心架构原则

### 原则 1：suri 是主人 Agent（第一性智能体）

```
suri 的职责范围：
  ✅ 按自己的 Soul 处理用户需求
  ✅ 自我升级：开发插件、增加技能、开发 MCP 工具
  ✅ 学习成长：通过 role_learner 持续进化
  ✅ 调度角色：当需要专职 Agent 时创建/委派
  ✅ 帮助角色：为角色开发工具库、更新 Soul、评估技能
  ✅ 维护系统：管理插件、维护代码、处理异常
  
  ❌ 不做超出自己 Soul 范围的事（会主动请求扩展）
  ❌ 不替角色完成其专职职责范围内的工作
```

### 原则 2：多 Agent 智能体架构

```
每个角色 = 一个独立的 Agent（智能体）
  ├── 独立的 Soul — 自我定义、职责、能力边界
  ├── 独立的技能 — 通过技能调用系统能力
  ├── 独立的记忆 — 经验积累、模式识别、偏好学习
  ├── 独立的学习能力 — 可自学、自增技能
  ├── 独立的工具调用 — 可调用 MCP 工具、打通链路
  └── 独立的通信能力 — 通过 role_comm 协作
```

- 角色 = 智能体 = 有独立 Soul、技能、记忆的实体
- 角色通过自己的技能完成任务
- 角色可以自己新增技能、调用 MCP 工具、打通链路
- suri 也是角色，只是有特殊权限和更广的能力边界

### 原则 3：插件是被动能力提供者，但也是 Agent

```
插件不主动决策
  ├── 只响应事件或角色调用
  └── 通过 manifest.json 声明暴露的能力
但每个插件也是 Agent
  ├── 可以分析自身性能数据
  ├── 可以学习、更新自己的插件能力
  └── 通过 role_learner 分析 → suri 评估 → 用户确认 → 自修改
```

### 原则 4：四维协同进化

Skill / Soul / Plugin / Tool 四个维度可独立进化，变更后通过事件总线广播通知相关方。

详见 [evolution/coevolution.md](../evolution/coevolution.md)。

```
核心协同规则：
1. 每个维度独立进化，不阻塞其他维度
2. 变更后必须广播事件（EventBus）
3. 接收方自主决策响应方式
4. 运行时 context 切换有策略（默认继续旧 Context）
5. system prompt 在 llm.request 前刷新
6. 能力索引增量重建
7. 所有变更须用户确认
8. 版本可追溯可回滚
```

### 原则 5：所有代码自修改须用户确认

```
自修改流程：
  1. 自分析 → 2. 生成方案 → 3. suri 呈现
  → 4. 用户确认 → 5. 执行变更 → 6. 验证 → 7. 生效

关键约束：
  - 无插件可私自修改代码
  - 所有升级方案必须包含回滚策略
  - suri_core 涉及核心逻辑的变更需重启
```

### 原则 6：用户请求处理流程

```
用户请求
    │
    ▼
suri 接收并分析
    │
    ├── 我能直接处理吗？
    │   ├── 能 → 调用自己的技能处理
    │   └── 不能 →
    │       │
    │       ▼
    │   检查现有角色是否有匹配能力
    │       ├── 有 → 分配给该角色
    │       │   ├── 项目任务 → 可能创建项目组，委派给项目总监
    │       │   └── 普通任务 → 直接分配
    │       │
    │       └── 无 → 问用户是否创建新角色
    │
    ├── 是否需要创建项目组？
    │   ├── 复杂项目 → 走项目工作流（详见 collaboration/project-workflow.md）
    │   └── 简单任务 → 直接处理或分配
    │
    └── 特殊情况：suri 也不确定怎么处理
        └── 问用户是否允许增加新技能
```

---

## 二、系统架构

### 架构分层

```
┌──────────────────────────────────────────────┐
│               接入层 (Access)                   │
│      CLI / Telegram / WebSocket / API          │
└─────────────────────┬────────────────────────┘
                      │
┌─────────────────────▼────────────────────────┐
│              事件总线 (EventBus)               │
│        异步发布/订阅，万物皆事件                │
└────┬──────────┬──────────┬──────────┬─────────┘
     │          │          │          │
     ▼          ▼          ▼          ▼
  suri(主人)   角色1      角色2      角色3
  (Agent)    (Agent)    (Agent)    (Agent)
```

### 插件全景

| 层级 | 插件 | 职责 |
|------|------|------|
| **内核层** (1) | suri_core | 内核核心，自举注册，EventBus + PluginManager 协调 |
| **基础服务层** (3) | config_service, log_service, security_service | 配置/日志/安全 |
| **执行层** (6) | task_scheduler, task_planner, agent_registry, interrupt_handler, role_comm, code_tool | 任务调度分解、Agent管理、角色通信、中断处理、代码工具 |
| **能力层** (6) | llm_gateway, role_manager, memory_service, role_learner, mcp_framework, upgrade_manager | LLM 网关、角色管理、记忆存储、角色学习、MCP协议、升级管理 |
| **接入层** (1) | access | 多通道接入 |
| **扩展层** (5) | test_framework, cron_service, hooks_service, doc_sync, monitor | 测试/定时/钩子/文档同步/监控 |

---

## 三、数据存储

### 存储分层

| 层级 | 位置 | 用途 |
|------|------|------|
| 用户数据 | `~/.suri/data/` | SQLite 数据库、配置文件、升级报告 |
| 运行时数据 | `~/.suri/runtime/` | 角色实例、动态插件、会话缓存 |
| 临时数据 | `/tmp/suri-agent/` | 解压文件、临时缓存 |
| 备份数据 | `~/.suri/backup/` | 代码变更快照 |

### 角色运行时数据

```
~/.suri/runtime/roles/{role_id}/
  ├── soul.md                 # 角色自我定义（可被 suri 更新）
  ├── skills/                 # 角色技能（可自学自增）
  │   └── {skill_name}_v{major}.{minor}.json
  ├── memories/               # 角色记忆
  │   ├── role.db (SQLite)
  │   └── insights/
  │       └── {timestamp}_{type}.md
  └── meta.json               # 角色元数据（类型/创建时间/版本）
```

**核心角色 suri** 的运行时数据位于 `~/.suri/runtime/roles/suri/`。

**代码仓库中的 `roles/` 目录** 仅作为角色模板/初始数据。

### SQLite 表结构

| 表名 | 用途 | 归属 |
|------|------|------|
| `plugins` | 插件注册表 | suri_core |
| `events` | 事件日志 | suri_core |
| `messages` | 通信记录 | role_comm |
| `changes` | 代码变更审计 | security_service |
| `agents` | Agent 注册表 | agent_registry |
| `agent_steps` | Agent 步骤 | agent_registry |

---

## 四、启动流程

```
main.py（极简入口，<20 行）
    │
    ▼
实例化 SuriCorePlugin（内核插件）
    │
    ▼
bootstrap()：
  ├─ 创建 EventBus（含内部分发逻辑）
  ├─ 创建 PluginManager
  ├─ 自注册：suri_core 注册为第一个插件
  └─ 扫描并加载其他插件
    │
    ▼
系统就绪，等待事件
```

---

## 五、插件生命周期

```
扫描 → 加载 → 初始化 → 注册 → 运行 → 暂停 → 卸载 → 清理
```

- **扫描**：plugin_manager 读取 plugins/ 和 `~/.suri/runtime/plugins/`
- **加载**：import 插件模块
- **初始化**：调用插件 init()，传入 event_bus 和配置
- **注册**：插件声明订阅的事件类型（含 manifest.json 暴露声明）
- **运行**：开始接收和处理事件
- **暂停**：暂停事件处理（保留状态）
- **卸载**：停止事件处理，调用 cleanup()
- **清理**：移除注册，释放资源

### 插件暴露声明（manifest.json）

```json
{
  "name": "my_plugin",
  "exposes": {
    "events": ["event.type1", "event.type2"],
    "tools": ["tool_name1", "tool_name2"],
    "commands": ["/cmd1"],
    "apis": {
      "method_name": {
        "params": {...},
        "returns": "..."
      }
    }
  },
  "hot_reload": "hot | warm | cold",
  "notify_on_change": ["role_type:worker"]
}
```

---

## 六、事件总线

- **异步**：基于 asyncio.Queue
- **模式**：发布/订阅
- **通信规则**：所有实体仅通过 EventBus 通信，禁止直接调用

### 事件类型分类

| 类别 | 事件 | 说明 |
|------|------|------|
| 系统 | `system.*` | 启动、关闭、插件变更 |
| 用户 | `user.input` / `user.command` | 用户输入 |
| 角色 | `role.*` | 角色创建、调用、销毁、技能激活、Soul 更新 |
| 任务 | `task.*` | 任务创建、规划、调度、完成、失败 |
| Agent | `agent.*` | Agent 创建、状态变更、受阻 |
| LLM | `llm.request` / `llm.response` | 大模型请求/响应 |
| 工具 | `tool.call` / `tool.result` / `tool.registered` | 工具调用/结果/注册 |
| 插件 | `plugin.*` | 插件加载、卸载、注册、升级 |
| 升级 | `upgrade.*` | 升级报告事件 |
| 中断 | `interrupt.*` | 中断处理事件 |

---

## 七、错误处理

### 错误码规范

| 错误码段 | 类别 | 说明 |
|----------|------|------|
| `1000-1099` | 系统级 | suri_core / EventBus / PluginManager |
| `1100-1199` | 基础服务 | config_service / log_service / security_service |
| `2000-2099` | 任务调度 | task_scheduler / task_planner |
| `2100-2199` | Agent | agent_registry / interrupt_handler |
| `2200-2299` | 通信 | role_comm |
| `3000-3099` | LLM | llm_gateway |
| `4000-4099` | 角色 | role_manager / role_learner |
| `4100-4199` | 升级 | upgrade_manager |
| `5000-5099` | 接入 | access |
| `9000-9099` | 通用 | 跨插件通用错误 |

---

## 八、角色与插件解耦

```
角色 (Role) = 数据（Soul 文件、技能、记忆）
插件 (Plugin) = 逻辑（处理事件、调用 LLM、操作文件）

角色不包含逻辑，插件不包含角色数据
```

- **插件不绑定特定角色** — 任何角色都可调用任何插件
- **角色切换** — 只影响 system prompt 和上下文，不影响插件运行
- **新增角色** — 不需要修改任何插件代码

### 插件版本协商

```json
{
  "name": "task_planner",
  "version": "1.2.0",
  "api_version": "1.0",
  "provides_interfaces": ["TaskPlanner"],
  "requires_interfaces": {
    "llm_gateway": ">=1.0.0",
    "role_manager": ">=1.0.0"
  },
  "event_contract": {
    "publishes": ["task.planned", "task.plan_updated"],
    "subscribes": ["task.plan_requested", "task.replan_requested"]
  }
}
```

---

## 九、安全沙箱

- **代码审查**：动态插件加载前静态扫描（禁止网络请求、系统删除等危险操作）
- **权限控制**：每个插件声明所需权限，suri_core 审批
- **资源限制**：CPU 时间、内存使用上限
- **文件隔离**：插件只能访问声明的目录

---

## 十、并发与上下文控制规则

### 10.1 并发规则

```
1. 所有 LLM 请求必须经过 llm_gateway，禁止绕过
2. llm_gateway 管理全局并发数、每模型速率、预算
3. 每个模型有独立的令牌桶（RPM / TPM / max_concurrency）
4. 请求按优先级调度：0(urgent) > 1(high) > 2(normal) > 3(low)
5. 高优先级可抢占低优先级（低优先级重新排队）
6. 排队超时后自动降级到备选模型
7. 所有备选不可用 → 通知调用方（不阻塞）
8. 预算超限后自动降级或拒绝
```

### 10.2 上下文隔离规则

```
1. 每个 Task 拥有独立的 Context，互不干扰
2. Context = system_layer + session_layer + task_layer + history_layer + memory_layer
3. system_layer：角色 Soul + 技能（固定不变）
4. session_layer：同会话内的 Task 共享（业务目标 + 已决策事项）
5. task_layer：每个 Task 独立（任务描述 + 状态 + 依赖）
6. history_layer：每个 Task 独立（对话历史，超限自动压缩）
7. memory_layer：每个 Task 独立从角色记忆检索
8. Agent 间通信是消息传递，不是上下文共享
```

### 10.3 上下文缓存规则

```
1. 三级缓存：Hot Tier(内存) → Warm Tier(SQLite) → Cold Tier(磁盘)
2. Hot Tier 默认容量 10，保留当前活跃 Task 的 Context
3. Warm Tier 默认容量 100，保留挂起 Task 的完整 Context（JSON 序列化）
4. Cold Tier 保留已完成 Task 的压缩摘要（LLM 生成）
5. LRU 替换：Hot 满 → 最旧移到 Warm；Warm 满 → 最旧压缩移到 Cold
6. Warm → Hot 反序列化恢复，Cold → Hot 需基于摘要重新生成
```

### 10.4 上下文压缩规则

```
1. history_layer token 数超过阈值（默认 40K）时自动压缩
2. 压缩策略：LLM 生成摘要，保留最近 N 条完整消息（默认 5）
3. 压缩不涉及 system/session/task 层，只压缩 history
4. 压缩异步执行，不阻塞当前 LLM 请求
```

### 10.5 任务派生规则

```
1. Task 派生子任务时，Context.clone() 继承父 Context
2. clone 规则：system + session 继承，task 替换，history 清空
3. 子任务完成后，关键结果注入父 Task 的 history_layer
4. 子任务失败不影响父 Task（有独立异常处理）
```

### 10.6 数据写入幂等规则

```
1. 所有数据写入操作必须幂等（支持重复执行）
2. 写操作先检查目标是否存在，存在则跳过或覆盖（按场景）
3. 文件写使用临时隔离空间 → rename 到目标
4. SQLite 写通过队列串行化，读通过 WAL 模式并发
```