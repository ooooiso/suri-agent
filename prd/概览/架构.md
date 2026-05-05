# 架构全景

> 描述 suri-agent 的整体架构。suri 是主人 Agent（角色类型 core），按 Soul 定义处理业务、自我进化、系统维护，并调度其他角色完成专职任务。

---

## 一、核心架构理念

### suri 的定位 — 主人 Agent，按 Soul 行事

suri 是系统中唯一的 **core** 类型角色，她的行为边界由 `roles/suri/soul.md` 定义。

```
suri = 主人 Agent（role_type=core）
  ├── 职责边界：由 Soul 决定
  │   ├── 当需求在 suri 技能范围内 → 直接处理
  │   ├── 当需求属于调度/维护范畴 → 执行调度/维护
  │   └── 当需求完全超出能力 → 申请升级自身
  │
  ├── 核心技能（Soul 固定部分）：
  │   1. 创建角色 — 没有合适角色时创建新角色
  │   2. 维护主程序 — 修改代码、新增插件、更新配置
  │   3. 任务调度 — 将任务分配给合适的角色
  │   4. 升级自身 — 能力不足时申请增加新技能
  │
  ├── 可扩展能力：通过自身技能学习获得
  │
  └── 系统职责：
      ├── 维护三清单（Role/Plugin/Tool Registry）的一致性
      ├── 接收广播事件 → 评估系统影响 → 决策调整
      ├── 通过自然语言对话开发维护插件和工具
      ├── 更新角色的 Soul（职责/能力边界）
      ├── 评估和确认角色的技能建议
      ├── 管理插件生命周期
      └── 处理异常和中断
```

### 角色可用所有工具，Soul 约束行为边界

**关键原则**：角色可以使用系统中所有注册的工具，**不做白名单控制**。约束来自角色的 Soul 定义。

```
设计师角色的 Soul:
  "我是一名视觉设计师，我的职责是设计用户界面和交互体验。
  我擅长使用设计类工具，但我不应该直接修改生产代码。"

→ Soul 约束设计师不会调用 code_tool.write_file
→ 如果调用了，说明有合理的上下文
→ 如果误调用，security_service 审计日志会记录
→ suri 可以通过对话提醒"这个操作不符合你的职责"
```

### 多 Agent 智能体架构

```
每个角色 = 一个独立的 Agent（智能体）
  ├── 独立的 Soul（自我定义、职责、能力边界）
  ├── 独立的技能（skill 文件，可自学自增，含 tool_mappings 映射工具集）
  ├── 独立的记忆（三层存储：Ad-hoc/Project/Global）
  ├── 独立的学习能力（role_learner 异步分析）
  ├── 独立的工具调用（通过 MCP 框架，自动携带 project_id/role_id）
  └── 独立的通信能力（role_comm，角色间自然语言协作）
```

> **概念澄清**：在本系统中，"角色（Role）"和"Agent"是同一概念。一个角色 = 一个 Agent = 一个独立的智能体实体。`agent_registry` 插件创建的 Agent 实例是角色的"执行实例"，一个角色在同一个项目中通常只有一个活跃执行实例。详见 `prd/agents/agent-overview.md`。

---

## 二、系统架构分层

```
┌──────────────────────────────────────────────────────────────────┐
│                        接入层 (Access Layer)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  CLI     │  │ Telegram │  │ WebSocket│  │  未来通道 (API)  │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
└───────┼──────────────┼──────────────┼──────────────────┼──────────┘
        │              │              │                  │
┌───────▼──────────────▼──────────────▼──────────────────▼──────────┐
│                      💠 事件总线 (EventBus)                         │
│              异步发布/订阅，所有实体通过事件通信                      │
└───────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
        │          │          │          │          │
   ┌────▼────┐     ▼          ▼          ▼          ▼
   │ suri    │ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
   │ (core)  │ │ 角色A   │ │ 角色B   │ │ 角色C   │ │ ...    │
   │ 主人Agent│ │(Agent)  │ │(Agent)  │ │(Agent)  │ │(Agent)  │
   │ ⭐调度权 │ └────────┘ └────────┘ └────────┘ └────────┘
   └─────────┘
   (suri 通过 EventBus 发布调度事件，非直接指令)
```

### 核心分层说明

