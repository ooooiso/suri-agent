# interrupt_handler 插件 PRD

## 定位

任务执行受阻时的系统级处理。分类受阻原因，生成用户决策建议，提供升级通道。

**关键约束**：只处理系统级中断，不处理业务逻辑错误。升级决策需用户确认或 suri 角色授权。

## 功能需求

### 1. 受阻原因分类（ClassifyReason）

关键词匹配（中英双语）自动分类：

| 类型 | 关键词 | 说明 |
|------|--------|------|
| `missing_tool` | 缺少工具、没有接口、不支持、need tool | 现有插件/工具无法满足需求 |
| `knowledge_gap` | 不会、不了解、不清楚、知识不足、unknown | 角色知识不足以完成任务 |
| `permission_denied` | 权限不足、拒绝访问、无权限、forbidden | 安全策略阻止操作 |
| `dependency_failed` | 依赖失败、上游错误、调用失败、unavailable | 前置步骤/依赖服务失败 |
| `timeout` | 超时、无响应、hang、timeout | 任务或 LLM 响应超时 |
| `resource_exhausted` | 内存不足、OOM、CPU 满载、quota exceeded | 系统资源耗尽 |

### 2. 中断响应生成（GenerateResponse）

根据原因类型生成结构化建议：

```
【任务受阻】{task_name}
原因：{reason}
建议：
1. {option_1}
2. {option_2}
3. {option_3}
请选择：- [继续] - [升级] - [取消]
```

### 3. 升级通道（Escalation）

| 升级目标 | 场景 | 方式 |
|----------|------|------|
| `escalate_to_dev()` | 缺少工具 / 技术问题 | 向 suri_dev 发送 escalation 消息（role_comm） |
| `escalate_to_hr()` | 需要新角色 / 权限配置 | 向 suri_hr 发送 escalation 消息（role_comm） |
| `escalate_to_user()` | 需要用户决策 / 确认 | 通过 access 向用户呈现选项 |
| `escalate_to_suri()` | 系统级异常 / 无法分类 | 向 suri 角色报告 |

### 4. 用户决策处理（UserDecision）

- 向用户呈现 2~3 个明确选项
- 支持回复：继续 / 升级 / 取消 / 自定义指令
- 用户选择后触发对应动作事件

### 5. 自动重试（AutoRetry）

- `dependency_failed` / `timeout` 类型可自动重试（需配置）
- 重试次数受 task_scheduler 重试策略约束
- 连续重试失败后转为 `escalate_to_user()`

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `agent.blocked` | agent_registry | 分析受阻原因并处理 |
| `task.failed` | task_scheduler | 分析失败原因，判断是否需要中断处理 |
| `task.timeout` | task_scheduler | 超时处理 |
| `user.decision` | access | 用户决策回复 |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `interrupt.handled` | log_service / 角色 | 中断已处理 |
| `interrupt.escalated` | role_comm / 目标角色 | 已升级给某角色 |
| `interrupt.user_decision_needed` | access | 需要用户决策 |
| `interrupt.cancelled` | agent_registry | Agent 被取消 |
| `agent.block_requested` | agent_registry | 标记 Agent 为受阻状态 |
| `interrupt.retry_requested` | task_scheduler | 请求重试 |

### 方法

```python
class InterruptHandler:
    def handle(self, agent_id: str, block_reason: str) -> InterruptResult
    def _classify_reason(self, block_reason: str) -> str
    def _handle_missing_tool(self, agent_id: str, reason: str) -> InterruptResult
    def _handle_knowledge_gap(self, agent_id: str, reason: str) -> InterruptResult
    def _handle_permission_denied(self, agent_id: str, reason: str) -> InterruptResult
    def _handle_dependency_failed(self, agent_id: str, reason: str) -> InterruptResult
    def _handle_timeout(self, agent_id: str, reason: str) -> InterruptResult
    def _handle_resource_exhausted(self, agent_id: str, reason: str) -> InterruptResult
    def escalate_to_dev(self, agent_id: str, reason: str) -> bool
    def escalate_to_hr(self, agent_id: str, reason: str) -> bool
    def escalate_to_user(self, agent_id: str, options: List[str]) -> bool
    def cancel_task(self, agent_id: str, reason: str) -> bool
```

