# memory_service 插件 PRD

## 定位

角色级独立记忆存储插件，为每个角色提供 SQLite 数据库 + 文本记忆文件的管理服务。是系统持久化层的核心。

## 功能需求

### 1. 独立存储
- 每个角色拥有独立的 SQLite（`roles/{role_id}/memories/role.db`）
- WAL 模式，支持并发读写
- 别名解析后写入 canonical 目录

### 2. 数据表

- `sessions` — 会话记录（session_id/user_id/start_time/end_time/status）
- `tasks` — 任务记录（task_id/session_id/requester/target_dept/target_director/status/retry_count）
- `messages` — 消息记录（message_id/task_id/sender/receiver/body/timestamp）
- `approvals` — 审批记录（approval_id/report_id/requester/status/token/user_response）
- `changelogs` — 代码变更审计
- `statistics` — 统计事件（tokens/时长/文件等）
- `experiences` — 经验日志（V2.0 角色进化）

### 3. 文本记忆
- 角色私人长期记忆（`memories/*.md`）
- 洞察文件（`memories/insights/*.md`）含 YAML frontmatter
- 按时间倒序排列

### 4. 查询能力
- 按角色、任务、会话查询消息
- 跨任务聚合（JOIN tasks + messages 按 session_id）
- 经验按标签过滤
- 洞察按 confidence 排序

### 5. 多用户隔离
- session 级消息过滤
- 用户 ID 绑定到 session

## 接口定义

### 订阅事件
- `system.start` → 初始化所有角色的数据库

### 发布事件
- 不发布事件（纯服务插件）

## 配置项

```yaml
memory_service:
  wal_mode: true
  default_limit: 50
  insight_ttl_days: 90
  auto_archive: true
```

## 事件 Payload Schema

### 订阅事件

#### `system.start`
触发初始化，无特定 payload。

### 发布事件

本插件不发布事件，纯服务插件。所有交互通过方法调用。

**查询接口参数**（非事件，供角色调用）：

| 方法 | 参数 | 返回 |
|------|------|------|
| `get_messages(role_id, limit)` | `role_id: string`, `limit: int` | 消息列表 |
| `get_insights(role_id, days)` | `role_id: string`, `days: int` | 洞察列表 |
| `get_experiences(role_id, task_id)` | `role_id: string`, `task_id: string` | 经验记录 |

## 依赖关系

- 上游：suri_core、config_service（解析角色别名）
- 下游：所有需要读写记忆的角色和插件，agent_registry（持久化 Agent 状态）

## 生命周期

1. `init()` → 初始化连接池（预留）
2. `start()` → 为所有现有角色初始化数据库表
3. `stop()` → 关闭所有数据库连接
4. `cleanup()` → 释放资源

## 安全边界

- 禁止跨角色读写（必须通过 role_id 参数）
- 路径解析防注入（禁止 `../`）
- 敏感字段（API Key）不入库
