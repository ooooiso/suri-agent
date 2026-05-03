# role_comm 插件 PRD

> 角色间消息通信服务。提供**自然语言消息**的点对点/广播能力，按 **session_id** 隔离不同对话上下文。

---

## 一、定位

role_comm 是角色的"信箱系统"：

| 角色 | 说明 |
|------|------|
| **信箱** | 存储和转发角色间的自然语言消息 |
| **路由** | 消息按 receiver 投递，按 session_id 分组 |
| **通知** | 新消息到达时发布事件，触发接收角色处理 |

**关键约束**：
- ❌ 不解析消息业务内容（角色 LLM 自己理解）
- ❌ 不提供方法调用 API（全部通过事件）
- ✅ 只做存储、转发、分组

---

## 二、纯事件驱动架构

```
角色 A（发送方）
    │
    │ 调 LLM → LLM 决定"给角色B发消息"
    │ Agent 代码识别发消息意图 → 发布事件
    ▼
event_bus.publish("role.message", {
    from_role: "designer_A",
    to_role: "dev_role",
    session_id: "dev↔designer_A__project_X_login",
    content: "按钮从蓝色改成绿色，字体16→20px"
})
    │
    ▼
┌──────────────────────────────────────────────┐
│              role_comm                        │
│                                               │
│  1. 收到 role.message 事件                    │
│  2. 存储到 SQLite（含 session_id）             │
│  3. 发布 role.message_received 事件           │
│                                               │
│  存储格式：                                    │
│    msg_id | session_id | from | to | content  │
│    | summary | timestamp                     │
└──────────────┬───────────────────────────────┘
               │
               ▼
event_bus.publish("role.message_received", {
    receiver: "dev_role",
    session_id: "dev↔designer_A__project_X_login",
    unread_count: 3
})
    │
    ▼
角色 B（接收方）
    │
    │ 收到事件 → 标记"有未读消息"（内存计数器+1）
    │ 下次空闲时 → 调 LLM 处理
    │ LLM context 中：该 session 的历史 + 新消息
    ▼
event_bus.publish("role.message", {  // B 回复 A
    from_role: "dev_role",
    to_role: "designer_A",
    session_id: "dev↔designer_A__project_X_login",
    content: "按钮已改好，蓝色→绿色"
})
```

### 2.1 role_comm 订阅的事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `role.message` | 任意角色 | 存储消息 → 发布 `role.message_received` |

### 2.2 role_comm 发布的事件

| 事件 | 目标 | Payload |
|------|------|---------|
| `role.message_received` | `receiver` 角色 | `{receiver, session_id, unread_count}` |
| `role.messages_batch` | `receiver` 角色 | `{receiver, sessions: {session_id: [msgs]}}`（按 session 分组） |

### 2.3 角色查询消息的事件（按需）

| 事件 | 来源 | 响应事件 | 说明 |
|------|------|---------|------|
| `role.messages_query` | 任意角色 | `role.messages_result` | 查询未读消息 |
| `role.messages_consume` | 任意角色 | `role.messages_consumed` | 消费（标记已读）特定 session 的消息 |
| `role.messages_summary` | 任意角色 | `role.messages_summary_result` | 获取消息摘要 |

---

## 三、关键设计：session_id 隔离对话上下文

### 3.1 每个消息携带 session_id

```python
# 角色 A 发消息时，消息体携带 session_id
{
    "msg_id": "uuid-xxx",
    "from_role": "designer_A",
    "to_role": "dev_role",
    "session_id": "dev↔designer_A__project_X_login",
    "content": "按钮从蓝色改成绿色，字体16→20px",
    "summary": None,       # 自动生成（长消息时）
    "timestamp": "...",
    "reply_to": None       # 回复链
}
```

### 3.2 session_id 的生成规则

```
session_id = "{role_A}↔{role_B}__{project}_{topic}"

示例：
  "dev↔designer_A__project_X_login"     # 项目X登录页的开发↔设计师
  "dev↔designer_B__project_Y_home"      # 项目Y首页的开发↔设计师
  "dev↔suri__upgrade_code_tool"          # suri 安排开发升级插件
  "suri↔user_甲__project_Z"              # suri 和用户的聊天会话
```

