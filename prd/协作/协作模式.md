# 协作模式

> 定义角色间协作的三种模式，全部基于**自然语言消息 + 事件驱动**。

---

## 核心约束：项目级隔离 + Session 隔离

角色间协作始终受三层上下文隔离约束：

| 隔离维度 | 说明 |
|---------|------|
| **项目级隔离** | 同一项目内的角色可互相通信；跨项目角色通信需显式授权 |
| **Session 隔离** | 不同 session 的协作消息互不可见；广播模式按 session_id 过滤 |
| **角色可见性** | 角色只能看到与自己角色相关的协作请求 |

### 项目级隔离

```
项目"电商APP"内的角色：
    设计师A ─── 开发B ─── 测试C
        ↕           ↕          ↕
    session_id: "ecommerce_session_01"

项目"内部工具"内的角色：
    开发D ─── 开发E
        ↕        ↕
    session_id: "internal_tools_session_01"

跨项目限制：
  → 电商APP的设计师A 不可自动通信 内部工具的开发D
  → 如需跨项目沟通，需要 suri 授权或通过 global 层转发
```

### Session 隔离

```
同一项目内的两个独立协作会话：

会话 A（Feature X 开发）：
    设计师A → 开发B → 测试C
    session_id: "feature_x_session"

会话 B（Bug fix）：
    开发B → 测试C
    session_id: "bugfix_session"

隔离规则：
  → 会话 A 中的协作消息不可见会于会话 B
  → 两条会话共享同一个 project_id，但 session_id 不同
  → role_comm 按 session_id 路由消息
```

## 根本原则

角色间通信 = **两个人通过信箱传纸条**

- A 写纸条需要思考（A 调 LLM）
- B 读纸条需要理解（B 调 LLM）
- 纸条本身不思考（role_comm 只送信）

**不走 LLM 的部分**：事件传递、消息存储、通知送达。

---

## 一、点对点模式

```
角色 A → 角色 B

设计师 LLM 思考 → 决定发消息
    │
    ▼
发布 role.message 事件（自然语言）
    │
    ▼
role_comm 存储 + 转发
    │
    ▼
角色 B 收到事件 → 标记未读
    │
    ▼
角色 B 下次调 LLM → 消息进入 B 的 context
    │
    ▼
角色 B LLM 理解消息 → 执行任务
```

**适用场景**：设计师通知开发改 UI、开发反馈进度给 suri

**特点**：
- 消息是纯自然语言，没有结构化字段
- 接收方 LLM 自己理解、自己决策
- 按 session_id 隔离不同对话

---

## 二、广播模式

```
suri
    │
    ▼
发布 role.broadcast 事件
    │
    ▼
role_comm 存储 + 通知所有角色
    │
    ▼
角色 A ── 角色 B ── 角色 C
(各角色自行决定是否处理)
```

**适用场景**：系统事件通知、紧急需求公告

**特点**：
- 一对多，所有角色收到同一消息
- 广播消息不标记消费（各角色独立读取）
- 角色自行判断是否与己相关

---

## 三、串联协作模式

```
设计师 → 开发 → 测试 → suri（串行链）

设计师：改好设计 → 发给开发
开发：改好代码 → 发给测试
测试：测完 → 发给 suri 确认
suri：确认完成
```

**适用场景**：有明确前后依赖的工作流

**特点**：
- 消息链按 session_id 串联
- 每一步都是独立 LLM 调用
- 前一步的结果是后一步的输入（自然语言描述）

---

## 四、对等讨论模式

```
角色 A ←→ 角色 B ←→ 角色 C
  ↕        ↕        ↕
    同一 session 内多人讨论
```

**适用场景**：架构设计讨论、方案评审

**特点**：
- 多个角色共用一个 session_id
- 所有消息在同一个 history_layer 中
- 每个角色调 LLM 时看到完整讨论上下文

---

## 五、跨项目通信授权流程

### 5.1 问题场景

当角色 A（项目"电商APP"）需要与角色 D（项目"内部工具"）通信时，由于项目级隔离，无法自动通信。需要经过显式授权流程。

### 5.2 授权流程

