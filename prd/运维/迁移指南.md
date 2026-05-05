# 数据库迁移指南

> 指导 suri-agent 数据库 Schema 变更的管理流程。

---

## 一、迁移脚本目录

```
agent_framework/migrations/
├── 001_initial.sql       # 初始 Schema
├── 002_agents.sql        # Agent 注册表
├── 003_{description}.sql # 按版本号命名
├── ...
└── runner.py             # 迁移执行器
```

**命名规则**：`{序号}_{描述}.sql`，序号从 001 开始递增。

---

## 二、迁移脚本格式

```sql
-- 001_initial.sql
-- 描述：初始数据库 Schema

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload TEXT,
    priority INTEGER DEFAULT 0,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    source TEXT NOT NULL,
    payload TEXT,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL
);

INSERT OR IGNORE INTO schema_version (version, applied_at) 
VALUES (1, strftime('%s', 'now'));
```

---

## 三、迁移执行流程

```
启动时 suri_core bootstrap
    │
    ├─ 读取 schema_version 表，获取当前版本号
    │
    ├─ 扫描 migrations/ 目录，获取所有 .sql 文件
    │
    ├─ 按序号排序，找出未执行的迁移
    │
    ├─ 逐个执行迁移脚本（每条 SQL 在一个事务中）
    │
    ├─ 迁移成功 → 更新 schema_version
    │
    └─ 迁移失败 → 回滚事务，记录错误日志，阻止启动
```

---

## 四、开发新迁移

1. 创建 `{序号}_{描述}.sql` 文件
2. 编写 SQL（必须幂等：使用 `IF NOT EXISTS` / `CREATE OR REPLACE`）
3. 提交代码

```bash
# 示例：新增索引
# 文件：003_add_message_idx.sql
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(from_role, to_role);
INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (3, strftime('%s', 'now'));
```

---

## 五、回滚策略

- 不支持自动回滚（SQLite 迁移全部向前）
- 回滚需手动编写 `rollback_{序号}.sql` 脚本
- 生产环境变更前先备份 `~/.suri/runtime/suri.db`