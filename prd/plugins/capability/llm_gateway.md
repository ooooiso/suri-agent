# llm_gateway 插件 PRD

> 大模型统一网关。系统唯一的 LLM 调用出口，也是**多 Agent 并发的调度中枢**。

---

## 一、定位

llm_gateway 承担三个核心角色：

| 角色 | 说明 |
|------|------|
| **模型代理** | 统一接入多厂商模型（OpenAI / Anthropic / DeepSeek / GLM / 通义 / 本地） |
| **并发调度** | 管理所有 Agent 的 LLM 请求队列，做速率控制、预算控制、模型路由 |
| **上下文管理层** | 与 Context Manager 配合，管理每个 Task 的独立上下文 |

---

## 二、并发调度架构

```
所有 Agent 的 LLM 请求
    │
    ├── Agent A (task_01: 重构代码)
    ├── Agent B (task_02: 写测试)
    ├── Agent C (task_03: 分析日志)
    ├── Agent D (task_04: 写文档)
    └── ...
    │
    ▼
┌──────────────────────────────────────────────────┐
│                llm_gateway                        │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │              请求队列                       │  │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐        │  │
│  │  │Req_A│ │Req_B│ │Req_C│ │Req_D│ ...     │  │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘        │  │
│  └─────┼────────┼────────┼────────┼──────────┘  │
│        │        │        │        │              │
│  ┌─────▼────────▼────────▼────────▼──────────┐  │
│  │             调度引擎                        │  │
│  │  ┌──────────────┐ ┌────────────────────┐  │  │
│  │  │ 模型路由      │ │ 速率控制            │  │  │
│  │  │ ・任务类型匹配 │ │ ・令牌桶/模型       │  │  │
│  │  │ ・优先级排序   │ │ ・降级链            │  │  │
│  │  │ ・预算检查     │ │ ・等待队列          │  │  │
│  │  └──────┬───────┘ └────────┬───────────┘  │  │
│  └─────────┼──────────────────┼───────────────┘  │
└────────────┼──────────────────┼──────────────────┘
             │                  │
    ┌────────▼────────┐  ┌─────▼──────┐
    │   模型连接池      │  │ 本地模型    │
    │  ┌────┐ ┌────┐  │  │ (ollama/   │
    │  │GPT4│ │Claude│  │  │ llama.cpp)│
    │  └────┘ └────┘  │  └───────────┘
    │  ┌────┐ ┌────┐  │
    │  │DS  │ │GLM │  │
    │  └────┘ └────┘  │
    └─────────────────┘
```

### 2.1 请求队列

每个请求进入队列时携带元数据：

```python
@dataclass
class LLMRequest:
    request_id: str
    task_id: str                    # 所属 Task
    agent_id: str                   # 所属 Agent
    priority: int                   # 0(urgent) / 1(high) / 2(normal) / 3(low)
    messages: list                  # messages 结构
    temperature: float = 0.7
    stream: bool = False
    preferred_model: str = None     # 任务偏好模型
    fallback_models: list = None    # 降级备选模型列表
    max_tokens: int = None
    context_info: dict = None       # 上下文信息（用于上下文管理）
    created_at: float
    timeout: float = 60.0
```

**队列调度策略**：
- 按 `priority` 排序，同优先级按 FIFO
- 高优先级请求可抢占低优先级（低优先级重新排队）
- 每个模型的队列独立，互不影响

### 2.2 速率控制（令牌桶 + 滑动窗口）

每个模型维护独立的速率控制器：

```yaml
# 配置示例（硬编码在 config）
per_model_limits:
  gpt4:
    rpm: 3                          # 每分钟 3 次请求
    tpm: 200000                     # 每分钟 200K tokens
    max_concurrency: 3              # 最大并发数
    queue_timeout: 30               # 排队超时（秒）
    cost_per_1k_input: 0.03        # 计费标准（$）
    cost_per_1k_output: 0.06
  claude:
    rpm: 5
    tpm: 300000
    max_concurrency: 5
    queue_timeout: 30
  deepseek:
    rpm: 60
    tpm: 1000000
    max_concurrency: 10
    queue_timeout: 60
  local:
    rpm: 999
    max_concurrency: 2              # 本地硬件限制
    queue_timeout: 120
```

**超限处理**：
1. 请求排入队列等待
2. 等待超过 `queue_timeout` → 自动降级到 `fallback_models` 中的下一个
3. 所有备选都超时 → 通知调用方（不阻塞）
4. 高优先级请求超过等待阈值 → 通知 suri 用户决策

### 2.3 预算控制

