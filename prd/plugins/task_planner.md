# task_planner 插件 PRD

## 定位

任务分解与依赖管理。被角色调用，将复杂任务分解为带依赖关系的可执行步骤序列。

**关键约束**：只做规划，不执行任务，不调用模型执行业务逻辑。规划结果通过事件交给 task_scheduler 调度。

## 功能需求

### 1. 任务规划（PlanGeneration）

双轨策略：规则驱动（快速路径）+ LLM 驱动（智能路径）。

**规则驱动**：
- 匹配预设模板 → 直接生成步骤序列
- 无需 LLM 调用，毫秒级响应

**LLM 驱动**：
- 无模板匹配或用户要求智能规划时触发
- 输出严格 JSON（task_name / steps / dependencies / involved_roles / estimated_total_time）
- 失败时降级为 `_generic_plan`

### 2. 预设任务模板（TaskTemplates）

```python
TASK_TEMPLATES = {
    "code": {
        "steps": ["理解需求", "识别依赖", "设计", "编码", "自测", "交付"],
        "default_role": "suri_dev"
    },
    "review": {
        "steps": ["收集变更", "逐文件审查", "影响分析", "出具报告"],
        "default_role": "suri_review"
    },
    "statistics": {
        "steps": ["数据抽取", "清洗", "计算聚合", "可视化"],
        "default_role": "suri_data"
    },
    "role_creation": {
        "steps": ["分析需求", "设计能力矩阵", "生成 Soul", "创建目录", "通知 suri"],
        "default_role": "suri_hr"
    }
}
```

### 3. 依赖管理（DependencyGraph）

- `TaskStep.depends_on` 定义前置步骤
- 自动构建 DAG，检测循环依赖
- `get_ready_steps()` 返回依赖已满足的步骤
- 步骤状态：pending → in_progress → completed / blocked

### 4. 多角色协作规划

```
step_1: suri 理解需求
    │
    ▼
step_2: 各角色评估自身负责范围
    │
    ▼
step_3..N: 各角色并行执行关键步骤
    │
    ▼
step_N+1: suri 汇总各角色输出，整合交付
```

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `task.plan_requested` | 角色 | 生成任务规划 |
| `task.replan_requested` | 角色/中断处理器 | 重新规划（如步骤受阻） |

### 发布事件

| 事件 | 目标 | 说明 |
|------|------|------|
| `task.planned` | task_scheduler / 角色 | 规划完成 |
| `task.step_ready` | task_scheduler | 某步骤依赖已满足，可执行 |
| `task.plan_updated` | task_scheduler / 角色 | 规划变更 |

### 方法

```python
class TaskPlanner:
    async def plan(self, task_text: str, context: Dict = None) -> TaskPlan
    def _rule_based_plan(self, task_text: str, matched_roles: List[str]) -> TaskPlan
    async def _llm_plan(self, task_text: str, context: Dict) -> TaskPlan
    def _build_dag(self, steps: List[TaskStep]) -> DAG
    def get_ready_steps(self, plan_id: str) -> List[TaskStep]
    def update_step_status(self, plan_id: str, step_id: str, status: str) -> bool
```

## 数据模型

```python
@dataclass
class TaskPlan:
    plan_id: str
    task_name: str
    steps: List[TaskStep]
    involved_roles: List[str]
    dependencies: List[str]
    estimated_total_time: Optional[int] = None
    created_at: str = ""

@dataclass
class TaskStep:
    step_id: str
    description: str
    assignee: str
    status: str = "pending"           # pending | in_progress | completed | blocked
    depends_on: List[str] = None
    estimated_time: Optional[int] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    block_reason: Optional[str] = None
    result: Optional[str] = None
```

## 事件 Payload Schema

### 订阅事件

#### `task.plan_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_text` | string | 是 | 任务描述 |
| `context` | object | 否 | 上下文信息 |
| `matched_roles` | array | 否 | 已匹配的角色列表 |
| `project_id` | string | 否 | 所属项目 |

#### `task.replan_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 原规划 ID |
| `reason` | string | 是 | 重新规划原因 |
| `blocked_step_id` | string | 否 | 受阻的步骤 ID |

### 发布事件

#### `task.planned`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 规划 ID |
| `task_name` | string | 是 | 任务名称 |
| `steps` | array | 是 | 步骤列表（TaskStep 数组）|
| `involved_roles` | array | 是 | 涉及角色 |
| `estimated_total_time` | integer | 否 | 预估总耗时（分钟）|
| `project_id` | string | 否 | 所属项目 |

#### `task.step_ready`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 规划 ID |
| `step_id` | string | 是 | 步骤 ID |
| `assignee` | string | 是 | 负责角色 |

#### `task.plan_updated`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 规划 ID |
| `updated_steps` | array | 是 | 变更的步骤 |
| `update_reason` | string | 是 | 变更原因 |

## 配置项

```yaml
task_planner:
  default_planning_mode: "auto"     # auto | rule | llm
  llm_model: "gpt-4o-mini"          # 规划用模型（可选轻量模型）
  max_steps_per_plan: 20
  enable_template_matching: true
  templates:
    code: { steps: [...], default_role: "suri_dev" }
    review: { steps: [...], default_role: "suri_review" }
    statistics: { steps: [...], default_role: "suri_data" }
    role_creation: { steps: [...], default_role: "suri_hr" }
```

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：llm_gateway（LLM 辅助规划）
- 上游：role_manager（获取角色信息、能力索引）
- 下游：task_scheduler（调度执行）

## 生命周期

1. `init()` → 加载预设模板、初始化规划缓存
2. `start()` → 标记就绪
3. `stop()` → 中断正在进行的 LLM 规划请求
4. `cleanup()` → 清空规划缓存

## 安全边界

- LLM 规划失败时自动降级为 generic_plan，不阻塞流程
- 循环依赖检测，发现时抛出错误事件
- 步骤数超过 max_steps_per_plan 时截断并告警
- **核心原则**：只做步骤分解，不执行任何业务操作
