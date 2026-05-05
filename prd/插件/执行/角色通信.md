# role_comm 插件 PRD

> 角色间消息通信服务。提供**自然语言消息**的点对点/广播能力，按 **dialog_id**（原 session_id，参见下方说明）隔离不同对话上下文。

---

## 一、定位

role_comm 是角色的"信箱系统"：

| 角色 | 说明 |
|------|------|
| **信箱** | 存储和转发角色间的自然语言消息 |
| **路由** | 消息按 receiver 投递，按 dialog_id 分组 |
| **通知** | 新消息到达时发布事件，触发接收角色处理 |

**关键命名规范**：
- `dialog_id` = 角色间通信的话题标识（role_comm 使用）
- `session_id` = 用户与系统的会话标识（session-hub 使用）
- **两个概念不同**：dialog_id 是"角色对话话题"，session_id 是"用户连接会话"

**关键约束**：
- ❌ 不解析消息业务内容（角色 LLM 自己理解）
- ❌ 不提供方法调用 API（全部通过事件）
- ✅ 只做存储、转发、分组

---

## 二、纯事件驱动架构

### 2.1 发消息流程（含意图识别）

```
角色 A（发送方）
    │
    │ 方式一（推荐）：LLM function calling
    │   LLM 返回结构化调用：
    │   {"function": "send_message", "args": {"to": "dev_role", "content": "修改按钮颜色"}}
    │   → Agent 代码直接解析 → 发布 role.message 事件
    │
    │ 方式二（降级）：自然语言解析
    │   LLM 返回："我需要告知开发者修改按钮颜色"
    │   → Agent 代码通过正则/LLM 二次解析 → 识别意图和参数
    │
    │ 方式三（未来）：Agent 框架自动注入发消息工具
    │   在 tool_descriptions 中注册 send_message 工具
    │   LLM 直接调用工具 → 自动触发 role.message 事件
    │
    ▼
event_bus.publish("role.message", {
    from_role: "designer_A",
    to_role: "dev_role",
    dialog_id: "dev↔designer_A__project_X_login",
    content: "按钮从蓝色改成绿色，字体16→20px"
})
    │
    ▼
┌──────────────────────────────────────────────┐
│              role_comm                        │
│                                               │
│  1. 收到 role.message 事件                    │
│  2. 存储到 SQLite（含 dialog_id）             │
│  3. 发布 role.message_received 事件           │
│                                               │
│  存储格式：                                    │
│    msg_id | dialog_id | from | to | content   │
│    | summary | timestamp                     │
└──────────────┬───────────────────────────────┘
               │
               ▼
event_bus.publish("role.message_received", {
    receiver: "dev_role",
    dialog_id: "dev↔designer_A__project_X_login",
    unread_count: 3
})
    │
    ▼
角色 B（接收方）
    │
    │ 收到事件 → 标记"有未读消息"（内存计数器+1）
    │ 下次空闲时 → 调 LLM 处理
    │ LLM context 中：该 dialog 的历史 + 新消息
    ▼
event_bus.publish("role.message", {  // B 回复 A
    from_role: "dev_role",
    to_role: "designer_A",
    dialog_id: "dev↔designer_A__project_X_login",
    content: "按钮已改好，蓝色→绿色"
})
```

### 2.2 接收方调度决策

```
接收方收到 role.message_received 事件后：
  
  1. 标记"有未读消息"（内存计数器 +1）
  
  2. 如果有空闲处理能力：
        → 立即准备处理（批量窗口内等更多消息）
    否则：
        → 排队等待（不触发 LLM 调用）
  
  3. 批量窗口（batch_window_ms = 2000ms）：
        → 等待 2 秒攒多条消息
        → 2 秒后开始处理
        → 多条件一次性发给 LLM
  
  4. 重要：调度决策本身**不额外调用 LLM**
        → 是代码级别的"排队/等待"逻辑
        → Token 消耗为 0
```

### 2.3 role_comm 订阅的事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `role.message` | 任意角色 | 存储消息 → 发布 `role.message_received` |

### 2.4 role_comm 发布的事件

| 事件 | 目标 | Payload |
|------|------|---------|
| `role.message_received` | `receiver` 角色 | `{receiver, dialog_id, unread_count}` |
| `role.messages_batch` | `receiver` 角色 | `{receiver, dialogs: {dialog_id: [msgs]}}`（按 dialog 分组） |

### 2.5 角色查询消息的事件（按需）

