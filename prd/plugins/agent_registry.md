# agent_registry 插件 PRD

## 定位

Agent 生命周期管理。创建/销毁 Agent，跟踪执行状态，支持父子关系，提供进度查询。

**关键约束**：只管理 Agent 元数据和状态，不执行 Agent 逻辑，不调用 LLM。

## 功能需求

### 1. Agent CRUD

- `create_agent(task_text, role_id, user_id)` → 生成 agent_id，创建 Agent 记录和独立 AgentContext
- `create_sub_agent(parent_id, subtask, role_id, user_id)` → 创建子 Agent，自动关联父 Agent
- `destroy_agent(agent_id)` → 销毁 Agent，释放上下文
- `get_agent(agent_id)` → 获取 Agent 信息
- `list_agents(user_id=None, status=None)` → 按条件列出 Agent

### 2. 状态跟踪

Agent 六态模型：

```
planning ──▶ running ──▶ completed
    │           │
    │           ├──▶ blocked ──▶ running（恢复）
    │           │
    │           └──▶ paused ──▶ running（恢复）
    │
    └──▶ cancelled
```

步骤四态模型：pending → in_progress → completed / blocked

### 3. 父子关系

- `parent_agent_id` 字段建立树形结构
- 父 Agent 状态自动聚合子 Agent 状态
- 子 Agent 完成时更新父 Agent 进度
- `get_children(parent_id)` 获取子 Agent 列表

### 4. 进度查询

- `Agent.progress` → "completed/total" 格式（如 "2/4"）
- `Agent.current_step` → 当前进行中的步骤
- `get_user_stats(user_id)` → 该用户的任务统计（total/active/completed/by_status）

### 5. AgentContext 隔离

每个 Agent 拥有独立的上下文：
- 独立的 message history
- 从 Soul 文件构建的系统提示（前 2000 字符 + 任务分解方法论）
- 不与其他 Agent 共享消息记录

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `agent.create_requested` | 角色 / task_scheduler | 创建 Agent |
| `agent.step_update` | 角色 | 更新步骤状态 |
| `agent.block_requested` | interrupt_handler | 标记 Agent 受阻 |
| `agent.destroy_requested` | 角色 / 系统 | 销毁 Agent |
| `task.completed` | task_scheduler | 同步对应 Agent 状态为 completed |
| `task.failed` | task_scheduler | 同步对应 Agent 状态为 failed |
| `task.timeout` | task_scheduler | 同步对应 Agent 状态为 timeout |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `agent.created` | log_service / 角色 | Agent 创建完成 |
| `agent.status_changed` | log_service / task_scheduler | 状态变更 |
| `agent.completed` | log_service / role_learner / 角色 | Agent 完成 |
| `agent.blocked` | log_service / interrupt_handler | Agent 受阻 |
| `agent.destroyed` | log_service | Agent 已销毁 |

### 方法

```python
class AgentRegistry:
    async def create_agent(self, task_text: str, role_id: str, user_id: str,
                           plan_id: str = None) -> Agent
    async def create_sub_agent(self, parent_id: str, subtask: str, 
                               role_id: str, user_id: str) -> Agent
    def get_agent(self, agent_id: str) -> Optional[Agent]
    def update_step(self, agent_id: str, step_id: str, 
                    status: str, result: str = None) -> bool
    def block_agent(self, agent_id: str, reason: str) -> bool
    def complete_agent(self, agent_id: str) -> bool
    def get_progress(self, agent_id: str) -> str
    def get_user_stats(self, user_id: str) -> Dict[str, Any]
    def cleanup_old_agents(self, max_age_hours: int = 24) -> int
```

## 数据模型

```python
@dataclass
class Agent:
    agent_id: str
    task_id: str
    task_name: str
    parent_agent_id: Optional[str]
    role_id: str
    status: str                        # planning | running | paused | completed | blocked | cancelled
    steps: List[TaskStep]
    user_id: str
    plan_id: Optional[str]
    created_at: str
    updated_at: str
    
    @property
    def progress(self) -> str:
        completed = sum(1 for s in self.steps if s.status == "completed")
        return f"{completed}/{len(self.steps)}"
    
    @property
    def current_step(self) -> Optional[TaskStep]:
        for s in self.steps:
            if s.status == "in_progress":
                return s
        for s in self.steps:
            if s.status == "pending":
                return s
        return None

class AgentContext:
    def __init__(self, agent_id: str, task_state: TaskStateService):
        self.agent_id = agent_id
        self._messages: List[Dict[str, str]] = []
    
    def add_message(self, role: str, content: str) -> None
    def build_chat_messages(self, role_id: str, task_hint: str = "") -> List[Dict]
        """构建 LLM 聊天消息列表
        
        调用链：
        1. agent_registry 创建 Agent 时初始化 AgentContext
        2. 角色执行任务前调用 build_chat_messages()
        3. build_chat_messages() 内部调用 role_learner.get_recent_insights_for_context(role_id, task_hint)
        4. 将 Soul + insights + skills 组装为 system prompt
        5. 附加历史消息和当前任务消息
        
        洞察注入限制：
        - 总字符不超过 2000
        - 按 task_hint 关键词粗排匹配
        - 按 confidence + recency 排序
        - 仅注入 30 天内的洞察
        """
```