```yaml
budget:
  mode: "monthly"                    # monthly / daily / unlimited
  monthly_limit_usd: 100.0
  priority_weights:                  # 优先级预算分配
    urgent: 0.1                      # 10%
    high: 0.3                        # 30%
    normal: 0.4                      # 40%
    low: 0.2                         # 20%
  notify_at_percent: [50, 80, 95]   # 消费到这些百分比时通知 suri
```

**消费记录**：
```python
# 每次 LLM 调用完成后记录
@dataclass
class CostRecord:
    request_id: str
    task_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float                  # 本次费用
    timestamp: float
```

**预算耗尽处理**：
- `urgent` / `high` 优先级 → 降级到更便宜的模型
- `normal` 优先级 → 排队等待下一个周期
- `low` 优先级 → 直接拒绝，通知调用方

### 2.4 模型路由（按任务类型）

```yaml
model_routes:
  # 代码生成/重构
  - task_pattern: "coding|refactor|debug"
    preferred: "gpt4"
    fallback: ["claude", "deepseek"]
  
  # 文档写作
  - task_pattern: "document|write|report"
    preferred: "claude"
    fallback: ["gpt4", "deepseek"]
  
  # 简单问答/角色学习
  - task_pattern: "chat|learn|analyze"
    preferred: "local" or "deepseek"
    fallback: ["gpt4-mini", "claude"]
  
  # 代码审查（安全敏感）
  - task_pattern: "review|audit"
    preferred: "gpt4"
    fallback: ["claude"]
  
  # 默认
  - task_pattern: ".*"
    preferred: "deepseek"
    fallback: ["gpt4-mini", "claude"]
```

**路由匹配流程**：
1. 从请求的 `messages` 中提取任务描述
2. 正则匹配 `task_pattern`，取第一个匹配
3. 检查首选模型是否在预算/速率限制内
4. 可用 → 路由到该模型
5. 不可用 → 沿 `fallback` 链尝试
6. 所有不可用 → 排队等待

---

## 三、上下文管理（Context Manager）

> Context Manager 是 llm_gateway 的兄弟模块，但独立存在。llm_gateway 在构建 messages 时从 Context Manager 获取各层上下文。

### 3.1 四层上下文模型

```
每个 Task 有一个独立的 Context 实例
Context = system_layer + session_layer + task_layer + history_layer + memory_layer
```

```
┌──────────────────────────────────────────────────────────────┐
│  Context (task_01)                                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ system_layer（固定）                                     │  │
│  │ ├ 角色 Soul（system prompt）                            │  │
│  │ ├ 技能定义（当前可用技能）                               │  │
│  │ └ 当前模型信息（模型名/切换方式）                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ session_layer（会话共享）                                │  │
│  │ ├ 会话目标（用户本次交互的目标描述）                      │  │
│  │ ├ 已决策事项（会话内已经达成一致的决策）                  │  │
│  │ └ 业务上下文（关联的项目/文件/需求）                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ task_layer（当前任务）                                   │  │
│  │ ├ 任务描述（当前 Task 的目标）                          │  │
│  │ ├ 任务状态（in_progress / waiting / done）              │  │
│  │ └ 任务依赖（该 Task 依赖的其他 Task 结果）               │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ history_layer（对话历史）                                │  │
│  │ ├ messages 列表（role/user/assistant/tool 消息）         │  │
│  │ ├ 上限 20 条（`MAX_HISTORY_MESSAGES`）                  │  │
│  │ ├ 超出上限时 → 最早的被压缩为摘要                        │  │
│  │ └ 摘要也作为一个消息保留                                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ memory_layer（按需注入）                                 │  │
│  │ ├ 从 memory_service 检索的长期记忆片段                  │  │
│  │ ├ 按相关性打分，top-K 注入                              │  │
│  │ └ 每个 Task 独立检索（不同任务检索不同记忆）              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Context 生命周期

```
                  Context 创建
                       │
                       ▼
              ┌─────────────────┐
              │    Hot Tier     │
              │   (内存 LRU)    │
              │  默认容量: 10   │
              └────────┬────────┘
                       │
           ┌───────────┼───────────┐
           │ 活跃中      │  LRU 淘汰 │
           ▼            ▼           ▼
    ┌────────────┐ ┌──────────────────┐
    │正在调 LLM  │ │   Warm Tier      │
    │context 在内存│ │  (SQLite 序列化)  │
    └────────────┘ │  默认容量: 100    │
                   └────────┬─────────┘
                            │
                   ┌────────┼────────┐
                   │ Task 完成│ LRU 淘汰│
                   ▼         ▼        ▼
            ┌──────────┐ ┌──────────────────┐
            │ 保留在Warm│ │   Cold Tier       │
            │ (可恢复)  │ │  (磁盘文件+摘要)   │
            └──────────┘ │  容量: 无限       │
                         │  (用户可清理)      │
                         └──────────────────┘