**谁决定 session_id？**
- 发送方 Agent 在 LLM 输出中识别出"会话目标"
- Agent 代码：check session 是否存在，不存在则创建
- session_id 由 `from_role` + `to_role` + 业务上下文拼接

### 3.3 角色看到的未读消息（按 session 分组）

```
dev_role 查询未读消息 → 返回值：

{
  "sessions": {
    "dev↔designer_A__project_X_login": {
      "unread_count": 3,
      "messages": [
        {"from": "designer_A", "content": "按钮改绿色", "summary": None},
        {"from": "designer_A", "content": "字体16→20", "summary": None},
        {"from": "designer_A", "content": "布局左右改上下", "summary": None}
      ]
    },
    "dev↔suri__upgrade_code_tool": {
      "unread_count": 1,
      "messages": [
        {"from": "suri", "content": "需要升级code_tool插件...", "summary": "升级code_tool插件"}
      ]
    }
  }
}
```

### 3.4 角色调 LLM 时的 context 构建

```
dev_role 有空 → 决定处理 "dev↔designer_A" 会话

构建 context：
  system_layer = dev_role 的 soul + 技能（固定）
  session_layer = project_X_login 的业务目标
  task_layer = 当前任务状态
  history_layer = [之前的完整对话历史...] + [3 条未读新消息]
  memory_layer = 按需检索

LLM 调用结果：
  → 理解 3 条消息
  → 执行改代码
  → 回复设计师
  → 1 次调用处理完 3 条消息

3 条消息 = 1 次 LLM 调用（不是 3 次）
```

---

## 四、消息压缩（节约 Token）

### 4.1 自动摘要

```python
# 消息存储时，如果 content 超过阈值，自动生成摘要
SUMMARY_CONFIG = {
    "threshold_chars": 500,       # 超过 500 字符生成摘要
    "summary_model": "cheapest",  # 用最便宜的模型生成
    "max_summary_chars": 100,     # 摘要控制在 100 字符
}
```

**调用 LLM 时默认只加载摘要**：

```
角色 B 的 history_layer：
  ┌────────────────────────────────────┐
  │ 设计师说（摘要）："修改登录页设计"   │
  │ 设计师说（摘要）："按钮颜色改绿色"   │
  │ 设计师说："字体也改到20px"（短消息，不解）│
  └────────────────────────────────────┘

角色 B 如果需要看完整内容：
  → 发布 role.messages_query 事件
  → role_comm 返回完整 content
  → 只在需要时加载，不走 LLM context
```

### 4.2 按 session 批量处理

```
配置项：
  role_comm:
    process_mode: "event_driven"
    batch_window_ms: 2000          # 收到事件后等 2 秒（攒多条）
    max_batch_size: 5              # 或攒够 5 条再处理

效果：
  designer 连续发 3 条消息（1 秒内）：
    t0: 消息1 → dev_role 收到事件 → 开始 2 秒倒计时
    t0.5: 消息2 → 攒着
    t1: 消息3 → 攒着
    t2: 倒计时结束 → 3 条一起进 LLM → 1 次调用
```

---

## 五、数据模型

```python
@dataclass
class RoleMessage:
    msg_id: str
    from_role: str
    to_role: str
    session_id: str              # 会话标识（核心字段）
    content: str                 # 自然语言消息内容
    summary: Optional[str]       # 自动生成的摘要
    timestamp: float
    consumed: bool = False       # 是否已被消费
    reply_to: Optional[str] = None  # 回复链
```

---

## 六、SQLite 表结构

```sql
CREATE TABLE messages (
    msg_id TEXT PRIMARY KEY,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    session_id TEXT NOT NULL,        -- 会话标识
    content TEXT NOT NULL,           -- 自然语言消息
    summary TEXT,                    -- 摘要（长消息自动生成）
    timestamp REAL NOT NULL,
    consumed INTEGER DEFAULT 0,
    reply_to TEXT
);

CREATE INDEX idx_messages_session ON messages(session_id, consumed, timestamp);
CREATE INDEX idx_messages_receiver ON messages(to_role, consumed, timestamp);
CREATE INDEX idx_messages_from ON messages(from_role, timestamp);
```

---

## 七、角色通信的完整 Token 消耗模型

