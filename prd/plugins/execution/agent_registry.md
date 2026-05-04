# agent_registry 插件 PRD

## 定位

Agent 生命周期管理。创建/销毁/跟踪 Agent，支持父子关系，提供状态查询和进度跟踪。

---

## 功能需求

### 1. Agent 生命周期

```
created → running → completed
                  → blocked → retrying → running
                  → cancelled
                  → timeout
```

### 2. 父子 Agent

- 子 Agent 继承父 Agent 的上下文
- 子 Agent 完成时通知父 Agent
- 父 Agent 可取消子 Agent

### 3. 状态查询

- 按 agent_id 查询
- 按 task_id 查询
- 按状态过滤
- 支持分页

---

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `task.planned` | task_planner | 创建 Agent |
| `agent.block_requested` | interrupt_handler | 标记 Agent 为受阻 |
| `interrupt.cancelled` | interrupt_handler | 取消 Agent |
| `step.completed` | task_scheduler | 更新步骤进度 |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `agent.created` | task_scheduler | Agent 创建完成 |
| `agent.blocked` | interrupt_handler | Agent 受阻 |
| `agent.completed` | task_scheduler / 角色 | Agent 完成 |
| `agent.cancelled` | task_scheduler | Agent 被取消 |
| `agent.progress` | 角色 | 进度更新 |

---

## 热更新与解耦

### 1. SQLite 持久化

当前使用内存字典存储 Agent 数据，重启后数据丢失。

**优化方案**：
- 从内存字典迁移到 SQLite
- 使用 `agent_framework/migrations/002_agents.sql` 表结构
- 启动时从数据库恢复活跃 Agent
- 定期持久化 Agent 状态变更

### 2. 表结构

```sql
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    parent_agent_id TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS agent_steps (
    step_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    depends_on TEXT,
    started_at TEXT,
    completed_at TEXT,
    result TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
```

---

## 配置项

```yaml
agent_registry:
  db_path: "~/.suri/data/agent_registry.db"
  cleanup_interval: 3600  # 清理过期 Agent 间隔（秒）
  max_agent_age: 86400    # Agent 最大存活时间（秒）
```

---

## 依赖关系

- 上游：suri_core（EventBus）
- 下游：task_scheduler（调度 Agent 步骤）
- 下游：interrupt_handler（处理 Agent 受阻）

---

## 生命周期

1. `init()` → 连接数据库，恢复活跃 Agent
2. `start()` → 启动定期清理
3. `stop()` → 持久化当前状态
4. `cleanup()` → 关闭数据库连接