# memory_service 插件 PRD

## 定位

角色级独立记忆存储插件，为每个角色提供 SQLite 数据库 + 文本记忆文件的管理服务。是系统持久化层的核心。

---

## 一、记忆架构（Architecture Overview）

### 1.1 记忆分类

| 类型 | 说明 | 示例 |
|------|------|------|
| **事实记忆** | 结构化事实数据 | "用户偏好 Markdown 格式" |
| **经验记忆** | 执行任务的记录和结果 | "上次写 API 文档用了 template A" |
| **模式记忆** | 识别出的模式和最佳实践 | "技术文档最佳结构：概述→安装→使用→API" |

### 1.2 存储方式

每个角色拥有独立的 SQLite 数据库：

```sql
-- 结构化记忆
CREATE TABLE memory_facts (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE,
    value TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    access_count INTEGER DEFAULT 0
);

-- 经验记忆
CREATE TABLE memory_experiences (
    id TEXT PRIMARY KEY,
    task_type TEXT,
    context TEXT,
    actions TEXT,      -- JSON
    result TEXT,
    satisfaction REAL,  -- 0-1
    created_at TIMESTAMP
);

-- 模式记忆
CREATE TABLE memory_patterns (
    id TEXT PRIMARY KEY,
    pattern TEXT,
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 1,
    source TEXT,       -- how this pattern was derived
    created_at TIMESTAMP
);
```

### 1.3 记忆生命周期

```
新记忆创建
    │
    ├─ 高频访问 → 保持活跃
    ├─ 低频访问 → 降级为冷存储
    └─ 长期未用 → 被遗忘
```

- **活跃记忆**：最近使用，优先级高
- **冷记忆**：历史数据，仍可查询但权重低
- **遗忘**：30 天以上未访问 + 低置信度 → 自动删除

### 1.4 记忆存储目录

每个角色的记忆存储在 `~/.suri/runtime/roles/{role_id}/memories/` 目录下：

```
~/.suri/runtime/roles/{role_id}/memories/
  ├── role.db              # SQLite 数据库（结构化记忆 + 消息 + 任务）
  ├── insights/            # 洞察文件（文本记忆）
  │   ├── 2024-01-15_learning.md
  │   └── 2024-01-16_pattern.md
  └── *.md                 # 角色私人长期记忆
```

---

## 二、功能需求

### 2.1 独立存储
- 每个角色拥有独立的 SQLite（`roles/{role_id}/memories/role.db`）
- WAL 模式，支持并发读写
- 别名解析后写入 canonical 目录

### 2.2 数据表

| 表名 | 用途 |
|------|------|
| `memory_facts` | 结构化事实记忆（key-value） |
| `memory_experiences` | 执行任务的经验记录 |
| `memory_patterns` | 识别出的模式和最佳实践 |
| `sessions` | 会话记录（session_id/user_id/start_time/end_time/status） |
| `tasks` | 任务记录（task_id/session_id/requester/target_dept/target_director/status/retry_count） |
| `messages` | 消息记录（message_id/task_id/sender/receiver/body/timestamp） |
| `approvals` | 审批记录（approval_id/report_id/requester/status/token/user_response） |
| `changelogs` | 代码变更审计 |
| `statistics` | 统计事件（tokens/时长/文件等） |
| `experiences` | 经验日志（V2.0 角色进化） |

### 2.3 文本记忆
- 角色私人长期记忆（`memories/*.md`）
- 洞察文件（`memories/insights/*.md`）含 YAML frontmatter
- 按时间倒序排列

### 2.4 查询能力
- 按角色、任务、会话查询消息
- 跨任务聚合（JOIN tasks + messages 按 session_id）
- 经验按标签过滤
- 洞察按 confidence 排序

### 2.5 多用户隔离
- session 级消息过滤
- 用户 ID 绑定到 session

---

## 三、接口定义

### 3.1 订阅事件
- `system.start` → 初始化所有角色的数据库

### 3.2 发布事件
- 不发布事件（纯服务插件）

### 3.3 方法调用（供角色和其他插件调用）

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `get_messages(role_id, limit)` | `role_id: string`, `limit: int` | 消息列表 | 查询角色消息 |
| `get_insights(role_id, days)` | `role_id: string`, `days: int` | 洞察列表 | 查询角色洞察 |
| `get_experiences(role_id, task_id)` | `role_id: string`, `task_id: string` | 经验记录 | 查询角色经验 |
| `get_facts(role_id, key)` | `role_id: string`, `key: string` | 事实值 | 查询结构化事实 |
| `set_fact(role_id, key, value)` | `role_id: string`, `key: string`, `value: any` | 无 | 存储结构化事实 |
| `store_experience(role_id, data)` | `role_id: string`, `data: dict` | 无 | 记录经验 |
| `add_insight(role_id, filepath, body)` | `role_id: string`, `filepath: string`, `body: str` | 无 | 添加洞察文件 |

---

## 四、配置项

```yaml
memory_service:
  wal_mode: true
  default_limit: 50
  insight_ttl_days: 90
  auto_archive: true
  max_facts_per_role: 1000
  max_experiences_per_role: 5000
  forget_threshold_days: 30    # 记忆遗忘天数
  forget_confidence_threshold: 0.3  # 遗忘置信度阈值
```

---

## 五、事件 Payload Schema

### 5.1 订阅事件

#### `system.start`
触发初始化，无特定 payload。

### 5.2 发布事件

本插件不发布事件，纯服务插件。所有交互通过方法调用。

---

## 六、依赖关系

- **上游**：suri_core、config_service（解析角色别名）
- **下游**：所有需要读写记忆的角色和插件，agent_registry（持久化 Agent 状态）
- **可选依赖**：role_learner（从记忆中挖掘学习模式）

---

## 七、生命周期

1. `init()` → 初始化连接池（预留）
2. `start()` → 为所有现有角色初始化数据库表
3. `stop()` → 关闭所有数据库连接
4. `cleanup()` → 释放资源

---

## 八、安全边界

- 禁止跨角色读写（必须通过 role_id 参数）
- 路径解析防注入（禁止 `../`）
- 敏感字段（API Key）不入库
- 文件大小限制（单个洞察文件 ≤ 1MB）

---

## 九、与 Context 层的关系

```
memory_service（持久化层）
    │
    ▼
Context 系统（运行时缓存层）
  ├── Hot Tier（内存）：当前活跃 Task 的完整 Context
  ├── Warm Tier（SQLite）：挂起 Task 的 Context（JSON 序列化）
  └── Cold Tier（磁盘）：已完成 Task 的压缩摘要
            │
            ▼
memory_service（角色长期记忆）
  ├── 事实记忆（key-value 结构化）
  ├── 经验记忆（执行记录 + 满意度）
  └── 模式记忆（最佳实践 + 置信度）
```

- memory_service 存储的是角色**长期积累的记忆**（事实、经验、模式）
- Context 系统存储的是**运行时会话上下文**（当前和历史对话）
- 两者互补：Context 过期或压缩后，关键信息应沉淀到 memory_service