## 事件 Payload Schema

### 订阅事件

#### `agent.create_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_text` | string | 是 | 任务描述 |
| `role_id` | string | 是 | 角色 ID |
| `user_id` | string | 是 | 用户 ID |
| `plan_id` | string | 否 | 关联的规划 ID |
| `parent_agent_id` | string | 否 | 父 Agent ID |

#### `agent.step_update`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `step_id` | string | 是 | 步骤 ID |
| `status` | string | 是 | pending / in_progress / completed / blocked |
| `result` | string | 否 | 步骤结果 |
| `block_reason` | string | 否 | 受阻原因 |

#### `agent.block_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `reason` | string | 是 | 受阻原因 |
| `step_id` | string | 否 | 受阻的步骤 ID |

#### `agent.destroy_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `reason` | string | 否 | 销毁原因 |
| `cascade` | boolean | 否 | 是否级联销毁子 Agent，默认 false |

### 发布事件

#### `agent.created`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `role_id` | string | 是 | 角色 ID |
| `task_name` | string | 是 | 任务名称 |
| `parent_agent_id` | string | 否 | 父 Agent ID |
| `created_at` | string | 是 | 创建时间 |

#### `agent.status_changed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `old_status` | string | 是 | 原状态 |
| `new_status` | string | 是 | 新状态 |
| `timestamp` | string | 是 | 变更时间 |

#### `agent.completed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `progress` | string | 是 | 最终进度，如 "5/5" |
| `duration_ms` | integer | 否 | 总耗时 |

#### `agent.blocked`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `reason` | string | 是 | 受阻原因 |
| `current_step` | object | 否 | 当前步骤信息 |

#### `agent.destroyed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `destroyed_at` | string | 是 | 销毁时间 |

## 配置项

```yaml
agent_registry:
  max_active_agents: 100            # 单用户最大活跃 Agent 数
  cleanup_interval: 3600            # 清理周期（秒）
  max_age_hours: 24                 # 已完成 Agent 保留时长
  enable_wal: true                  # SQLite WAL 模式
  id_entropy: 4                     # agent_id 随机字符数
```

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：memory_service（持久化 Agent 状态到 SQLite）
- 下游：interrupt_handler（受阻处理）
- 下游：log_service（记录生命周期事件）

### 与 role_manager 的边界

| 维度 | agent_registry | role_manager |
|------|---------------|--------------|
| **管理对象** | 临时 Agent 实例 | 持久 Role 身份 |
| **生命周期** | 任务级（创建→完成→销毁） | 系统级（创建→长期存在→删除） |
| **数据存储** | SQLite `agents` / `agent_steps` | 文件系统 `roles/{role_id}/soul.md` |
| **核心职责** | 跟踪执行状态、父子关系、进度 | 管理 Soul、技能、能力索引 |
| **关系** | Agent 必须关联一个 Role | Role 可存在零个或多个 Agent |
| **类比** | 调度板（job ticket） | HR（人员档案） |

## SQLite 表结构

```sql
CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    task_name TEXT,
    parent_agent_id TEXT,
    role_id TEXT NOT NULL,
    status TEXT DEFAULT 'planning',
    user_id TEXT NOT NULL,
    plan_id TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE agent_steps (
    step_id TEXT,
    agent_id TEXT,
    description TEXT,
    status TEXT DEFAULT 'pending',
    assignee TEXT,
    depends_on TEXT,          -- JSON 数组
    estimated_time INTEGER,
    started_at TEXT,
    completed_at TEXT,
    block_reason TEXT,
    result TEXT,
    PRIMARY KEY (step_id, agent_id)
);

CREATE INDEX idx_agents_user ON agents(user_id, status);
CREATE INDEX idx_agents_parent ON agents(parent_agent_id);
```

## 生命周期

1. `init()` → 连接 SQLite、加载活跃 Agent 到内存
2. `start()` → 启动定时清理协程
3. `stop()` → 停止清理协程，保存所有 Agent 状态
4. `cleanup()` → 关闭数据库连接

## 安全边界

- 用户只能访问自己的 Agent（user_id 隔离）
- Agent 数量超过上限时拒绝创建并返回错误事件
- 销毁 Agent 时级联销毁子 Agent（可选配置）
- 数据库操作异常不影响其他 Agent
- **核心原则**：只管理状态和上下文，不执行 Agent 逻辑