| 层级 | 组件数 | 职责 |
|------|--------|------|
| **内核层** (1) | suri_core | 系统内核，自举注册，协调 EventBus 和 PluginManager |
| **服务层** (3) | config_service, log_service, security_service | 基础服务：配置/日志/安全 |
| **执行层** (7) | task_scheduler, task_planner, agent_registry, interrupt_handler, role_comm, code_tool, **agent_executor** | 任务编排、Agent 管理、通信、代码工具、**Agent 执行引擎** |
| **能力层** (6) | llm_gateway, memory_service, role_manager, role_learner, mcp_framework, upgrade_manager | LLM/记忆/角色管理/学习/工具/升级 |
| **接入层** (1) | access | 多通道接入（CLI/Telegram/WebSocket） |
| **扩展层** (5) | test_framework, cron_service, hooks_service, doc_sync, monitor | 测试/定时/钩子/文档同步/监控 |

---

## 三、三清单体系（核心设计）

> 系统有三个核心清单，实时记录所有身份、能力、状态。变更后广播通知相关方。

### 3.1 三清单总览

```
┌────────────────────────────────────────────────────────────────┐
│                 S U R I  三 清 单 体 系                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ① 角色清单 (Role Registry)                               │   │
│  │  用途：记录所有角色的身份、技能、状态                      │   │
│  │  维护者：role_manager 插件                               │   │
│  │  存储：SQLite + 内存缓存                                 │   │
│  │  关键字段：role_id, role_type, skills(含tool_mappings),  │   │
│  │            status, active_projects                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ② 插件清单 (Plugin Registry)                             │   │
│  │  用途：记录所有插件的身份、版本、能力、状态                │   │
│  │  维护者：plugin_manager 插件                             │   │
│  │  存储：SQLite + 内存缓存                                 │   │
│  │  关键字段：plugin_id, version, type, tools_provided,    │   │
│  │            status, call_count, error_rate               │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ③ 工具清单 (Tool Registry)                               │   │
│  │  用途：记录所有工具的注册信息、调用统计、状态              │   │
│  │  维护者：mcp_framework 插件                              │   │
│  │  存储：SQLite + 内存缓存                                 │   │
│  │  关键字段：tool_id, source_plugin, call_count, status,  │   │
│  │            permission_level                              │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 变更广播机制

```
任何变更发生后（角色/工具/插件）：
  1. 更新对应清单
  2. 发布变更事件（带完整 payload）
  3. suri 接收事件 → 评估是否需要调整系统策略
  4. 所有角色接收事件 → 评估是否需要调整自身行为
  5. 用户可见的通知（通过 access 层）
```

> **完整事件注册表见 `prd/schema/event-registry.md`**，覆盖 12 大类 60+ 事件。

### 3.3 角色清单项目信息

角色清单中的每条记录包含角色参与的项目信息：

```python
role_registry.get_role("developer") = {
    "role_id": "developer",
    "role_type": "worker",
    "current_project": "internal_tools",  # 当前活跃项目
    "active_projects": [                  # 参与的所有项目
        {
            "project_id": "ecommerce_app",
            "joined_at": "2026-04-01",
            "last_active": "2026-05-03",
            "task_count": 45
        },
        {
            "project_id": "internal_tools",
            "joined_at": "2026-04-15",
            "last_active": "2026-05-04",
            "task_count": 23
        }
    ],
    "status": "ready"                    # 角色状态，详见 agent-overview.md
}
```

---

## 四、上下文与存储体系（双维度）

> 本系统从**两个维度**管理上下文与数据，两者互不冲突：
> - **存储维度**（三层隔离）：角色数据的物理存储位置隔离
> - **运行时维度**（Context 结构）：LLM 调用时构建的上下文结构

### 4.1 存储维度 — 三层隔离

角色的运行时数据按物理位置分为三层：

```
① Ad-hoc 层（临时会话）
   存储：~/.suri/runtime/roles/{role_id}/adhoc/{session_id}/role.db
   特点：聊完归档、7天自动清理（cron_service 负责）、不沉淀为长期记忆
   隔离度：★★★★★

② Project 层（项目工作）
   存储：~/.suri/runtime/roles/{role_id}/projects/{project_id}/role.db
   特点：完整记忆系统、切换时保存快照+加载新项目
   隔离度：★★★★★

③ Global 层（全局记忆）
   存储：~/.suri/runtime/roles/{role_id}/global/role.db
   特点：所有项目共享、沉淀通用技能、永久保留
   隔离度：★★☆☆☆