```
角色 A（设计师）→ 角色 B（开发）的完整链路

┌──────────────────────────────────────────────┐
│ 步骤 1: 设计师调 LLM                          │
│   ├─ LLM 调用：1 次                           │
│   ├─ Token 消耗：1~3K（正常对话中的增量）      │
│   └─ LLM 决定：发消息给开发                    │
├──────────────────────────────────────────────┤
│ 步骤 2: 事件传递（不走 LLM）                   │
│   ├─ event_bus.publish("role.message")        │
│   ├─ role_comm 存储到 SQLite                  │
│   ├─ event_bus.publish("role.message_received")│
│   └─ Token 消耗：0                            │
├──────────────────────────────────────────────┤
│ 步骤 3: 开发收到通知（不走 LLM）                │
│   ├─ 开发 Agent 标记"有未读消息"               │
│   └─ Token 消耗：0                            │
├──────────────────────────────────────────────┤
│ 步骤 4: 开发调 LLM 处理                        │
│   ├─ LLM 调用：1 次                           │
│   ├─ Token 消耗：3~10K（看任务复杂度）          │
│   ├─ 批量：3 条消息可一次处理，还是 1 次调用     │
│   └─ LLM 决定：改代码 + 回复设计师              │
├──────────────────────────────────────────────┤
│ 总计：2 次 LLM 调用                            │
│       最低 4K token，最高 13K token           │
│       这是角色通信的不可压缩成本                │
└──────────────────────────────────────────────┘

优化空间：
  多条消息批量处理 → 仍然 2 次 LLM 调用（不增加）
  消息摘要 → LLM 只看 summary，不看全文
  context 压缩 → history 不膨胀
  A 不需要单独确认消息 → 省去额外 1 次 LLM
```

---

## 八、边界设计

### 8.1 角色 vs 用户通信

```
角色 ↔ 角色：走 role_comm（事件驱动）
  设计师 → role.message → role_comm → role.message_received → 开发

角色 ↔ 用户：走 session-hub（access 层）
  用户 → session-hub → 路由到角色 → 角色 LLM 处理 → session-hub → 用户

角色不直接和用户通信，
角色之间的对话用户不可见（除非角色主动汇报给 suri）。
```

### 8.2 角色 vs 插件通信

```
角色 → 插件：走工具调用（不走 role_comm）
  角色 LLM 返回 tool_call → Agent 执行 → 事件 → 插件返回结果
  不经过 role_comm，不浪费 token

角色 ↔ 角色：走 role_comm（自然语言）
  设计师说"改颜色"→ 开发自己理解
  插件听不懂"改颜色"，插件只理解 tool_call
```

### 8.3 消息留存策略

| 场景 | 留存时间 | 说明 |
|------|---------|------|
| 活跃 session | 无限期 | 角色还在对话 |
| 非活跃 session | 7 天 | 超过 7 天无新消息 |
| 已完成的 session | 30 天 | 任务完成后保留 30 天 |

---

## 九、配置项

```yaml
role_comm:
  # 事件驱动配置
  process_mode: "event_driven"    # event_driven | polling
  batch_window_ms: 2000           # 攒消息窗口（毫秒）
  max_batch_size: 5               # 最大批量处理条数
  
  # 消息压缩
  summary:
    enabled: true
    threshold_chars: 500           # 超过此长度自动摘要
    max_summary_chars: 100         # 摘要最大长度
  
  # 留存
  retention_days:
    active: 0                     # 活跃会话不删除
    inactive: 7                   # 非活跃 7 天清除
    completed: 30                 # 已完成 30 天清除
  
  # 事件通知
  notify_on_receive: true         # 收到新消息时发布事件
```

---

## 十、迭代规划

| 迭代 | 内容 | 状态 |
|------|------|------|
| 迭代 1 | 基础消息存储、点对点投递 | ✅ 已实现 |
| 迭代 2 | **session_id 支持**（按会话分组、隔离上下文） | 📋 规划中 |
| 迭代 3 | **事件驱动**（纯事件化、去除方法调用） | 📋 规划中 |
| 迭代 4 | **消息摘要**（长消息自动摘要、按需加载全文） | 📋 规划中 |
| 迭代 5 | **批量处理**（batch_window_ms + max_batch_size） | 📋 规划中 |