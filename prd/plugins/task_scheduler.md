# task_scheduler 插件 PRD

## 定位

任务执行调度中心。管理任务的优先级队列、并发控制和超时重试。被角色调用或自动订阅 task 事件进行调度。

**关键约束**：只做调度，不执行业务逻辑，不调用 LLM，不决定任务内容。调度目标由角色和 task_planner 决定。

## 功能需求

### 1. 优先级队列（PriorityQueue）
- 基于 `asyncio.PriorityQueue`，按优先级 + 时间戳排序
- 优先级：CRITICAL(0) / HIGH(1) / NORMAL(2) / LOW(3)
- 同优先级按 FIFO 处理
- 支持动态调整优先级（重新入队）

### 2. 并发控制（ConcurrencyControl）
- `asyncio.Semaphore(max_concurrent)` 限制同时执行的任务数
- 默认最大并发：10
- 支持按角色/用户分别限制并发（预留）

### 3. 超时与重试（TimeoutRetry）
- 默认任务超时：300 秒
- 重试策略：最多 3 次
- 退避间隔：[0, 30, 120] 秒（首次立即，第二次 30s，第三次 120s）
- 超时后标记为 `task.timeout`，可选择重试或失败

### 4. LLM 响应等待（LLMWaiter）
- 角色发起 `llm.request` 后，task_scheduler 可注册等待
- 使用 `asyncio.Event` 等待 `llm.response` 事件
- LLM 等待超时：60 秒（独立配置）
- 超时后触发 `task.timeout` 或降级策略

### 5. 任务状态流转

```
queued ──▶ running ──▶ completed
   │          │
   │          ├──▶ blocked（触发 interrupt_handler）
   │          │
   │          └──▶ timeout ──▶ retry / failed
   │
   └──▶ cancelled
```

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `task.created` | 角色 | 自动调度（如配置 auto_schedule） |
| `task.plan_ready` | task_planner | 按规划步骤批量入队 |
| `task.priority_changed` | 角色/系统 | 重新排序 |
| `task.cancel_requested` | 角色/用户 | 取消任务 |
| `llm.response` | llm_gateway | 唤醒等待的 LLM Event |
| `agent.status_changed` | agent_registry | Agent 状态变更，触发对应任务状态同步 |
| `interrupt.retry_requested` | interrupt_handler | 重试被中断的任务 |
| `interrupt.cancelled` | interrupt_handler | 取消被中断的任务 |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `task.queued` | log_service | 任务已入队 |
| `task.started` | log_service / 角色 | 任务开始执行 |
| `task.completed` | log_service / role_learner / 角色 | 任务完成 |
| `task.failed` | log_service / interrupt_handler / 角色 | 任务失败 |
| `task.timeout` | log_service / interrupt_handler | 任务超时 |
| `task.cancelled` | log_service / 角色 | 任务被取消 |
| `task.retried` | log_service | 任务重试 |

### 内部方法

```python
class TaskScheduler:
    async def schedule(self, task_id: str, priority: Priority, 
                       executor_role: str, timeout: int = None) -> bool
    async def cancel(self, task_id: str) -> bool
    async def pause(self, task_id: str) -> bool
    async def resume(self, task_id: str) -> bool
    async def _process_task(self, task_id: str) -> None
    async def _wait_for_llm(self, task_id: str, timeout: int) -> LLMResponse
    def get_queue_status(self) -> Dict[str, Any]  # 队列长度/活跃数/等待数
```

## 事件 Payload Schema

### 订阅事件

#### `task.created`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务唯一标识 |
| `priority` | string | 是 | CRITICAL / HIGH / NORMAL / LOW |
| `executor_role` | string | 是 | 执行角色 ID |
| `timeout` | integer | 否 | 超时（秒），默认 300 |
| `project_id` | string | 否 | 所属项目 |
| `payload` | object | 否 | 任务数据 |

