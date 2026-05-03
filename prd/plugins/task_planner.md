# task_planner 插件 PRD

## 定位

任务分解与依赖管理。被角色调用，将复杂任务分解为带依赖关系的可执行步骤序列。

**关键约束**：只做规划，不执行任务，不调用模型执行业务逻辑。规划结果通过事件交给 task_scheduler 调度。

---

## 功能需求

### 1. 任务规划（PlanGeneration）

双轨策略：规则驱动（快速路径）+ LLM 驱动（智能路径）。

**规则驱动**：
- 匹配预设模板 → 直接生成步骤序列
- 无需 LLM 调用，毫秒级响应
- 匹配逻辑：任务文本包含模板关键词（如"实现""编写""code"→ code 模板）

**LLM 驱动**：
- 无模板匹配或用户要求智能规划时触发
- 输出严格 JSON（见下方 Schema）
- 失败时降级为 `_generic_plan`

**generic_plan 降级算法**：
- 按中文句号/英文句点/分号/换行符拆分任务文本
- 每个非空片段作为一个步骤
- 步骤间无依赖关系（全部并行）
- 分配角色：suri
- 示例：输入"创建目录结构。编写 manifest.json。实现核心逻辑" → 3 个并行步骤

### 2. 规则注册机制（RuleProvider）

规则不再硬编码在 task_planner 中，而是由各插件通过 `RuleProvider` 接口动态注册。

**注册流程**：
```
插件启动时（start() 方法）：
    │
    ├─ 调用 event_bus.publish("task_planner.register_rules", {templates: [...]})
    │
    ▼
task_planner 收到注册事件：
    ├─ 将模板加入规则索引
    ├─ 按 priority 排序
    └─ 更新关键词匹配树
```

**匹配逻辑**：
```
用户输入 → task_planner.plan()
    │
    ├─ 遍历所有已注册模板（内置 + 插件注册）
    │   ├─ 按 priority 降序
    │   └─ 检查关键词匹配
    │
    ├─ 匹配到 → 使用该模板生成步骤
    │
    ├─ 匹配到多个 → 取 priority 最高的
    │
    └─ 未匹配 → 走 LLM 驱动 / generic_plan
```

**内置默认模板**（task_planner 自带，优先级 0）：

| template_id | keywords | steps | 说明 |
|------------|----------|-------|------|
| `builtin.code` | 实现, 编写, 开发, code, implement, write | 理解需求→识别依赖→设计→编码→自测→交付 | 代码开发 |
| `builtin.review` | 审查, review, 检查, audit | 收集变更→逐文件审查→影响分析→出具报告 | 代码审查 |
| `builtin.statistics` | 统计, 分析, stat, analyze, 报告 | 数据抽取→清洗→计算聚合→可视化 | 数据分析 |
| `builtin.role_creation` | 创建角色, new role, 角色, 添加角色 | 分析需求→设计能力矩阵→生成 Soul→创建目录→通知 suri | 角色创建 |

**插件注册示例**（code_tool 插件注册）：
```python
class CodeToolPlugin(PluginInterface, RuleProvider):
    def get_task_templates(self):
        return [
            TaskTemplate(
                template_id="code_tool.write_file",
                name="文件写入",
                keywords=["写入", "创建文件", "write", "create", "生成代码"],
                steps=[
                    TemplateStep("分析文件结构", "suri"),
                    TemplateStep("生成代码内容", "suri"),
                    TemplateStep("写入文件", "suri"),
                    TemplateStep("运行测试验证", "suri"),
                ],
                default_role="suri",
                priority=10  # 高于内置模板
            ),
        ]
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

---

## LLM 规划输出 JSON Schema

当规则驱动无法匹配模板时，task_planner 调用 LLM 生成规划。LLM 必须返回以下格式的 JSON：

```json
{
  "task_name": "string, 任务名称",
  "steps": [
    {
      "step_id": "string, 步骤唯一标识，如 step_1",
      "description": "string, 步骤描述",
      "assignee": "string, 负责角色，默认 suri",
      "depends_on": ["string, 前置步骤 ID 列表，如 step_0"],
      "estimated_time": "integer, 预估分钟数，可选"
    }
  ],
  "involved_roles": ["string, 涉及的所有角色列表"],
  "estimated_total_time": "integer, 预估总耗时（分钟），可选"
}
```

**约束**：
- steps 数组长度 1-20
- depends_on 引用的 step_id 必须在 steps 中存在
- 不允许循环依赖（A→B→A）
- involved_roles 必须包含所有 assignee 中出现的角色

**示例输出**：
```json
{
  "task_name": "实现 cron_service 插件",
  "steps": [
    {"step_id": "step_1", "description": "创建目录结构", "assignee": "suri", "depends_on": []},
    {"step_id": "step_2", "description": "编写 manifest.json", "assignee": "suri", "depends_on": ["step_1"]},
    {"step_id": "step_3", "description": "编写 plugin.py 骨架", "assignee": "suri", "depends_on": ["step_1"]},
    {"step_id": "step_4", "description": "实现核心调度逻辑", "assignee": "suri", "depends_on": ["step_3"]},
    {"step_id": "step_5", "description": "编写测试用例", "assignee": "suri", "depends_on": ["step_4"]},
    {"step_id": "step_6", "description": "运行测试验证", "assignee": "suri", "depends_on": ["step_5"]}
  ],
  "involved_roles": ["suri"],
  "estimated_total_time": 120
}
```

---

## 接口定义

### 订阅事件

| 事件 | 来源 | 处理 |
|------|------|------|
| `task.plan_requested` | 角色 | 生成任务规划 |
| `task.replan_requested` | 角色/中断处理器 | 重新规划（如步骤受阻） |
| `task_planner.register_rules` | 插件 | 注册任务模板 |

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
    def _generic_plan(self, task_text: str) -> TaskPlan
    def _build_dag(self, steps: List[TaskStep]) -> DAG
    def get_ready_steps(self, plan_id: str) -> List[TaskStep]
    def update_step_status(self, plan_id: str, step_id: str, status: str) -> bool
    def register_template(self, template: TaskTemplate) -> bool
    def unregister_template(self, template_id: str) -> bool
```