| 事件 | 来源 | 响应事件 | 说明 |
|------|------|---------|------|
| `role.messages_query` | 任意角色 | `role.messages_result` | 查询未读消息 |
| `role.messages_consume` | 任意角色 | `role.messages_consumed` | 消费（标记已读）特定 dialog 的消息 |
| `role.messages_summary` | 任意角色 | `role.messages_summary_result` | 获取消息摘要 |

---

## 三、关键设计：dialog_id 隔离对话上下文

> **命名说明**：使用 `dialog_id` 而非 `session_id`，以与 session-hub 的 `session_id`（用户会话标识）区分。
> `dialog_id` = 角色间通信的话题标识；`session_id` = 用户与系统的连接会话。

### 3.1 每个消息携带 dialog_id

```python
# 角色 A 发消息时，消息体携带 dialog_id
{
    "msg_id": "uuid-xxx",
    "from_role": "designer_A",
    "to_role": "dev_role",
    "dialog_id": "dev↔designer_A__project_X_login",
    "content": "按钮从蓝色改成绿色，字体16→20px",
    "summary": None,       # 自动生成（长消息时）
    "timestamp": "...",
    "reply_to": None       # 回复链
}
```

### 3.2 dialog_id 的生成规则

```
dialog_id = "{role_A}↔{role_B}__{project}_{topic}"

示例：
  "dev↔designer_A__project_X_login"     # 项目X登录页的开发↔设计师
  "dev↔designer_B__project_Y_home"      # 项目Y首页的开发↔设计师
  "dev↔suri__upgrade_code_tool"          # suri 安排开发升级插件
  "suri↔user_甲__project_Z"              # suri 和用户的聊天会话
```

**谁决定 dialog_id？**
- 发送方 Agent 在 LLM 输出中识别出"会话目标"
- Agent 代码：check dialog 是否存在，不存在则创建
- dialog_id 由 `from_role` + `to_role` + 业务上下文拼接

### 3.3 角色看到的未读消息（按 dialog 分组）

```
dev_role 查询未读消息 → 返回值：

{
  "dialogs": {
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

### 4.1 自动摘要（异步方案）

```python
# 消息存储时，如果 content 超过阈值，异步生成摘要
SUMMARY_CONFIG = {
    "enabled": True,              # 可配置：默认关闭
    "threshold_chars": 2000,     # 超过 2000 字符生成摘要（约 500 token）
    "strategy": "simple_truncate", # "simple_truncate" | "llm_summary"
    "max_summary_chars": 200,    # 摘要最大长度
}
```

**摘要策略**：
```
方式一（推荐，默认）：简单截断
  取首段 + 末尾两行 → 控制在 max_summary_chars 内
  特点：0 LLM 调用、即时生成、无额外成本

方式二（可选）：LLM 摘要
  使用最便宜的模型异步生成
  消息先存储，摘要后补（不影响发送延迟）
  如果摘要模型不可用：降级到方式一
```

**调用 LLM 时默认只加载摘要**：

```
角色 B 的 history_layer：
  ┌────────────────────────────────────┐
  │ 设计师说（摘要）："修改登录页设计"   │
  │ 设计师说（摘要）："按钮颜色改绿色"   │
  │ 设计师说："字体也改到20px"（短消息，不摘要）│
  └────────────────────────────────────┘

角色 B 如果需要看完整内容：
  → 发布 role.messages_query 事件
  → role_comm 返回完整 content
  → 只在需要时加载，不走 LLM context
```

### 4.2 按 dialog 批量处理

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

### 4.3 简单确认消息不走 LLM

```
以下场景不需要 LLM 处理：
  "收到"、"好的" → 自动标记 consumed
  仅 emoji 回复 → 自动标记 consumed
  纯状态更新（如"已完成"）→ 自动标记 consumed

判断逻辑（增强版 — 避免误判含有细节的状态更新）：
  多层判定法：
    1. content 长度 < 10 字符 → 视为"简单确认"
    2. content 长度 < 20 字符且仅含中文/英文纯状态词 → 视为"状态确认"
       纯状态词列表：["已完成", "已处理", "已更新", "已修改", "已提交",
                      "done", "ok", "okay", "yep", "got it", "收到",
                      "了解", "好的", "没问题", "可以", "好的收到"]
    3. content 包含"因为"/"理由"/"but"/"需要"等转折/因果词 → 视为"含附加信息"
       不走简单确认，走 LLM 处理
    4. 纯 emoji（仅含表情符号/标点/空格）→ 视为简单确认

