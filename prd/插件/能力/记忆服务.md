# memory_service 插件 PRD

## 定位

角色级记忆存储插件，为每个角色提供三层 SQLite 数据库（Ad-hoc / Project / Global） + 文本记忆文件的管理服务。是系统持久化层的核心。

---

## 一、记忆架构（Architecture Overview）

### 1.1 三层记忆模型

根据 ARCHITECTURE-ANALYSIS.md 的上下文隔离设计，角色的记忆分为三层：

```
┌──────────────────────────────────────────────────────────────┐
│  角色的记忆分为三层，严格隔离                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ① Ad-hoc 层（临时会话）                                 │  │
│  │  角色与 suri 之间的一次性简单对话                       │  │
│  │  存储：adhoc/{session_id}/role.db（仅 messages 表）     │  │
│  │  特点：聊完归档、7天自动清理、不沉淀为长期记忆           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ② Project 层（项目工作）                                │  │
│  │  角色在特定项目中的持续工作上下文                        │  │
│  │  存储：projects/{project_id}/role.db                   │  │
│  │  特点：有完整记忆系统（messages + facts + experiences）  │  │
│  │  项目切换时保存 context_snapshot + 加载新项目数据        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ ③ Global 层（全局记忆）                                 │  │
│  │  角色的跨项目通用知识                                    │  │
│  │  存储：global/role.db（通用 facts + 通用 experiences）  │  │
│  │  特点：所有项目共享、沉淀通用技能、永久保留（受遗忘约束）  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 记忆存储目录

```
~/.suri/runtime/roles/{role_id}/
├── adhoc/                         # ★ 临时会话（Ad-hoc 层）
│   ├── {session_id}/
│   │   ├── role.db               # 仅 messages 表（极简）
│   │   └── context.md
│   └── ...
│
├── projects/                      # ★ 项目级数据（Project 层）
│   ├── {project_id}/
│   │   ├── role.db               # 完整记忆系统
│   │   ├── context.md            # 项目上下文摘要
│   │   ├── insights/             # 洞察文件
│   │   └── reference/            # 项目参考资料
│   └── ...
│
├── global/                        # ★ 全局记忆（Global 层）
│   ├── role.db                   # 通用事实 + 通用经验
│   ├── insights/
│   └── memories/
```

### 1.3 三层数据库 Schema 对比

#### Ad-hoc 层数据库（极简，聊完即清理）

```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    sender TEXT,
    receiver TEXT,
    body TEXT,
    timestamp TIMESTAMP
);
-- 注意：无 memory_facts / memory_experiences / memory_patterns 表
-- 临时对话不沉淀为长期记忆，避免污染角色知识库
```

#### Project 层数据库（完整记忆系统）

```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    task_id TEXT,
    session_id TEXT,
    sender TEXT,
    receiver TEXT,
    body TEXT,
    timestamp TIMESTAMP
);

CREATE TABLE memory_facts (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE,
    value TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    access_count INTEGER DEFAULT 0
);

CREATE TABLE memory_experiences (
    id TEXT PRIMARY KEY,
    task_type TEXT,
    context TEXT,
    actions TEXT,       -- JSON
    result TEXT,
    satisfaction REAL,
    created_at TIMESTAMP
);

CREATE TABLE memory_patterns (
    id TEXT PRIMARY KEY,
    pattern TEXT,
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 1,
    source TEXT,
    created_at TIMESTAMP
);

-- 项目上下文快照（用于快速恢复）
CREATE TABLE context_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    task_id TEXT,
    summary TEXT,
    key_facts TEXT,         -- JSON
    active_tools TEXT,      -- JSON
    created_at TIMESTAMP,
    expires_at TIMESTAMP
);
```

#### Global 层数据库（跨项目通用知识）

```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    sender TEXT,
    receiver TEXT,
    body TEXT,
    timestamp TIMESTAMP
);

CREATE TABLE memory_facts (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE,
    value TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    access_count INTEGER DEFAULT 0
);

CREATE TABLE memory_experiences (
    id TEXT PRIMARY KEY,
    task_type TEXT,
    context TEXT,
    actions TEXT,
    result TEXT,
    satisfaction REAL,
    created_at TIMESTAMP
);
```

---

## 二、功能需求

### 2.1 三层独立存储
- 每个角色拥有三层独立的 SQLite 存储
- Ad-hoc 层在 `roles/{role_id}/adhoc/{session_id}/role.db`
- Project 层在 `roles/{role_id}/projects/{project_id}/role.db`
- Global 层在 `roles/{role_id}/global/role.db`
- 所有 DB 使用 WAL 模式，支持并发读写

### 2.2 上下文切换能力

```
角色切换上下文时（例如从 Ad-hoc 到 Project，或 Project 到 Project）：
  1. 保存当前上下文的 context_snapshot（摘要 + 关键事实）
  2. 发布 project.context_switched 事件
  3. 清除运行时缓存中旧上下文的数据
  4. 加载新上下文的 context.md + 最近洞察
