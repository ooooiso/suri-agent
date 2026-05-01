# core/

> 关联代码: suri-agent/core/context.py, suri-agent/core/model_router.py, suri-agent/core/task_dispatcher.py, suri-agent/core/tool_executor.py, suri-agent/core/task_plan.py, suri-agent/core/task_state.py, suri-agent/core/agent_registry.py, suri-agent/core/state_card.py, suri-agent/core/department_registry.py, suri-agent/core/interrupt_handler.py, suri-agent/core/message_bus.py

核心调度层：负责任务调度、模型路由、审批、上下文、工具执行、文档同步，以及 V3.0 新增的多 Agent 任务管理、状态卡片、部门扩展、中断处理和内部通信。

## 模块说明

### V2.0 核心模块

| 文件 | 功能 |
|------|------|
| `task_dispatcher.py` | 任务调度器：接收→解析→匹配部门→下发总监→跟踪→交付 |
| `model_router.py` | 模型路由：按任务类型**智能选择模型**，超时/报错时自动降级 |
| `context.py` | 上下文管理：构建角色上下文，注入 Soul、规则、技能、记忆、**模型信息** |
| `approval.py` | 审批引擎：安全审批流程管理 |
| `tool_executor.py` | 工具执行器：调用公共工具，执行角色技能中的脚本 |
| `doc_sync.py` | 文档同步服务：检测变更→大模型生成摘要→用户确认→写入核心记忆库 |

### V3.0 新增模块

| 文件 | 功能 | 关联文档 |
|------|------|----------|
| `task_plan.py` | 任务规划器：接收用户需求，生成结构化任务分解草案（步骤列表 + 涉及角色） | 本文档 |
| `task_state.py` | 任务状态中心：SQLite 集中存储所有 Agent 和步骤状态，支持跨角色查询和持久化 | 本文档 |
| `agent_registry.py` | Agent 注册表：维护 user_id → List[Agent] 映射，支持创建/销毁/查询/归档，管理独立对话上下文 | 本文档 |
| `state_card.py` | 状态卡片渲染器：将活跃 Agent 转换为终端/Telegram 可展示的格式化 ASCII 看板 | 本文档 |
| `department_registry.py` | 部门注册表：读取 `departments.yaml`，维护部门-能力-负责人映射，支持 hr 动态创建部门 | 本文档 |
| `interrupt_handler.py` | 中断处理器：角色上报 blocked 时暂停任务，分析原因并生成升级建议 | 本文档 |
| `message_bus.py` | 消息总线：轻量级发布-订阅队列，角色完成子步骤时广播状态更新，suri 订阅汇总 | 本文档 |

---

## 智能模型路由（model_router.py）

`ModelService.call_model()` 支持通过任务内容自动选择最合适的模型：

```python
await model.call_model(
    prompt,
    model_type='chat',
    auto_select=True,           # 启用智能路由
    task_content=raw_input,     # 用户原始输入，用于推断任务类型
)
```

路由流程：
1. `TaskDispatcher.dispatch()` 将 `raw_input` 传给 `ModelService`
2. `ModelService` 委托 `ModelManager.select_model_for_task()` 分析任务内容
3. 推断所需能力（coding / vision / reasoning / long_context / fast / chat）
4. 从用户已配置的模型中筛选匹配项，按成本等级排序
5. 调用选中的模型；失败时按传统降级策略 fallback

**示例**：
- 用户说 "帮我写个 Python 爬虫" → 选具备 `coding` 能力的模型（如 DeepSeek Coder）
- 用户说 "你好" → 选具备 `fast` 能力的免费模型（如 GLM-4.7-Flash）
- 用户说 "总结这份 5 万字报告" → 选具备 `long_context` 能力的模型

---

## V3.0 多 Agent 任务管理架构

### 架构概览

```
用户输入 → suri_process()
    │
    ├──→ TaskPlanService.create_plan() → 生成任务分解
    │
    ├──→ AgentRegistry.create_agent() → 创建 Agent（绑定步骤）
    │
    ├──→ 调度执行（通过 Agent 上下文隔离）
    │       ├──→ _execute_dispatch() → 角色执行
    │       └──→ MessageBus.broadcast_status() → 广播状态
    │
    ├──→ 结果回流 → _summarize_result() / _summarize_multi_result()
    │
    ├──→ MemoryService.save_experience() → 保存经验
    │
    └──→ StateCardRenderer.render_terminal() → 追加状态卡片
```