```

**状态迁移**：

| 事件 | 操作 |
|------|------|
| Task 创建 | 创建 Context → 放入 Hot Tier |
| Task 调 LLM | Context 在 Hot Tier 中 |
| Task 挂起（等待依赖/等待用户） | 保留在 Hot Tier（短期）或移到 Warm Tier（长期） |
| Task 完成 | Context 移到 Warm Tier |
| Hot Tier 满 | LRU 选出最久未活跃的 → 序列化到 Warm Tier |
| Warm Tier 满 | LRU 选出最旧的 → 压缩摘要 → 移到 Cold Tier |
| Cold Tier 满 | 通知用户清理或自动删除最旧的 |

### 3.3 上下文压缩

当 `history_layer` 的 token 数超过阈值时自动触发压缩：

```python
COMPRESSION_CONFIG = {
    "threshold_tokens": 40000,       # 超过这个值触发压缩
    "target_tokens": 2000,           # 压缩到的目标值
    "strategy": "llm_summary",       # 使用 LLM 生成摘要
    "preserve_last_n": 5,            # 保留最近 N 条完整消息
}
```

**压缩流程**：
1. 检测到 history_layer 超过 40K tokens
2. 取最早的 (total - 5) 条消息
3. 调用 LLM 生成摘要（用最便宜的模型）
4. 保留最近的 5 条完整消息
5. 摘要 + 最近 5 条 = 新的 history_layer

**压缩示例**：
```
压缩前:
  messages = [
    user: "帮我写个 API"
    assistant: "好的，分析需求..."
    tool_call: code_tool.read("main.py")
    tool_result: "...main.py 内容..."
    user: "用 FastAPI 实现"
    ...(共 200 条，50K tokens)
  ]

压缩后:
  messages = [
    { role: "system", content: "[摘要] 用户需要 FastAPI 项目...已创建 main.py..." }
    user: "最后一步，添加 JWT 认证"  # 最近 5 条保留
    assistant: "我来分析认证需求..."
    ...
  ]  # 约 5K tokens
```

### 3.4 上下文克隆（任务派生）

当 Agent 在任务执行过程中派生子任务：

```
Agent A 正在处理 task_01（写 API）
  ├── 发现需要先分析数据库结构
  ├── 创建子任务 task_01_analysis
  └── Context.clone(task_01, task_01_analysis)
      ├── system_layer = 继承 soul + 技能
      ├── session_layer = 继承会话目标
      ├── task_layer = "分析数据库结构"  ← 替换
      ├── history_layer = []             ← 清空
      └── memory_layer = 重新检索         ← 新的检索
```

**clone 规则**：
- system_layer：继承（角色的 soul 不变）
- session_layer：继承（同一个会话的业务目标共享）
- task_layer：替换（新任务的新描述）
- history_layer：清空（新任务从零开始）
- memory_layer：重新按新任务检索

### 3.5 上下文隔离

```
┌─────────────────────────────────────────────────────┐
│                    全局 Context Manager              │
│                                                      │
│  Hot Tier (内存):                                    │
│    ├─ Context(task_01, agent_A)   ← A 的代码上下文    │
│    ├─ Context(task_02, agent_B)   ← B 的测试上下文    │
│    └─ Context(task_03, agent_C)   ← C 的日志上下文    │
│                                                      │
│  Warm Tier (SQLite):                                 │
│    ├─ Context(task_00, agent_A)   ← A 已完成的任务    │
│    ├─ Context(task_04, agent_D)   ← D 挂起的任务      │
│    └─ ...                                            │
│                                                      │
│  Cold Tier (Files):                                  │
│    └─ ...                                            │
└─────────────────────────────────────────────────────┘

隔离原则：
  - Agent A 看不到 Agent B 的 context
  - Task_01 看不到 Task_02 的 history
  - 只有 session_layer 被同会话内的 Task 共享
  - memory_layer 按 Task 独立检索角色记忆