---

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

---

## 事件 Payload Schema

### 订阅事件

#### `task.plan_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_text` | string | 是 | 任务描述 |
| `context` | object | 否 | 上下文信息（含 session_id、历史消息等） |
| `matched_roles` | array | 否 | 已匹配的角色列表 |
| `project_id` | string | 否 | 所属项目 |

#### `task.replan_requested`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plan_id` | string | 是 | 原规划 ID |
| `reason` | string | 是 | 重新规划原因 |
| `blocked_step_id` | string | 否 | 受阻的步骤 ID |

#### `task_planner.register_rules`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 注册插件的 ID |
| `templates` | array | 是 | TaskTemplate 数组 |

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

---

## 配置项

```yaml
task_planner:
  default_planning_mode: "auto"     # auto | rule | llm
  llm_model: "deepseek/deepseek-chat"  # 规划用模型（可用轻量模型）
  max_steps_per_plan: 20
  enable_template_matching: true
```

---

## 与 role_manager 的边界

| 维度 | task_planner | role_manager |
|------|-------------|--------------|
| **获取信息** | 角色列表 + 技能列表（用于分配 assignee） | Soul 内容、能力索引 |
| **调用方式** | 通过 role_manager.list_roles() 获取角色信息 | 不调用 task_planner |
| **数据依赖** | 不读取 Soul 文件，不解析 YAML frontmatter | 管理 Soul 文件的完整生命周期 |
| **职责** | 只做步骤分解，不管理角色身份 | 管理角色身份和技能 |

---

## 依赖关系

- 上游：suri_core（EventBus）
- 上游：llm_gateway（LLM 辅助规划）
- 上游：role_manager（获取角色列表和技能列表，不获取 Soul 内容）
- 下游：task_scheduler（调度执行）

---

## 生命周期

1. `init()` → 加载内置模板、初始化规则索引
2. `start()` → 标记就绪
3. `stop()` → 中断正在进行的 LLM 规划请求
4. `cleanup()` → 清空规则索引

---

## 热更新与解耦

### 1. 任务模板外部化

当前 `_load_builtin_templates()` 中的内置模板硬编码在代码中，无法热更新。

**优化方案**：
- 创建 `~/.suri/data/templates/task_templates.yaml` 作为外部模板文件
- `_load_builtin_templates()` 改为从外部文件加载
- 保留内置模板作为 fallback（仅当外部文件不存在时）

### 2. 支持热更新

```python
def register_events(self):
    self.event_bus.subscribe("config.updated", self._on_config_updated)
    self.event_bus.subscribe("task_planner.templates_updated", self._on_templates_updated)

async def _on_config_updated(self, event: Event):
    if event.payload.get("plugin_id") == "task_planner":
        self._load_templates()

async def _on_templates_updated(self, event: Event):
    """其他插件通知模板变更"""
    self._load_templates()
```

### 3. 模板注册事件

- 新增 `task_planner.templates_updated` 事件类型
- 其他插件可通过发布此事件通知 task_planner 刷新模板
- 重新加载时保留内置模板（不可覆盖）

---

## 安全边界

- 模板注册优先级限制（≤99）
- 内置模板不可注销
- LLM 规划结果需校验（循环依赖检测）
- 步骤数上限（默认 20）

---

## 已知问题 & 优化项（迭代 2 已修复）

### 1. `_template_to_plan` 的 depends_on 逻辑有 bug ✅ 已修复

**问题描述**：`elif i > 0: depends_on = [f"step_{i}"]` 中 `step_{i}` 是当前步骤 ID（自引用），应改为引用前一步。

**修复方案**：改为 `depends_on = [steps[i-1].step_id]`，引用前一步的 step_id。

### 2. `_generic_plan` 拆分逻辑过于简单 ✅ 已修复

**问题描述**：正则 `re.split(r'[。；;.\n]', task_text)` 会把 `manifest.json` 中的 `.` 也当作分隔符。

**修复方案**：改用 `re.split(r'[。；;\n]', task_text)`，移除英文句点 `.` 作为分隔符，避免 manifest.json 被误拆。

### 3. 关键词匹配冲突 ✅ 已修复

**问题描述**：`"创建一个新角色"` 同时匹配 `builtin.code`（关键词含"创建"）和 `builtin.role_creation`（关键词含"角色"），且 code 模板 priority=0 排在前面。

**修复方案**：关键词匹配改为优先匹配**更长的关键词**。遍历模板时，计算匹配到的关键词长度之和，取总长度最大的模板。如"新增角色"匹配到 role_creation 的"新增角色"（4 字）> code 的"新增"（2 字）。

### 4. `_wait_for_llm_response` 事件订阅未取消 ✅ 已修复

**问题描述**：`subscribe` 后没有对应的 `unsubscribe` 机制，每次 LLM 规划都会新增订阅。

**修复方案**：在 `_wait_for_llm_response` 的 `finally` 块中调用 `self._event_bus.unsubscribe("llm.response", callback)` 取消订阅，防止内存泄漏。