### 核心流程

1. **任务规划** (`task_plan.py`)
   - 接收用户需求，调用 LLM 生成结构化任务分解草案
   - 输出 `TaskPlan`：包含步骤列表、涉及角色、预估耗时

2. **Agent 创建** (`agent_registry.py`)
   - 每个任务创建独立 Agent，绑定 `TaskPlan` 步骤
   - 中途新需求 → 创建并行 Agent（同一 user_id 下多 Agent）
   - 子任务 → `create_sub_agent()` 创建子 Agent（parent_agent_id 关联）

3. **状态管理** (`task_state.py`)
   - SQLite 集中存储所有 Agent 和步骤状态
   - 步骤状态机：`pending → in_progress → completed/blocked`
   - Agent 状态：`planning → running → paused → completed/blocked`

4. **状态卡片** (`state_card.py`)
   - `render_terminal()`：ASCII 分割线 + emoji 状态图标
   - `render_telegram()`：紧凑 Markdown 格式，支持消息编辑更新
   - `render_for_broadcast()`：中台播报格式「【昵称】在【任务名】完成：...」

5. **内部通信** (`message_bus.py`)
   - 角色完成子步骤时通过 `broadcast_status()` 广播
   - suri 通过 `consume()` 订阅汇总
   - SQLite 持久化队列，支持重启后恢复

6. **中断处理** (`interrupt_handler.py`)
   - 角色返回 blocked → 分析 block_reason
   - 生成建议：让 dev 开发工具 / 让 hr 招聘角色 / 用户手动提供信息
   - suri 向用户说明情况，等待决策（继续/升级/取消）

### Agent 上下文隔离

每个 Agent 拥有独立的 `AgentContext`（独立 messages 列表），与 suri 主上下文隔离：
- 多 Agent 并行时消息不串扰
- 一个 Agent 异常不影响其他 Agent
- LLM API 串行调用是物理限制，Agent 价值在于状态隔离

---

## 部门扩展机制 (department_registry.py)

### 数据来源

- **中枢部门**（suri, suri_dev, suri_hr, suri_review, suri_stats）硬编码
- **扩展部门**从 `departments.yaml` 动态加载

### 能力匹配

`suri` 按能力关键词匹配最合适的部门：
```python
dept = dept_registry.find_department_by_ability(["UI", "设计"])
# → 返回 design 部门
```

### 动态创建

`hr` 可通过 `create_department()` 创建新部门：
- 自动更新 `departments.yaml`
- 自动生成部门经理 Soul 模板
- 负责人接收 suri 下发的任务，在部门内进行二次调度

---

## 事件记录

- 新增 `doc_sync.py` 文档同步服务
- **新增智能模型路由**：`model_router.py` 支持 `auto_select` 按任务内容自动选模
- **P0 调度规则改造**：`ContextService._format_tools_prompt()` 和 `ToolService.execute()` 中的提示文本去硬编码，改为通用描述（不再直接引用 `suri-dev`）
- **V2.0 角色重命名**：`suri-dev` → `suri_dev`，`suri-hr` → `suri_hr`，`document-review` → `suri_review`，`analyst` → `suri_stats`，保留 `_ROLE_ALIASES` 兼容层
- **V2.0 动态输出路由**：OutputRouter 从 Soul `output_channels` 动态构建路由，TerminalChannel 支持昵称显示
- **V2.0 经验日志**：`memory.py` 新增 `experiences` 表 + `save_experience()` API
- **V2.0 核心角色保护**：SecurityService `CORE_ROLES` + `is_core_role()`，Soul 文件删除保护
- **V3.0 多 Agent 架构**：TaskPlan + TaskStateService + AgentRegistry + StateCardRenderer，从"单次函数调用"升级为"长期任务管理器"
- **V3.0 部门扩展**：DepartmentRegistry 支持动态创建扩展部门，hr 按能力矩阵匹配
- **V3.0 中断处理**：InterruptHandler 分析 block_reason，生成升级建议
- **V3.0 内部通信**：MessageBus SQLite 持久化队列，支持广播和点对点
