# Suri Agent 数据库 Schema 规范

> 本文档统一定义 suri-agent 所有 SQLite 表的完整结构。所有表按归属插件分组，包含 `CREATE TABLE` 语句、字段说明和索引定义。

---

## 中央数据库（`~/.suri/runtime/suri.db`）

归属：**suri_core**

### `plugins` — 插件注册表

```sql
CREATE TABLE plugins (
    plugin_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    version     TEXT NOT NULL,
    type        TEXT NOT NULL,           -- core / service / execution / capability / access / extension
    path        TEXT NOT NULL,
    status      TEXT DEFAULT 'inactive', -- inactive / active / paused / error / stale
    capabilities TEXT,                   -- JSON array
    manifest    TEXT,                    -- manifest.json 全文
    last_heartbeat TEXT,                 -- ISO 8601
    created_at  TEXT,
    updated_at  TEXT
);

CREATE INDEX idx_plugins_status ON plugins(status);
CREATE INDEX idx_plugins_type   ON plugins(type);
```

### `events` — 事件日志

```sql
CREATE TABLE events (
    event_id    TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    source      TEXT NOT NULL,           -- 发布者 plugin_id / role_id
    target      TEXT,                    -- 定向目标（可选）
    payload     TEXT,                    -- JSON
    priority    TEXT NOT NULL,           -- CRITICAL / HIGH / NORMAL / LOW
    timestamp   TEXT NOT NULL,
    consumed    INTEGER DEFAULT 0        -- 0=未消费 1=已消费
);

CREATE INDEX idx_events_type      ON events(event_type);
CREATE INDEX idx_events_source    ON events(source);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_consumed  ON events(consumed) WHERE consumed = 0;
```

---

归属：**role_comm**

### `messages` — 角色通信消息

```sql
CREATE TABLE messages (
    message_id  TEXT PRIMARY KEY,
    sender      TEXT NOT NULL,
    receiver    TEXT,                    -- NULL 表示广播
    msg_type    TEXT NOT NULL,           -- direct / broadcast / escalation / system
    content     TEXT NOT NULL,
    project_id  TEXT,
    timestamp   TEXT NOT NULL,
    consumed    INTEGER DEFAULT 0,
    ttl         INTEGER DEFAULT 86400    -- 秒，默认 24h
);

CREATE INDEX idx_messages_sender   ON messages(sender);
CREATE INDEX idx_messages_receiver ON messages(receiver);
CREATE INDEX idx_messages_project  ON messages(project_id);
CREATE INDEX idx_messages_consumed ON messages(consumed) WHERE consumed = 0;
```

> **注意**：`framework.md` 中原有的 `messages_comm` 表已删除，与本表合并。`messages` 同时覆盖系统通信记录和角色间通信。

---

归属：**security_service**

### `changes` — 代码变更审计

```sql
CREATE TABLE changes (
    change_id   TEXT PRIMARY KEY,
    changer     TEXT NOT NULL,           -- role_id / user_id / plugin_id
    change_type TEXT NOT NULL,           -- create / modify / delete
    file_path   TEXT NOT NULL,
    old_content TEXT,                    -- 修改前内容（大文件可存 hash）
    new_content TEXT,                    -- 修改后内容
    approval_token TEXT,                 -- 关联审批令牌
    timestamp   TEXT NOT NULL
);

CREATE INDEX idx_changes_changer  ON changes(changer);
CREATE INDEX idx_changes_file     ON changes(file_path);
CREATE INDEX idx_changes_timestamp ON changes(timestamp);
```

### `approval_tokens` — 审批令牌

```sql
CREATE TABLE approval_tokens (
    token       TEXT PRIMARY KEY,
    requester   TEXT NOT NULL,
    operation   TEXT NOT NULL,           -- file_modify / soul_modify / plugin_install / etc.
    resource    TEXT NOT NULL,           -- 目标文件/角色/插件
    expires_at  TEXT NOT NULL,           -- 默认创建后 300 秒
    status      TEXT DEFAULT 'pending',  -- pending / approved / rejected / expired
    decided_by  TEXT,                    -- 审批者
    decided_at  TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX idx_tokens_requester ON approval_tokens(requester);
CREATE INDEX idx_tokens_status    ON approval_tokens(status);
CREATE INDEX idx_tokens_expires   ON approval_tokens(expires_at) WHERE status = 'pending';
```

---

归属：**agent_registry**

### `agents` — Agent 注册表