```

### 4.2 运行时维度 — Context 五层结构

> **当前 V0.5 实现**：使用字符串拼接构建 Context。
> **V2.0 目标**：实现完整的 Context Manager（五层结构 + 三级缓存）。
> 详见 `prd/plugins/capability/llm_gateway.md` §三。

每个 LLM 请求的上下文由以下五层构成（V2.0）：

```
┌──────────────────────────────────────────────────────────────┐
│  Context (task_01)                                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ system_layer（固定）                                     │  │
│  │ ├ 角色 Soul（system prompt）                            │  │
│  │ ├ 技能定义（当前可用技能）                               │  │
│  │ └ 当前模型信息（模型名/切换方式）                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ session_layer（会话共享）                                │  │
│  │ ├ 会话目标（用户本次交互的目标描述）                      │  │
│  │ ├ 已决策事项（会话内已经达成一致的决策）                  │  │
│  │ └ 业务上下文（关联的项目/文件/需求）                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ task_layer（当前任务）                                   │  │
│  │ ├ 任务描述（当前 Task 的目标）                          │  │
│  │ ├ 任务状态（in_progress / waiting / done）              │  │
│  │ └ 任务依赖（该 Task 依赖的其他 Task 结果）               │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ history_layer（对话历史）                                │  │
│  │ ├ messages 列表（role/user/assistant/tool 消息）         │  │
│  │ ├ 上限 20 条（`MAX_HISTORY_MESSAGES`）                  │  │
│  │ ├ 超出上限时 → 最早的被压缩为摘要                        │  │
│  │ └ 摘要也作为一个消息保留                                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ memory_layer（按需注入）                                 │  │
│  │ ├ 从 memory_service 检索的长期记忆片段                  │  │
│  │ ├ 按相关性打分，top-K 注入                              │  │
│  │ └ 每个 Task 独立检索（不同任务检索不同记忆）              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**存储维度与运行时维度的关系**：

| 存储层 | 提供数据给运行时 Context 的哪些层 |
|--------|--------------------------------|
| Ad-hoc DB | history_layer + session_layer |
| Project DB | history_layer + session_layer + memory_layer(项目限定) |
| Global DB | memory_layer(全局记忆来源) + system_layer(技能) |
| role/{id}/soul.md | system_layer |
| role/{id}/skills/ | system_layer(技能描述) |

### 4.3 项目切换机制

```
角色当前在"电商APP"项目工作
    │
    ├── suri 分配了新任务："去内部工具项目修复登录 bug"
    │
    ▼
suri 发布 project.context_switched 事件
    │
    ▼
developer 角色接收事件：
    │
    ├── Step 1: 保存当前项目上下文
    │   ├─ 从 Project DB 读取当前运行时 Context
    │   ├─ 压缩为 context_snapshot
    │   └─ 存入 projects/ecommerce_app/role.db
    │
    ├── Step 2: 加载目标项目上下文
    │   ├─ 从 projects/internal_tools/role.db 读取 context_snapshots
    │   ├─ 读取项目摘要
    │   └─ 构建新的运行时 Context
    │
    └── Step 3: 开始执行新任务
        ├─ 所有工具调用自动附加 project_id
        ├─ 所有新消息写入 internal_tools 的 Project DB
        └─ 所有新事实写入 internal_tools 的 Project DB
```

### 4.4 工具调用自动携带元数据

```python
# 所有工具调用自动传递上下文元数据
class RoleAgent:
    async def call_tool(self, tool_name: str, params: dict):
        result = await self.mcp_server.call_tool(
            tool_name=tool_name,
            params={
                **params,
                "_meta": {
                    "role_id": self.role_id,
                    "project_id": self.current_project,
                    "task_id": self.current_task_id,
                    "session_id": self.current_session_id
                }
            }
        )
        return result
```

---

## 五、角色与插件的关系

```
角色 (Role) = 智能体（独立的 Agent）
  ├── 拥有 Soul 文件 → 自我定义、职责、能力边界
  ├── 拥有技能 → 通过技能调用插件/MCP 工具
  ├── 拥有记忆 → 三层隔离的存储系统
  ├── 拥有学习能力 → 自学、自增技能
  └── 拥有通信能力 → 与其他角色协作

插件 (Plugin) = 能力提供者
  ├── 提供工具/服务 → 被角色调用
  ├── 提供事件处理 → 被 EventBus 调度
  ├── 插件自身也是 Agent → 可以学习、更新自己的能力
  └── 不绑定特定角色 → 可被任何角色使用
```

### suri 角色的特殊地位