#### `task.plan_ready`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 规划 ID |
| `steps` | array | 是 | 步骤列表 |
| `project_id` | string | 否 | 所属项目 |

#### `task.priority_changed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `old_priority` | string | 是 | 原优先级 |
| `new_priority` | string | 是 | 新优先级 |

#### `task.cancel_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `reason` | string | 否 | 取消原因 |
| `requester` | string | 是 | 请求者 |

#### `agent.step_ready`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | Agent ID |
| `step_id` | string | 是 | 步骤 ID |
| `description` | string | 是 | 步骤描述 |

#### `llm.response`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `request_id` | string | 是 | 对应请求 ID |
| `content` | string | 是 | 模型响应内容 |
| `model_id` | string | 是 | 使用的模型 |
| `usage` | object | 否 | token 使用统计 |

### 发布事件

#### `task.queued`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `queue_position` | integer | 是 | 队列位置 |
| `estimated_start` | string | 否 | 预计开始时间 |

#### `task.started`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `started_at` | string | 是 | 开始时间 |
| `worker_id` | integer | 否 | 执行 worker 编号 |

#### `task.completed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `result` | string | 是 | 执行结果 |
| `duration_ms` | integer | 否 | 执行耗时 |
| `completed_at` | string | 是 | 完成时间 |

#### `task.failed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `error_code` | integer | 是 | 错误码 |
| `error_message` | string | 是 | 错误描述 |
| `retry_count` | integer | 是 | 已重试次数 |

#### `task.timeout`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `timeout_seconds` | integer | 是 | 超时时间 |

#### `task.cancelled`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `reason` | string | 否 | 取消原因 |

#### `task.retried`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 是 | 任务 ID |
| `retry_number` | integer | 是 | 第几次重试 |
| `next_retry_at` | string | 是 | 下次重试时间 |

## 配置项

```yaml
task_scheduler:
  max_concurrent: 10
  default_timeout: 300
  llm_wait_timeout: 60
  auto_schedule: true           # task.created 自动入队
  retry_policy:
    max_retries: 3
    intervals: [0, 30, 120]
  priority_weights:
    CRITICAL: 0
    HIGH: 1
    NORMAL: 2
    LOW: 3
```

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：llm_gateway（等待 LLM 响应）
- 上游：task_planner（获取任务规划）
- 下游：log_service（记录调度日志）
- 下游：interrupt_handler（超时/失败时触发中断处理）
- 下游：role_learner（任务完成后触发学习）

## 生命周期

1. `init()` → 初始化 PriorityQueue、Semaphore、运行中任务字典
2. `start()` → 启动调度主循环（消费者协程）
3. `pause()` → 暂停新任务入队，等待运行中任务完成
4. `resume()` → 恢复调度
5. `stop()` → 停止调度循环，取消所有排队任务，等待运行中任务完成或强制超时
6. `cleanup()` → 释放 Semaphore、清空队列、持久化未完成任务状态

## 安全边界

- 单个任务异常不影响队列中其他任务
- 取消任务时发送 `task.cancelled` 事件，由执行者自行清理
- 重试次数耗尽后标记 `task.failed`，不再自动重试
- 内存中运行任务字典防止重复调度同一任务
- **核心原则**：调度器不解析任务内容，只管理执行时序

### 与 agent_registry 的状态边界

| 维度 | task_scheduler | agent_registry |
|------|---------------|--------------|
| **状态类型** | 任务调度状态（queued / running / completed / failed / timeout / cancelled / retried） | Agent 执行状态（planning / running / blocked / paused / completed / cancelled） |
| **状态更新方式** | 内部维护 + 发布事件 | 订阅 task.* 事件 + 角色直接调用 step_update |
| **职责边界** | 管「什么时候执行」 | 管「执行得怎么样」 |
| **协作方式** | task_scheduler 发布 task.completed/failed/timeout → agent_registry 订阅同步 Agent 状态 | agent_registry 发布 agent.status_changed → task_scheduler 订阅（如需调度联动） |
