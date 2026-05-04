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

> ⚠️ **重要**：角色数据分为两大类，分别管理，不可混淆。

### 3.1 角色定义数据（入 Git，在 `roles/{id}/` 下）

suri-agent 是"末日程序"，角色 **定义**（Soul、技能描述、元数据）比代码更宝贵，必须纳入 Git 版本控制。

```
roles/{role_id}/（Git 管理）
  ├── soul.md                 # 角色自我定义（系统 prompt 核心）
  ├── skills/                 # 角色技能定义（可自学自增）
  │   └── {skill_name}_v{major}.{minor}.json
  ├── meta.json               # 角色元数据（role_type/version/创建时间）
  └── reference/              # 角色参考资料（可选，角色自行维护）
```

**注意**：角色运行时数据（记忆、SQLite DB）不在此目录，入 Git 的仅为角色**定义**文件。

### 3.2 角色运行时数据（不入 Git，在 `~/.suri/runtime/roles/` 下）

运行时数据涉及执行上下文切换、会话缓存、记忆库，时效性强且体积大，不适合 Git 管理。

```
~/.suri/runtime/roles/{role_id}/
  ├── adhoc/                  # 临时会话数据（7天自动清理）
  │   └── {session_id}/
  │       └── role.db         # 会话记忆库
  ├── projects/               # 项目工作数据
  │   └── {project_id}/
  │       └── role.db         # 项目记忆库 + context_snapshots
  ├── global/
  │   └── role.db             # 全局记忆库
  ├── context/
  │   └── snapshot.json       # 角色上下文快照（用于休眠/恢复）
  └── output/                 # 角色产出文件（可选入 Git）
```

### 3.3 系统数据与运行时

```
~/.suri/
  ├── config.json             # API Key、模型选择等敏感配置（不进入 Git）
  ├── data/                   # 中央数据
  │   ├── suri.db             # 中央 SQLite（事件记录、审计日志、三清单缓存）
  │   └── upgrade_reports/    # 升级报告存档
  └── runtime/
      ├── logs/               # 运行时日志
      ├── sessions/           # 会话缓存
      └── agent_framework/plugins/   # 动态插件运行时数据
```

### 存储分层总览

| 层级 | 位置 | 用途 | 入 Git |
|------|------|------|--------|
| 角色定义 | `roles/{id}/` | soul.md / skills / meta.json | ✅ 是 |
| 角色运行时 | `~/.suri/runtime/roles/{id}/` | 记忆库 DB / context_snapshots / output | ❌ 否 |
| 系统数据 | `~/.suri/data/` | 中央 SQLite、升级报告 | ❌ 否 |
| 临时数据 | `/tmp/suri-agent/` | 解压文件、临时缓存 | ❌ 否 |
| 备份数据 | `~/.suri/backup/` | 代码变更快照 | ❌ 否 |

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

- **扫描**：plugin_manager 递归扫描 agent_framework/plugins/ 所有子目录 + `~/.suri/runtime/agent_framework/plugins/`
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

### 7.1 错误码规范

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

### 7.2 完整错误码注册表

#### 系统级（1000-1099）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 1001 | `EVENT_BUS_FULL` | EventBus 队列已满，丢弃 LOW 事件 | ✅ | `error.system` |
| 1002 | `PLUGIN_LOAD_FAILED` | 插件加载失败（语法错误/依赖缺失） | ❌ | `error.plugin` |
| 1003 | `PLUGIN_INIT_FAILED` | 插件初始化失败 | ❌ | `error.plugin` |
| 1004 | `CIRCULAR_DEP_DETECTED` | 插件间检测到循环依赖 | ❌ | `error.system` |
| 1005 | `PLUGIN_TIMEOUT` | 插件事件响应超时 | ✅ | `error.plugin` |
| 1006 | `SYSTEM_SHUTDOWN_ERROR` | 系统关闭流程异常 | ❌ | `error.system` |

