# 系统运行规则

> 本文档定义 suri-agent 的核心运行规则。所有规则由角色在调用插件时遵守，和程序无关。

---

## 1. 通信规则

### 1.1 消息格式

所有角色间消息必须符合 `RoleMessage` 标准格式：
- 必填字段：`msg_id`, `sender`, `receiver`, `msg_type`, `content`, `timestamp`, `priority`
- 合法 `msg_type`：task / approval / notify / escalation / status_update / request_help / completion
- 合法 `priority`：high / normal / low

### 1.2 通信权限

| 场景 | 是否允许 | 说明 |
|------|---------|------|
| 自己 → 自己 | ✅ | 自通信 |
| 同工作组 | ✅ | 组内自由通信 |
| 角色 ↔ suri | ✅ | 核心角色通道 |
| 跨工作组 | ⚠️ | 需审批或双方为管理员 |
| 广播 | ✅ | 所有角色可接收 |

### 1.3 消息留存

| 消息类型 | 留存天数 | 说明 |
|----------|---------|------|
| approval | 90 | 审批类需长期审计 |
| escalation | 90 | 升级类需长期审计 |
| task | 30 | 任务类常规留存 |
| notify | 30 | 通知类常规留存 |
| request_help | 30 | 求助类常规留存 |
| completion | 30 | 完成类常规留存 |
| status_update | 7 | 状态更新短期留存 |

### 1.4 广播规则

- 广播消息存活时间：86400 秒（24 小时）
- 广播消息不标记单消费者消费
- 高优先级广播建议附带 `ttl` 字段

---

## 2. 安全规则

### 2.1 插件安全

- 动态插件加载前必须经过 AST 安全扫描
- 禁止操作：socket / subprocess / eval / exec / 系统删除
- 危险操作直接拒绝加载
- 异常插件隔离，不影响核心和其他插件

### 2.2 文件安全

- 文件变更需 `security_service` 审批令牌
- Soul 文件只读，角色自身不可修改
- 插件只能访问声明的目录
- 代码变更审计记录到 SQLite `changes` 表

### 2.3 通信安全

- 消息大小上限：65536 字节
- 跨工作组通信需审批
- 敏感信息（API Key / 密码 / 私钥）在投影时脱敏

---

## 3. 学习规则

### 3.1 角色经验隔离

- 角色 A 的经验不可泄露给角色 B
- 经验存储于 `roles/{role_id}/memories/` 下
- 跨角色分析仅 ProgramLearner（suri 角色调用）可执行

### 3.2 升级报告管理

- 所有报告必须走完整状态机
- 无报告可长期滞留 PENDING（定期检查）
- 实施失败必须回滚并记录原因

### 3.3 自修改流程

- 无实体可私自修改代码
- 所有变更须经用户确认
- 升级方案必须包含回滚策略
- suri_core 升级后需通过冒烟测试

---

## 4. 调度规则

### 4.1 并发控制

- 系统最大并发任务数：10
- 单用户最大活跃 Agent 数：100
- LLM 响应等待超时：60 秒

### 4.2 超时与重试

- 默认任务超时：300 秒
- 最大重试次数：3 次
- 退避间隔：[0s, 30s, 120s]
- 可重试类型：dependency_failed / timeout

### 4.3 优先级

| 优先级 | 权重 | 典型场景 |
|--------|------|---------|
| CRITICAL | 0 | 系统错误、安全事件 |
| HIGH | 1 | 用户紧急请求 |
| NORMAL | 2 | 常规任务 |
| LOW | 3 | 后台学习、定时任务 |

---

## 5. 中断规则

### 5.1 中断分类

| 类型 | 自动重试 | 默认动作 |
|------|---------|---------|
| missing_tool | ❌ | escalate_to_dev |
| knowledge_gap | ❌ | escalate_to_user |
| permission_denied | ❌ | escalate_to_hr |
| dependency_failed | ✅ | 重试后 escalate_to_user |
| timeout | ✅ | 重试后 escalate_to_user |
| resource_exhausted | ❌ | escalate_to_suri |

### 5.2 用户决策

- 必须提供 2~3 个明确选项
- 用户决策超时：600 秒
- 超时默认行为：暂停等待（不自动取消）

### 5.3 升级规则

- 升级消息必须抄送 suri
- 升级后等待响应超时：300 秒
- 连续升级无响应时回流用户

---

## 6. Agent 规则

### 6.1 生命周期

- Agent 六态：planning → running → [completed | blocked | paused | cancelled]
- 父 Agent 状态自动聚合子 Agent 状态
- 已完成 Agent 保留 24 小时后自动清理

### 6.2 上下文隔离

- 每个 Agent 拥有独立的 `AgentContext`
- 消息历史不与其他 Agent 共享
- 系统提示从 Soul 文件构建 + 任务分解方法论注入

### 6.3 子 Agent

- 子 Agent 必须关联父 Agent
- 子 Agent 完成时更新父 Agent 进度
- 父 Agent 取消时级联取消子 Agent（可选）

---

## 7. 角色类型权限矩阵

| 权限 | core (suri) | admin | project_director | worker |
|------|:-----------:|:-----:|:----------------:|:------:|
| 创建角色 | ✅ | ✅ | ⚠️ 仅项目内 | ❌ |
| 删除角色 | ✅ | ⚠️ 非核心角色 | ❌ | ❌ |
| 修改 Soul | ✅ | ⚠️ 需审批 | ⚠️ 仅自身 | ❌ |
| 创建 Agent | ✅ | ✅ | ✅ | ⚠️ 需授权 |
| 删除 Agent | ✅ | ✅ | ✅ | ⚠️ 仅自身 |
| 广播消息 | ✅ | ✅ | ✅ | ⚠️ 仅项目内 |
| 跨项目通信 | ✅ | ⚠️ 需审批 | ❌ | ❌ |
| 修改核心代码 | ✅ | ⚠️ 需审批 | ❌ | ❌ |
| 审批请求 | ✅ | ✅ | ❌ | ❌ |
| 安装插件 | ✅ | ⚠️ 需审批 | ❌ | ❌ |
| 读取其他角色记忆 | ✅ | ⚠️ 需审批 | ❌ | ❌ |
| 修改自身 output/ | ✅ | ✅ | ✅ | ✅ |
| 读取公共资源 | ✅ | ✅ | ✅ | ✅ |

**图例**：✅ 允许 / ⚠️ 有条件允许 / ❌ 禁止

**说明**：
- `suri`（core）拥有最高权限，但修改核心代码仍需用户确认
- `admin` 可管理非核心角色，但修改 Soul 需 security_service 审批
- `project_director` 权限仅限所属项目范围内
- `worker` 只能操作自身数据，不能创建/删除其他实体
