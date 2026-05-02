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
```

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
- 下游：task_scheduler（调度执行）
- 下游：interrupt_handler（受阻处理）
- 下游：log_service（记录生命周期事件）

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