#### 基础服务（1100-1199）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 1101 | `CONFIG_NOT_FOUND` | 配置文件缺失 | ✅ | `error.plugin` |
| 1102 | `SECURITY_PATH_DENIED` | 文件沙箱路径越界访问 | ❌ | `error.security` |
| 1103 | `APPROVAL_EXPIRED` | 审批令牌已超时 | ✅ | `error.security` |
| 1104 | `APPROVAL_REJECTED` | 审批被用户拒绝 | ❌ | `error.security` |
| 1105 | `LOG_WRITE_FAILED` | 日志写入失败 | ✅ | `error.system` |

#### 任务调度（2000-2099）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 2001 | `TASK_PLAN_FAILED` | 任务分解失败 | ✅ | `task.failed` |
| 2002 | `TASK_STEP_TIMEOUT` | 任务步骤执行超时 | ✅ | `task.timeout` |
| 2003 | `TASK_MAX_RETRIES` | 任务已达最大重试次数 | ❌ | `task.failed` |
| 2004 | `TASK_DEP_MISSING` | 任务依赖未满足 | ✅ | `task.failed` |
| 2005 | `TASK_PRIORITY_INVALID` | 优先级参数不合法 | ❌ | `task.failed` |

#### Agent 相关（2100-2199）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 2101 | `AGENT_CREATE_FAILED` | Agent 创建失败 | ❌ | `agent.blocked` |
| 2102 | `AGENT_MAX_CONCURRENT` | 并发 Agent 数已达上限（100） | ✅ | `error.system` |
| 2103 | `INTERRUPT_UNRESOLVED` | 中断未能自动解决，需要人工介入 | ✅ | `interrupt.escalated` |

#### 通信（2200-2299）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 2201 | `ROLE_NOT_FOUND` | 目标角色不存在 | ❌ | `role.message_rejected` |
| 2202 | `SESSION_INACTIVE` | 会话已过期或不活跃 | ✅ | `role.message_rejected` |
| 2203 | `MSG_PERMISSION_DENIED` | 角色无权向目标角色发消息 | ❌ | `error.security` |

#### LLM 网关（3000-3099）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 3001 | `LLM_RATE_LIMITED` | 模型请求被限流 | ✅ | `llm.error` |
| 3002 | `LLM_BUDGET_EXCEEDED` | 模型预算超限 | ✅ | `llm.error` |
| 3003 | `LLM_TIMEOUT` | LLM 请求超时 | ✅ | `llm.error` |
| 3004 | `LLM_MODEL_UNAVAILABLE` | 模型不可用（API 降级/维护） | ✅ | `llm.error` |
| 3005 | `LLM_CONTEXT_OVERFLOW` | 上下文超过模型限制 | ✅ | `llm.error` |
| 3006 | `LLM_INVALID_RESPONSE` | LLM 返回格式异常 | ✅ | `llm.error` |

#### 角色管理（4000-4099）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 4001 | `ROLE_CREATE_FAILED` | 角色创建失败（soul.md 模板无效） | ❌ | `error.plugin` |
| 4002 | `ROLE_SOUL_INVALID` | Soul 文件格式校验失败 | ✅ | `role.created` |
| 4003 | `ROLE_SKILL_MISSING` | 技能文件缺失 | ✅ | `role.status_changed` |
| 4004 | `ROLE_LEARN_FAILED` | 角色学习分析失败 | ✅ | `error.plugin` |

#### 接入层（5000-5099）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 5001 | `CHANNEL_AUTH_FAILED` | 接入通道认证失败 | ✅ | `error.plugin` |
| 5002 | `CHANNEL_RATE_LIMITED` | 通道被限流 | ✅ | `error.plugin` |
| 5003 | `CHANNEL_TIMEOUT` | 通道响应超时 | ✅ | `error.plugin` |
| 5004 | `INVALID_COMMAND` | 非法命令格式 | ❌ | `error.plugin` |

#### 通用错误（9000-9099）

| 错误码 | 名称 | 说明 | 是否可恢复 | 发布事件 |
|--------|------|------|-----------|---------|
| 9001 | `INTERNAL_ERROR` | 插件内部未分类异常 | ✅ | `error.plugin` |
| 9002 | `NOT_IMPLEMENTED` | 功能尚未实现 | ❌ | `error.plugin` |
| 9003 | `INVALID_PARAMS` | 参数校验失败 | ❌ | `error.plugin` |
| 9004 | `RESOURCE_EXHAUSTED` | 资源耗尽（CPU/内存/磁盘） | ✅ | `error.system` |

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