```

### 2.3 Ad-hoc 会话生命周期管理

```
创建：suri 或角色发起临时对话时，memory_service.create_adhoc_session()
运行：消息追加到 adhoc/{session_id}/role.db
过期：7 天以上未访问的 ad-hoc 会话自动清理
清理：clean_expired_adhoc(role_id, max_age_days=7)
```

### 2.4 查询能力

- 按角色 + 会话查询消息（Ad-hoc）
- 按角色 + 项目查询消息/事实/经验/洞察（Project）
- 按角色查询全局通用知识（Global）
- 跨项目聚合经验（管理员视角）

### 2.5 文本记忆

- 角色私人长期记忆（`global/memories/*.md`）
- 项目专属洞察（`projects/{id}/insights/*.md`）
- 洞察文件按时间倒序排列，含 YAML frontmatter

---

## 三、接口定义

### 3.1 订阅事件

| 事件 | 行为 |
|------|------|
| `system.started` | 初始化所有角色的三层数据库 |
| `project.created` | 创建项目级 role.db |
| `project.role_joined` | 角色加入项目时初始化项目记忆 |
| `project.context_switched` | 角色切换项目时加载新上下文 |

### 3.2 发布事件

本插件不主动发布事件（纯服务插件）。

### 3.3 方法调用（供角色和其他插件调用）

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `get_messages(role_id, session_id=None, project_id=None, limit=50)` | `role_id`, `session_id` 或 `project_id` | 消息列表 | 三层查询：session_id → Ad-hoc，project_id → Project，无 → Global |
| `get_facts(role_id, project_id=None, key=None)` | `role_id`, `project_id`, `key` | 事实列表 | 按项目或全局查询事实 |
| `set_fact(role_id, project_id, key, value)` | `role_id`, `project_id`, `key`, `value` | 无 | 存储项目级事实 |
| `set_global_fact(role_id, key, value)` | `role_id`, `key`, `value` | 无 | 存储全局事实 |
| `store_experience(role_id, project_id, data)` | `role_id`, `project_id`, `data` | 无 | 记录项目经验 |
| `get_insights(role_id, project_id=None, days=7)` | `role_id`, `project_id`, `days` | 洞察列表 | 按项目查询洞察 |
| `create_adhoc_session(role_id)` | `role_id` | session_id | 创建临时会话 |
| `clean_expired_adhoc(role_id, max_age_days=7)` | `role_id`, `max_age_days` | 清理数量 | 清理过期 ad-hoc 会话 |
| `save_context_snapshot(role_id, project_id, task_id, ...)` | `role_id`, `project_id`, `task_id`, `summary`, `key_facts` | snapshot_id | 保存项目上下文快照 |
| `get_context_snapshot(role_id, project_id, task_id)` | `role_id`, `project_id`, `task_id` | snapshot | 获取上下文快照 |

---

## 四、配置项

```yaml
memory_service:
  wal_mode: true
  default_limit: 50
  insight_ttl_days: 90
  auto_archive: true
  max_facts_per_project: 1000
  max_experiences_per_project: 5000
  adhoc_ttl_days: 7              # Ad-hoc 会话保留天数
  forget_threshold_days: 30      # 全局记忆遗忘天数
  forget_confidence_threshold: 0.3
  context_snapshot_ttl_hours: 48 # 上下文快照过期时间
```

---

## 五、依赖关系

- **上游**：suri_core、config_service、role_manager（获取角色目录路径）
- **下游**：所有需要读写记忆的角色和插件、agent_registry
- **可选依赖**：role_learner（从记忆中挖掘学习模式）

---

## 六、生命周期

1. `init()` → 初始化连接池（预留）
2. `start()` → 为所有现有角色初始化三层数据库
3. `stop()` → 关闭所有数据库连接
4. `cleanup()` → 清理过期 ad-hoc 会话 + 释放资源

---

## 七、安全边界

- 禁止跨角色读写（必须通过 role_id 参数）
- 禁止跨项目读写（必须通过 project_id 参数，Global 层除外）
- 路径解析防注入（禁止 `../`）
- 敏感字段（API Key）不入库
- 文件大小限制（单个洞察文件 ≤ 1MB）
- Ad-hoc 会话超 7 天自动清理

---

## 八、与三清单体系的关系

```python
# memory_service 不与三清单直接交互，但为三清单提供数据源
# - Role Registry 的 active_projects 列表中各项目的最近活动时间
# - Plugin Registry 不依赖 memory_service
# - Tool Registry 的调用统计可在 Project 层中查询

# memory_service 的数据可以被 suri 的每日分析流程使用：
suri 每日分析流程：
  1. 读取三清单全量数据
  2. 查 memory_service 获取角色在项目中的活跃度
  3. 交叉分析能力缺口
  4. 生成优化建议报告