```

---

## 四、并发与上下文控制配置

```yaml
# ~/.suri/data/configs/llm_gateway.yaml
llm_gateway:
  # 并发控制
  max_concurrent_requests: 8           # 全局最大并发 LLM 调用
  per_model_limits:
    gpt4:
      rpm: 3
      tpm: 200000
      max_concurrency: 3
      queue_timeout: 30
      cost_per_1k_input: 0.03
      cost_per_1k_output: 0.06
    claude:
      rpm: 5
      tpm: 300000
      max_concurrency: 5
      queue_timeout: 30
      cost_per_1k_input: 0.015
      cost_per_1k_output: 0.075
    deepseek:
      rpm: 60
      tpm: 1000000
      max_concurrency: 10
      queue_timeout: 60
      cost_per_1k_input: 0.001
      cost_per_1k_output: 0.002
    local:
      max_concurrency: 2
      queue_timeout: 120

  # 模型路由
  model_routes:
    - task_pattern: "coding|refactor|debug"
      preferred: "gpt4"
      fallback: ["claude", "deepseek"]
    - task_pattern: "document|write|report"
      preferred: "claude"
      fallback: ["gpt4", "deepseek"]
    - task_pattern: "chat|learn|analyze"
      preferred: "deepseek"
      fallback: ["gpt4-mini", "claude"]
    - task_pattern: "review|audit"
      preferred: "gpt4"
      fallback: ["claude"]
    - task_pattern: ".*"
      preferred: "deepseek"
      fallback: ["gpt4-mini", "claude"]

  # 预算控制
  budget:
    mode: "monthly"
    monthly_limit_usd: 100
    notify_at_percent: [50, 80, 95]

  # 上下文管理
  context_manager:
    hot_tier_size: 10                  # 内存保持多少个活跃 Context
    warm_tier_size: 100                # SQLite 保持多少个挂起 Context
    history_compress_threshold: 40000  # tokens，超过触发压缩
    history_compress_target: 2000      # 压缩到的目标
    history_preserve_last: 5           # 压缩时保留最近 N 条完整消息
```

---

## 五、事件扩展

### 新增事件

| 事件 | 发布者 | 消费者 | 说明 |
|------|--------|--------|------|
| `context.created` | Context Manager | log_service | Context 创建 |
| `context.compress` | Context Manager | log_service | Context 压缩完成 |
| `context.migrate` | Context Manager | log_service | Context 在 Hot/Warm/Cold 间迁移 |
| `llm.queue_waiting` | llm_gateway | suri | 请求排队超过阈值 |
| `llm.rate_limited` | llm_gateway | suri | 模型被限流 |
| `llm.budget_exceeded` | llm_gateway | suri | 预算超限 |
| `llm.model_degraded` | llm_gateway | 调用方 | 模型降级（首选不可用，用备选） |

### `llm.request` 事件扩展

新增字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | string | 否 | 关联 Task ID（用于上下文管理） |
| `agent_id` | string | 否 | 发起请求的 Agent ID |
| `priority` | int | 否 | 优先级（0-3），默认 2 |
| `preferred_model` | string | 否 | 任务偏好模型 |
| `fallback_models` | array | 否 | 降级备选模型列表 |

---

## 六、性能预估

### 6.1 内存消耗

```
Hot Tier（10 个 Context）：
  1 个 Context ≈ 15K tokens ≈ 60KB
  10 个 ≈ 600KB → 可忽略

如果 history 膨胀到 50K tokens ≈ 200KB：
  10 个 ≈ 2MB → 仍然很小

Warm Tier（100 个 Context 序列化到 SQLite）：
  1 个 ≈ 50KB（JSON）
  100 个 ≈ 5MB → 可接受

结论：瓶颈不在内存，在 LLM API
```

### 6.2 并发吞吐

```
系统瓶颈完全在 LLM API：

  GPT-4:    3 RPM,   200K TPM,  3 并发
  Claude:   5 RPM,   300K TPM,  5 并发
  DeepSeek: 60 RPM,  1M TPM,   10 并发
  本地:     无限制,  无限制,    2 并发（硬件限制）
  ─────────────────────────────────────────
  总计:     最多 ~20 个 LLM 调用同时进行

EventBus 和 Context Manager 自身开销 < 1ms
```

### 6.3 真正的瓶颈

| 瓶颈 | 限制 | 应对 |
|------|------|------|
| LLM API 限流 | GPT-4 3 RPM | 排队 + 降级 + 模型路由 |
| LLM API 费用 | $30-60/百万 tokens | 本地模型做简单任务 |
| 网络延迟 | 每次调用 2-10s | 异步并发，不阻塞其他 Agent |
| 上下文窗口 | 128K tokens | 三级压缩 + summary 替代 |
| Agent / Task 数量 | 无硬上限 | Hot/Warm/Cold 三级自动换出 |

---

## 七、迭代规划

| 迭代 | 内容 | 状态 |
|------|------|------|
| 迭代 1 | 基础模型调用、模型切换、Token 统计 | ✅ 已实现 |
| 迭代 2 | **并发调度**（请求队列 + 速率控制 + 模型路由） | 📋 规划中 |
| 迭代 3 | **Context Manager**（四层上下文 + 三级缓存 + 压缩） | 📋 规划中 |
| 迭代 4 | 预算控制、消费记录、通知 suri | 🔮 远期 |
| 迭代 5 | Web 面板配置界面 | 🔮 远期 |