```
suri 是系统唯一的"主人 Agent"（role_type=core）
  ├── 不可删除
  ├── 有自己的 Soul（决定其行为边界和偏好）
  ├── 有自己的技能（持续学习中）
  ├── 负责处理自己技能范围内的用户需求
  ├── 负责自我升级：开发插件/增加技能/MCP 工具
  ├── 负责调度其他角色（需要时）
  ├── 负责维护三清单体系的一致性
  ├── 接收广播事件 → 评估系统影响
  └── 通过自然语言对话开发维护插件和工具
```

---

## 六、角色通信模型

### 6.1 核心链路

```
角色 A（发送方）→ 调 LLM → LLM 决定"给角色 B 发消息"
  → 发布 role.message 事件（含 session_id）
  → role_comm 存储 + 发布 role.message_received
  → 角色 B 收到事件 → 下次空闲时处理
```

### 6.2 session_id 隔离不同对话

```
role_comm 中的每条消息携带 session_id：
  "dev↔designer_A__ecommerce_login"     # 项目内的开发↔设计师
  "dev↔suri__upgrade_code_tool"          # suri 安排任务
  "suri↔user_张三__project_ecommerce"    # suri 和用户对话

角色查未读消息时按 session_id 分组返回：
  不同 session 的历史互不干扰
  LLM 一次只处理一个 session 的 context
```

---

## 七、suri 通过自然语言维护插件和工具

```
用户： "能不能让 code_tool 支持批量搜索功能？"
    │
    ▼
suri: "分析需求 → 设计实现 → 开发代码 → 注册新工具 → 广播更新"
    │
    ├── 修改对应插件的代码
    ├── 注册/更新工具（更新 Tool Registry）
    ├── 广播 tool.registered / tool.updated
    └── 通知所有角色（特别是正在使用该工具的角色）
```

**工具进化的四种场景**：
1. **新增工具**：角色反复做同一模式操作，可封装为工具
2. **优化工具**：工具响应慢、参数不合理、返回不友好
3. **扩展工具**：工具需要支持更多场景
4. **废弃工具**：工具不再被使用、有更好的替代

---

## 八、用户请求处理核心流程

```
用户: "帮我写一份产品文档"
    │
    ▼
suri 接收需求
    │
    ├── 判断：在我的技能范围内吗？
    │   ├── 能 → suri 自己调用工具处理
    │   └── 不能 →
    │       │
    │       ▼
    │   判断：是否有合适角色？
    │       │
    │       ├── 有 → 检查角色当前项目
    │       │   ├── 同一项目 → 直接分配
    │       │   └── 不同项目 → 先切换再分配
    │       │
    │       └── 没有 →
    │           suri 问用户 → 创建角色 → 配置工具 → 开始工作
    │
    └── 超出能力范围 → 问用户是否允许升级
```

---

## 九、关键约束

1. **suri 按 Soul 行事** — suri 按 `roles/suri/soul.md` 定义的职责处理需求
2. **所有任务由角色技能驱动** — suri 也通过自己的技能执行任务
3. **角色可以自学习、自增技能** — 通过 role_learner + upgrade_manager
4. **suri 负责调度、维护、帮助角色成长**
5. **所有变更加入三清单 + 广播通知** — 角色/工具/插件变更必须同步清单并广播
6. **所有代码自修改须用户确认**
7. **上下文隔离** — 存储层三层隔离（Ad-hoc/Project/Global），防止跨项目混淆
8. **LLM 请求全走 llm_gateway** — 不允许任何插件或角色绕过网关直接调用 API
9. **所有数据写入必须幂等** — 支持重试不造成重复（需配合文件锁使用，见 `framework-rules.md`）
10. **工具调用自动携带 _meta** — 自动附加 role_id/project_id/task_id
11. **角色可用所有工具** — Soul 自然约束，security_service 做安全兜底，不做硬边界白名单
12. **权限优先级规则**：Soul约束 > 工具权限声明 > 文件沙箱权限，security_service 做最终安全兜底

---

## 十、相关文档索引

| 文档 | 内容 | 本文件中的引用章节 |
|------|------|------------------|
| `prd/schema/event-registry.md` | 完整事件注册表（12 大类 60+ 事件） | §三、§九 |
| `prd/agents/agent-overview.md` | 角色类型、状态、生命周期 | §一、§五 |
| `prd/overview/design-principles.md` | 解耦设计原则、数据存储规范 | §四、§九 |
| `prd/plugins/capability/llm_gateway.md` | Context Manager 五层结构 + 三级缓存 | §四 |
| `prd/operations/framework-rules.md` | 框架核心规则、并发控制、幂等约束 | §九 |
| `prd/security/security-spec.md` | AST 扫描、文件沙箱、审批令牌 | §九(约束11) |