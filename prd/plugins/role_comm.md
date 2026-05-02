# role_comm 插件 PRD

## 定位

角色间消息通信服务。提供点对点、广播消息能力，SQLite 持久化队列，通信权限规则，消息留存策略。

**关键约束**：只做消息投递和存储，不解析消息业务内容，不决定消息处理逻辑。

## 功能需求

### 1. 消息发送（Send）

- 点对点：`send(sender, receiver, msg_type, content, task_id)`
- 广播：`broadcast(sender, content, msg_type)` — receiver="broadcast"
- 求助：`request_help(sender, content, task_id)` — 快捷方法，receiver="suri"

### 2. 消息消费（Consume）

- `consume(receiver, limit=50)` → 获取消息并原子标记已消费
- `peek(receiver, limit=50)` → 只看不消费
- `get_unread_count(receiver)` → 未读消息数
- 广播消息可被所有消费者收到（不标记单消费者消费）

### 3. SQLite 持久化队列

- 消息存 SQLite，支持崩溃恢复
- WAL 模式支持并发读写
- `consumed` 字段标记消费状态
- 定期清理过期消息

### 4. 通信权限规则

> 部门概念已移除，简化为"角色间通信权限矩阵"。

| 场景 | 是否允许 | 通道 |
|------|---------|------|
| 自己 → 自己 | ✅ | self |
| 同工作组 | ✅ | group |
| 角色 ↔ suri | ✅ | private |
| 跨工作组 | ✅（需审批或双方为管理员）| private_with_cc |
| 广播 | ✅ | broadcast |
| 审批/回流 | ✅（抄送 suri）| security_chain |

### 5. 消息留存策略

| 消息类型 | 留存天数 |
|----------|---------|
| approval | 90 |
| task | 30 |
| notify | 30 |
| escalation | 90 |
| status_update | 7 |
| request_help | 30 |
| completion | 30 |

### 6. 消息格式校验

必填字段：`message_id`, `sender`, `receiver`, `msg_type`, `content`, `timestamp`, `priority`

合法 `msg_type`：task / approval / notify / escalation / status_update / request_help / completion

合法 `priority`：high / normal / low

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `role.message` | 任意角色/插件 | 存储并路由消息 |
| `role.broadcast` | 任意角色/插件 | 广播消息 |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `role.message_received` | receiver 角色 | 新消息到达 |
| `role.message_delivered` | sender 角色 | 消息已投递 |
| `role.message_rejected` | sender 角色 | 消息被拒绝（权限不足） |

### 方法

```python
class RoleComm:
    async def send(self, sender: str, receiver: str, msg_type: str,
                   content: str, task_id: str = None, priority: str = "normal") -> bool
    async def broadcast(self, sender: str, content: str, 
                        msg_type: str = "notify") -> bool
    async def request_help(self, sender: str, content: str,
                           task_id: str = None) -> bool
    def consume(self, receiver: str, limit: int = 50) -> List[RoleMessage]
    def peek(self, receiver: str, limit: int = 50) -> List[RoleMessage]
    def get_unread_count(self, receiver: str) -> int
    def cleanup_old_messages(self, max_age_days: int = 30) -> int
```

## 数据模型

```python
@dataclass
class RoleMessage:
    msg_id: str
    sender: str
    receiver: str              # 或 "broadcast"
    msg_type: str
    content: str
    task_id: Optional[str]
    agent_id: Optional[str]
    priority: str              # high | normal | low
    timestamp: str
    consumed: bool = False
```

## 事件 Payload Schema

### 订阅事件

#### `role.message`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `msg_id` | string | 是 | 消息 ID |
| `sender` | string | 是 | 发送者角色 ID |
| `receiver` | string | 是 | 接收者角色 ID 或 "broadcast" |
| `msg_type` | string | 是 | task / approval / notify / escalation / status_update / request_help / completion |
| `content` | string | 是 | 消息内容 |
| `task_id` | string | 否 | 关联任务 ID |
| `priority` | string | 否 | high / normal / low，默认 normal |

#### `role.broadcast`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sender` | string | 是 | 发送者 |
| `content` | string | 是 | 广播内容 |
| `msg_type` | string | 否 | 默认 notify |
| `ttl` | integer | 否 | 存活时间（秒） |

### 发布事件

#### `role.message_received`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `receiver` | string | 是 | 接收者角色 ID |
| `msg_id` | string | 是 | 消息 ID |
| `sender` | string | 是 | 发送者 |
| `content` | string | 是 | 内容摘要 |
| `unread_count` | integer | 是 | 接收者未读消息数 |

#### `role.message_delivered`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `msg_id` | string | 是 | 消息 ID |
| `receiver` | string | 是 | 接收者 |
| `delivered_at` | string | 是 | 投递时间 |

#### `role.message_rejected`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `msg_id` | string | 是 | 消息 ID |
| `sender` | string | 是 | 发送者 |
| `receiver` | string | 是 | 接收者 |
| `reject_reason` | string | 是 | 拒绝原因：permission_denied / invalid_format / size_exceeded |

## 配置项

```yaml
role_comm:
  max_message_size: 65536       # 单条消息最大字节数
  default_retention_days: 30
  retention_policy:
    approval: 90
    task: 30
    notify: 30
    escalation: 90
    status_update: 7
    request_help: 30
    completion: 30
  broadcast_ttl: 86400          # 广播消息存活时间（秒）
  enable_delivery_receipt: true # 投递回执
  permission_mode: "workgroup"  # workgroup | role_level | open
```

## 依赖关系

- 上游：suri_core（EventBus）

### 与 access 的边界

| 维度 | role_comm | access |
|------|-----------|--------|
| **通信范围** | 角色间内部通信 | 用户 ↔ 系统外部通信 |
| **持久化** | SQLite 持久队列 | 通道即时投递 |
| **典型场景** | 角色 A 请求角色 B 协助 | 用户在 Telegram 群 @Project Director |
| **映射关系** | Telegram 群消息 → 路由到角色 → 角色回复 → 通过 access 返回群 | access 接收外部消息，可生成 role_comm 消息记录 |
| **关键原则** | 外部消息是内部通信的「投影」| access 不解析业务内容，只负责通道转换 |
- 下游：任意角色/插件（消息消费者）

## SQLite 表结构

```sql
CREATE TABLE messages (
    msg_id TEXT PRIMARY KEY,
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    msg_type TEXT NOT NULL,
    content TEXT NOT NULL,
    task_id TEXT,
    agent_id TEXT,
    priority TEXT DEFAULT 'normal',
    timestamp TEXT NOT NULL,
    consumed INTEGER DEFAULT 0
);

CREATE INDEX idx_messages_receiver ON messages(receiver, consumed, timestamp);
CREATE INDEX idx_messages_sender ON messages(sender, timestamp);
CREATE INDEX idx_messages_task ON messages(task_id);
```

## 生命周期

1. `init()` → 连接 SQLite 消息库、加载未读消息统计
2. `start()` → 标记就绪
3. `stop()` → 停止消息处理
4. `cleanup()` → 清理过期消息、关闭数据库连接

## 安全边界

- 消息大小超过上限时拒绝并返回错误事件
- 权限不足的消息被拒绝，记录审计日志
- 广播消息不标记消费，避免单点消费导致其他接收者收不到
- 定期清理过期消息，防止存储膨胀
- **核心原则**：不解析消息内容，只做投递和存储