### 10.2 上下文模型（详见 architecture.md）

> 上下文模型的完整定义（5 层架构、三级缓存、生命周期管理）已在 `prd/overview/architecture.md` 第 7 章详细描述。
> 本文件仅列出框架规则层面的关键约束。

```
1. 每个 Task 拥有独立的 Context，互不干扰
2. Agent 间通信是消息传递，不是上下文共享
3. LLM 请求全走 llm_gateway，系统 prompt 在请求前刷新
4. 数据写入必须幂等（支持重试不造成重复）
5. context 变更须广播事件通知相关方
```

### 10.3 上下文压缩规则

```
1. history_layer token 数超过阈值（默认 40K）时自动压缩
2. 压缩策略：LLM 生成摘要，保留最近 N 条完整消息（默认 5）
3. 压缩不涉及 system/session/task 层，只压缩 history
4. 压缩异步执行，不阻塞当前 LLM 请求
```

### 10.4 任务派生规则

```
1. Task 派生子任务时，Context.clone() 继承父 Context
2. clone 规则：system + session 继承，task 替换，history 清空
3. 子任务完成后，关键结果注入父 Task 的 history_layer
4. 子任务失败不影响父 Task（有独立异常处理）
```

### 10.5 并发写入锁机制

> 当多个 Agent 同时写入同一文件时，必须通过文件锁串行化写入操作，防止数据损坏。

```python
import asyncio
import fcntl
from pathlib import Path

class FileWriteLock:
    """
    基于 fcntl.flock 的跨进程文件写入锁。
    同一进程内也可通过 asyncio.Lock 做协程级串行化。
    """
    
    _instance = None
    _coroutine_locks: dict[str, asyncio.Lock] = {}
    _lock_dir = Path("/tmp/suri-agent/locks/")
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._lock_dir.mkdir(parents=True, exist_ok=True)
        return cls._instance
    
    async def acquire(self, path: str, timeout: float = 10.0) -> bool:
        """
        获取文件写入锁。
        先通过 asyncio.Lock 串行化协程，再通过 fcntl.flock 串行化进程。
        """
        lock_key = Path(path).resolve().as_posix()
        
        # 协程级锁（同一进程内串行化）
        if lock_key not in self._coroutine_locks:
            self._coroutine_locks[lock_key] = asyncio.Lock()
        
        coro_lock = self._coroutine_locks[lock_key]
        
        try:
            # 等待协程锁（带超时）
            await asyncio.wait_for(coro_lock.acquire(), timeout=timeout)
            
            # 进程级锁（跨进程串行化）
            lock_file = self._lock_dir / lock_key.replace("/", "_")
            fd = lock_file.open("w")
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            
            return True
        except asyncio.TimeoutError:
            return False
    
    async def release(self, path: str) -> None:
        """释放文件写入锁"""
        lock_key = Path(path).resolve().as_posix()
        if lock_key in self._coroutine_locks:
            self._coroutine_locks[lock_key].release()
```

### 10.6 数据写入幂等规则

```
1. 所有数据写入操作必须幂等（支持重复执行，不造成重复效果）
2. 文件写使用临时隔离空间 → os.replace() 原子重命名到目标
3. SQLite 写通过队列串行化 + WAL 模式（读并发，写串行）
4. 并发文件写入须使用 FileWriteLock（见 §10.5），防止 race condition
5. 写操作前应先检查目标状态（文件是否存在 / DB 记录是否已存在）
6. Key-Value 写入使用 INSERT OR REPLACE（SQLite）或 conditional put
7. 追加写入（如日志）不检查存在性，每条记录唯一 ID 保证幂等

并发写入场景示例：
  Agent A（写 src/main.py）和 Agent B（写同一文件）同时进行：
    1. FileWriteLock.acquire("src/main.py") → Agent A 获得锁
    2. Agent A 写入临时文件 → os.replace() 到目标
    3. FileWriteLock.release("src/main.py")
    4. Agent B 获得锁 → 读取最新文件 → 写入 → 释放
    → 保证文件内容不因并发写入而损坏
```