## 数据模型

```python
@dataclass
class InterruptResult:
    handled: bool
    action: str                    # wait | escalate | cancel | auto_resolve | retry
    suggestion: str                # 给用户的中文建议文本
    new_agent_id: Optional[str]    # 升级后创建的新 Agent ID
    reason: str                    # 原因类型
    escalation_target: Optional[str]  # 升级目标角色 ID
```

## 事件 Payload Schema

### 订阅事件

#### `agent.blocked`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `reason` | string | 是 | 受阻原因描述 |
| `current_step` | object | 否 | 当前步骤信息 |
| `block_type` | string | 否 | 分类：missing_tool / knowledge_gap / permission_denied / dependency_failed / timeout / resource_exhausted |

#### `task.failed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `error_code` | integer | 是 | 错误码 |
| `error_message` | string | 是 | 错误描述 |
| `retry_count` | integer | 是 | 已重试次数 |
| `agent_id` | string | 否 | 关联 Agent ID |

#### `task.timeout`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `timeout_seconds` | integer | 是 | 超时时间 |
| `agent_id` | string | 否 | 关联 Agent ID |

#### `user.decision`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `decision_id` | string | 是 | 决策单 ID |
| `choice` | string | 是 | 用户选择：continue / escalate / cancel / custom |
| `custom_instruction` | string | 否 | 自定义指令 |
| `user_id` | string | 是 | 用户 ID |

### 发布事件

#### `interrupt.handled`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `action` | string | 是 | wait / escalate / cancel / auto_resolve / retry |
| `reason` | string | 是 | 中断原因类型 |

#### `interrupt.escalated`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `escalation_target` | string | 是 | 升级目标角色 ID |
| `reason` | string | 是 | 升级原因 |
| `context` | object | 否 | 上下文摘要 |

#### `interrupt.user_decision_needed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `decision_id` | string | 是 | 决策单 ID |
| `agent_id` | string | 是 | Agent ID |
| `question` | string | 是 | 问题描述 |
| `options` | array | 是 | 选项列表 |
| `timeout` | integer | 是 | 决策超时（秒） |

#### `interrupt.cancelled`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `cancelled_by` | string | 是 | 取消者 |
| `reason` | string | 否 | 取消原因 |

#### `agent.block_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `reason` | string | 是 | 受阻原因描述 |
| `block_type` | string | 是 | 分类：missing_tool / knowledge_gap / permission_denied / dependency_failed / timeout / resource_exhausted |
| `suggested_action` | string | 否 | 建议的处理动作 |

#### `interrupt.retry_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `agent_id` | string | 是 | Agent ID |
| `retry_number` | integer | 是 | 重试次数 |

## 配置项

```yaml
interrupt_handler:
  enable_auto_retry: true
  auto_retry_types: ["dependency_failed", "timeout"]
  max_auto_retries: 2
  escalation_timeout: 300         # 升级后等待响应超时（秒）
  decision_timeout: 600           # 用户决策等待超时（秒）
  reason_keywords:
    missing_tool: ["缺少工具", "没有接口", "不支持", "need tool", "missing"]
    knowledge_gap: ["不会", "不了解", "不清楚", "unknown", "knowledge"]
    permission_denied: ["权限不足", "拒绝访问", "无权限", "forbidden", "denied"]
    dependency_failed: ["依赖失败", "上游错误", "调用失败", "unavailable"]
    timeout: ["超时", "无响应", "hang", "timeout"]
    resource_exhausted: ["内存不足", "OOM", "quota", "exhausted"]
```

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：agent_registry（获取 Agent 状态）
- 上游：role_comm（发送升级消息）
- 下游：access（向用户呈现决策选项）
- 下游：log_service（记录中断事件）

## 生命周期

1. `init()` → 加载中断处理模板、关键词映射
2. `start()` → 标记就绪
3. `stop()` → 中断正在进行的升级等待
4. `cleanup()` → 保存未完成的用户决策请求

## 安全边界

- 不自动取消任务，必须用户确认或 suri 授权
- 升级消息通过 role_comm 发送，受通信权限约束
- 用户决策超时后默认行为：等待（不自动取消）
- **核心原则**：只提供建议，不替用户做决策