```
角色 A（项目"电商APP"）需要联系角色 D（项目"内部工具"）
    │
    ├─ 1. 角色 A 发起跨项目请求
    │      └─ 发布 role.cross_project.request 事件
    │         payload: {
    │           "from_role": "designer_A",
    │           "from_project": "ecommerce_app",
    │           "to_role": "developer_D",
    │           "to_project": "internal_tools",
    │           "reason": "需要内部工具的 API 接口信息",
    │           "session_id": "ecommerce_session_01"
    │         }
    │
    ├─ 2. role_comm 拦截并校验权限
    │      ├── 检查跨项目授权缓存（是否有已批准的授权 Token）
    │      ├── 有有效授权 → 直接放行（跳至第 5 步）
    │      └── 无授权 → 构建授权请求
    │
    ├─ 3. suri 评估跨项目请求
    │      ├── 检查请求合理性（LLM 分析 reason 字段）
    │      ├── 生成授权建议（临时/永久/拒绝）
    │      └── 向用户呈现授权决策界面
    │
    ├─ 4. 用户决策
    │      ├── 批准（永久） → 生成永久授权 Token
    │      │      存储在 security_service 的跨项目授权表
    │      ├── 批准（临时） → 生成临时授权 Token（含 TTL）
    │      │      payload: {
    │      │        "token": "xproj_abc123",
    │      │        "from_role": "designer_A",
    │      │        "to_role": "developer_D",
    │      │        "scope": "单次消息",
    │      │        "expires_at": "2024-07-01T12:00:00Z"
    │      │      }
    │      ├── 拒绝 → 发布 role.cross_project.denied 事件
    │      │      通知角色 A：请求被拒绝
    │      └── 有条件批准 → 用户指定消息范围/次数限制
    │
    └─ 5. 授权放行
           ├── 发布 role.cross_project.authorized 事件
           ├── 消息通过 role_comm 转发给角色 D
           └── 跨项目消息标记 scope="cross_project"
```

### 5.3 授权 Token 生命周期

```
状态图：

        ┌──────────┐
        │ PENDING  │  ← 刚创建
        └────┬─────┘
             │
             ▼
       ┌────────────┐
       │  APPROVED  │  ← 用户批准（永久）
       └──────┬─────┘
              │
       ┌──────────────┐
       │ APPROVED_TTL │  ← 用户批准（含过期时间）
       └──────┬───────┘
              │
              ▼
        ┌──────────┐
        │ EXPIRED  │  ← TTL 到期
        └──────────┘

       ┌──────────┐
       │ REJECTED │  ← 用户拒绝
       └──────────┘
```

### 5.4 跨项目授权配置

```yaml
# ~/.suri/data/configs/cross_project_auth.yaml
# 跨项目通信授权配置

default_policy:
  # 默认策略：拒绝所有跨项目通信，除非显式授权
  allow_by_default: false

temporary_token_ttl:
  # 临时授权 Token 默认过期时间
  default_seconds: 3600  # 1 小时
  max_seconds: 86400     # 最大 24 小时

authorization_cache:
  # 授权缓存（避免每次请求都通知用户）
  enabled: true
  cache_ttl_seconds: 300  # 授权缓存 5 分钟

whitelist:
  # 白名单：某些角色可自动跨项目通信
  # 通常保留给 suri 和 admin 角色
  - from_role: "suri"
    to_role: "*"          # suri 可与任何角色通信
    reason: "系统管理员"
  - from_role: "admin"
    to_role: "*"
    reason: "管理员"
```

### 5.5 授权表结构（SQLite）

```sql
-- 跨项目授权表（归属 security_service）
CREATE TABLE cross_project_auth (
    token       TEXT PRIMARY KEY,         -- 授权令牌
    from_role   TEXT NOT NULL,
    from_project TEXT NOT NULL,
    to_role     TEXT NOT NULL,
    to_project  TEXT NOT NULL,
    scope       TEXT DEFAULT 'single',    -- single / limited / permanent
    max_messages INTEGER,                 -- 最大消息数（limited 模式）
    used_messages INTEGER DEFAULT 0,      -- 已用消息数
    expires_at  TEXT,                     -- ISO 8601（NULL 表示永久有效）
    status      TEXT DEFAULT 'pending',   -- pending / approved / approved_ttl / expired / rejected
    created_by  TEXT NOT NULL,            -- 审批者（suri / user）
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX idx_auth_from   ON cross_project_auth(from_role);
CREATE INDEX idx_auth_to     ON cross_project_auth(to_role);
CREATE INDEX idx_auth_status ON cross_project_auth(status);
```

---

## 六、协作与用户可见性

```
用户 → session-hub → suri
                        │
                  需要用户参与？
                    ├── 是 → session-hub 呈现给用户
                    └── 否 →
                        │
                        ▼
              角色间协作（用户不可见）
              设计师 → 开发 → 测试
              （session_id 隔离，不影响用户会话）
```

**用户不可见的协作**：角色间日常沟通，用户不需要知道
**用户可见的协作**：需要用户审批、决策、确认的场景 → suri 通过 session-hub 呈现