```sql
CREATE TABLE agents (
    agent_id        TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL,
    task_name       TEXT,
    parent_agent_id TEXT,
    role_id         TEXT NOT NULL,
    status          TEXT DEFAULT 'planning', -- planning / running / blocked / paused / completed / cancelled
    user_id         TEXT NOT NULL,
    plan_id         TEXT,
    created_at      TEXT,
    updated_at      TEXT,
    completed_at    TEXT
);

CREATE INDEX idx_agents_role    ON agents(role_id);
CREATE INDEX idx_agents_status  ON agents(status);
CREATE INDEX idx_agents_user    ON agents(user_id);
CREATE INDEX idx_agents_parent  ON agents(parent_agent_id);
```

### `agent_steps` — Agent 步骤

```sql
CREATE TABLE agent_steps (
    step_id     TEXT,
    agent_id    TEXT NOT NULL,
    step_name   TEXT,
    status      TEXT DEFAULT 'pending', -- pending / in_progress / completed / blocked
    result      TEXT,
    depends_on  TEXT,                   -- JSON array of step_ids
    started_at  TEXT,
    completed_at TEXT,
    PRIMARY KEY (step_id, agent_id)
);

CREATE INDEX idx_steps_agent   ON agent_steps(agent_id);
CREATE INDEX idx_steps_status  ON agent_steps(status);
```

---

## 角色级数据库（`~/.suri/runtime/roles/{role_id}/memories/role.db`）

归属：**memory_service**（每个角色独立一个 SQLite 文件）

### `sessions` — 会话记录

```sql
CREATE TABLE sessions (
    session_id  TEXT PRIMARY KEY,
    agent_id    TEXT,
    user_id     TEXT,
    started_at  TEXT,
    ended_at    TEXT,
    summary     TEXT
);
```

### `tasks` — 任务记录

```sql
CREATE TABLE tasks (
    task_id     TEXT PRIMARY KEY,
    session_id  TEXT,
    description TEXT,
    status      TEXT,                   -- completed / failed / timeout
    result      TEXT,
    started_at  TEXT,
    ended_at    TEXT
);

CREATE INDEX idx_tasks_session ON tasks(session_id);
```

### `messages` — 角色会话消息

```sql
CREATE TABLE messages (
    message_id  TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,          -- 'user' 或 role_id
    content     TEXT NOT NULL,
    timestamp   TEXT
);

CREATE INDEX idx_messages_session ON messages(session_id);
```

### `approvals` — 角色相关审批

```sql
CREATE TABLE approvals (
    approval_id TEXT PRIMARY KEY,
    token       TEXT NOT NULL,
    type        TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    requester   TEXT,
    timestamp   TEXT
);
```

### `changelogs` — 角色感知的代码变更

```sql
CREATE TABLE changelogs (
    log_id      TEXT PRIMARY KEY,
    change_id   TEXT,                   -- 关联中央 changes 表
    description TEXT,
    timestamp   TEXT
);
```

### `statistics` — 角色运行统计

```sql
CREATE TABLE statistics (
    stat_id     TEXT PRIMARY KEY,
    metric      TEXT NOT NULL,          -- task_count / token_used / avg_latency
    value       REAL NOT NULL,
    timestamp   TEXT
);
```

### `experiences` — 经验记录（RoleLearner 分析源）

```sql
CREATE TABLE experiences (
    experience_id   TEXT PRIMARY KEY,
    task_id         TEXT,
    description     TEXT,
    outcome         TEXT,               -- success / failure
    tools_used      TEXT,               -- JSON array
    duration_ms     INTEGER,
    timestamp       TEXT
);

CREATE INDEX idx_experiences_outcome ON experiences(outcome);
CREATE INDEX idx_experiences_timestamp ON experiences(timestamp);
```

---

## 已删除的表

| 表名 | 原归属 | 删除原因 |
|------|--------|----------|
| `roles` | framework.md（未明确归属） | role_manager 使用文件系统（`soul.md`）存储角色定义，不使用 SQLite 表 |
| `config` | framework.md（未明确归属） | config_service 使用 `~/.suri/config.json` 文件存储配置，不使用 SQLite 表 |
| `messages_comm` | framework.md | 与 `messages` 表（role_comm）重复，合并 |

---

## 设计原则

1. **表归属明确**：每张表有且只有一个归属插件，该插件负责 schema 演进和迁移
2. **角色隔离**：角色级数据（memories/insights/skills）存储在角色独立目录中，不混入中央数据库
3. **审计不可改**：`changes` 和 `events` 表写入后不允许 UPDATE/DELETE，仅允许 INSERT 和 SELECT
4. **索引策略**：所有外键、查询字段、状态过滤字段均有索引