判断逻辑：
  - 判定为"简单确认"或"状态确认" → 不走 LLM，直接标记 consumed
  - 无法判定（含新信息、转折、疑问句）→ 走 LLM 处理
```

---

## 五、数据模型

```python
@dataclass
class RoleMessage:
    msg_id: str
    from_role: str
    to_role: str
    dialog_id: str              # 对话标识（核心字段，原 session_id）
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
    dialog_id TEXT NOT NULL,         -- 对话标识（原 session_id）
    content TEXT NOT NULL,           -- 自然语言消息
    summary TEXT,                    -- 摘要（长消息自动生成）
    timestamp REAL NOT NULL,
    consumed INTEGER DEFAULT 0,
    reply_to TEXT
);

CREATE INDEX idx_messages_dialog ON messages(dialog_id, consumed, timestamp);
CREATE INDEX idx_messages_receiver ON messages(to_role, consumed, timestamp);
CREATE INDEX idx_messages_from ON messages(from_role, timestamp);
```

---

## 七、角色通信的完整 Token 消耗模型

> 修正后的模型：包含发送方意图识别 + 调度决策 + 接收方处理 + 可选确认

```
角色 A（设计师）→ 角色 B（开发）的完整链路

┌──────────────────────────────────────────────┐
│ 步骤 1: 设计师调 LLM → 决定发消息             │
│   ├─ LLM 调用：1 次                           │
│   ├─ Token 消耗：1~3K（正常对话中的增量）      │
│   └─ LLM 输出含发消息意图 → Agent 代码解析    │
├──────────────────────────────────────────────┤
│ 步骤 2: 事件传递 + 调度决策（不走 LLM）        │
│   ├─ event_bus.publish("role.message")        │
│   ├─ role_comm 存储到 SQLite                  │
│   ├─ event_bus.publish("role.message_received")│
│   ├─ 接收方 Agent 标记未读（代码逻辑）          │
│   └─ Token 消耗：0（调度决策是代码逻辑）        │
├──────────────────────────────────────────────┤
│ 步骤 3: 开发调 LLM 处理消息                    │
│   ├─ LLM 调用：1 次                           │
│   ├─ Token 消耗：3~10K（看任务复杂度）          │
│   ├─ 批量处理：3 条消息还是 1 次调用           │
│   └─ LLM 决定：改代码 + 回复设计师             │
├──────────────────────────────────────────────┤
│ 步骤 4（可选）：确认回复                       │
│   ├─ 如果需要确认已理解 → 额外 1 次调用         │
│   ├─ 简单确认（如"收到"）→ 不走 LLM           │
│   └─ Token 消耗：0~3K                        │
├──────────────────────────────────────────────┤
│ 最低：2 次 LLM 调用（发送 + 处理，无确认）      │
│ 最高：4 次 LLM 调用（发送 + 处理 + 重试 + 确认）│
│ Token 范围：4K ~ 16K                          │
│ 这是角色通信的实际成本                          │
└──────────────────────────────────────────────┘

优化空间：
  方式一（推荐）：function calling 结构化解 → 减少意图识别误差
  多条消息批量处理 → 仍然 2 次 LLM 调用（不增加）
  消息摘要 → LLM 只看 summary，不看全文（节省 30-50% history token）
  简单确认不走 LLM → 省去额外 1 次 LLM 调用
  context 压缩 → history 不膨胀
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
| 活跃 dialog | 无限期 | 角色还在对话 |
| 非活跃 dialog | 7 天 | 超过 7 天无新消息 |
| 已完成的 dialog | 30 天 | 任务完成后保留 30 天 |

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
    enabled: false                # 默认关闭
    threshold_chars: 2000         # 超过此长度自动摘要（约 500 token）
    strategy: "simple_truncate"   # "simple_truncate" | "llm_summary"
    max_summary_chars: 200        # 摘要最大长度
  
  # 简单确认
  auto_ack:
    enabled: true                 # 简单确认自动标记 consumed
    max_chars: 10                 # 小于此长度视为简单确认
  
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
| 迭代 2 | **dialog_id 支持**（按对话分组、隔离上下文） | 📋 规划中 |
| 迭代 3 | **事件驱动**（纯事件化、去除方法调用）+ **意图识别**（function calling + 自然语言降级） | 📋 规划中 |
| 迭代 4 | **消息摘要**（长消息自动摘要、按需加载全文） | 📋 规划中 |
| 迭代 5 | **批量处理 + 简单确认**（batch_window_ms + auto_ack） | 📋 规划中 |