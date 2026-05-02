# 系统工作流程定义

> 本文档定义 suri-agent 的标准工作流程。所有流程由角色通过调用插件能力完成，和程序无关。

---

## 1. 标准任务流（单角色 / 无项目组）

**场景**：单角色可完成的常规任务，未成立项目组

```
用户输入
    │
    ▼
access ──▶ event: user.input
    │
    ▼
suri 角色接收
    │
    ▼
分析需求 → 判断是否需分解
    │
    ├── 简单任务 ───────────────────────┐
    │                                   │
    │    直接调用插件执行                 │
    │    ├─ llm_gateway（如需模型）       │
    │    ├─ mcp_framework（如需工具）     │
    │    └─ memory_service（读写记忆）    │
    │                                   │
    └── 复杂任务 ───────────────────────┤
        │                               │
        ▼                               │
    调用 task_planner.plan()            │
        │                               │
        ▼                               │
    生成 TaskPlan（步骤序列 + 依赖）      │
        │                               │
        ▼                               │
    调用 agent_registry.create_agent()  │
        │                               │
        ▼                               │
    task_scheduler 按优先级调度步骤      │
        │                               │
        ▼                               │
    各步骤执行（调用对应角色/插件）       │
        │                               │
        ▼                               │
    agent_registry 更新步骤状态          │
        │                               │
        ▼                               ▼
    全部完成 ────────────────────────▶ suri 汇总结果
                                        │
                                        ▼
                                    返回给用户
```

---

## 2. 项目组多角色协作流

**场景**：复杂任务，已成立项目组，有项目总监和 Telegram 群组

```
用户在 Telegram 项目群组中说明任务
    │
    ▼
access/telegram 捕获消息，@路由给项目总监
    │
    ▼
项目总监接收并分析需求 → 识别涉及角色
    │
    ▼
项目总监调用 task_planner 生成协作规划
    │
    ▼
┌─────────────────────────────────────────────┐
│ step_1: 项目总监理解需求，确认整体目标       │
│ step_2: 各角色评估自身负责范围               │
│ step_3~N: 各角色并行/串行执行关键步骤        │
│ step_N+1: 项目总监汇总各角色输出，整合交付   │
└─────────────────────────────────────────────┘
    │
    ▼
项目总监调用 task_scheduler 调度执行
    │
    ├── 并行步骤：同时调度多个角色
    │   └─ 各角色通过 role_comm 通信同步
    │       └─ 关键进度通过 access 投影到 Telegram 群
    │
    └── 串行步骤：等待依赖完成后调度
    │
    ▼
项目总监定期在群中播报进度
    │
    └── 如有受阻 → 项目总监先协调，无法解决再汇报 suri
    │
    ▼
全部步骤完成
    │
    ▼
项目总监在群中汇总 → 交付用户
```

**协作规则**：
- 用户在项目群中 @项目总监 或 @实现角色 直接对话
- 项目总监负责调度，suri 不介入日常执行
- 各角色进度通过 access 投影到 Telegram 群
- 每 N 分钟（默认 1800s）项目总监在群中播报进度

**协作规则**：
- 并行步骤的角色通过 `role_comm` 交换中间结果
- `task_scheduler` 通过 DAG 依赖确保步骤按正确顺序执行
- `agent_registry` 跟踪每个子 Agent 的进度
- 每 N 分钟（默认 1800s）同步一次进度

---

## 3. 异常处理流

**场景**：任务执行失败或受阻

```
任务执行失败
    │
    ▼
task_scheduler 记录失败，触发重试
    │
    ├── 重试成功 ──▶ 继续执行
    │
    └── 重试耗尽（3 次）
        │
        ▼
    发布 event: task.failed
        │
        ▼
    interrupt_handler 介入
        │
        ▼
    分类失败原因
        │
        ├── missing_tool ──▶ escalate_to_dev()
        ├── knowledge_gap ──▶ escalate_to_user() / 搜索
        ├── permission_denied ──▶ escalate_to_hr() / 申请权限
        ├── dependency_failed ──▶ 自动重试 / escalate_to_user()
        ├── timeout ──▶ 自动重试 / 调整超时配置
        └── resource_exhausted ──▶ 等待 / escalate_to_suri()
        │
        ▼
    生成用户决策建议
        │
        ▼
    用户选择：继续 / 升级 / 取消
        │
        ├── 继续 ──▶ 重新调度
        ├── 升级 ──▶ 创建新 Agent 处理升级任务
        └── 取消 ──▶ agent_registry.cancel_agent()
```

**重试策略**：
- 退避间隔：[0s, 30s, 120s]
- 最大重试：3 次
- 重试类型：dependency_failed / timeout（可配置）

---

## 4. 用户决策回路

**场景**：任务执行中需要用户确认或选择

```
角色执行到需要用户决策的步骤
    │
    ▼
整理上下文（当前进度 + 可选方案）
    │
    ▼
生成 2~3 个明确选项
    │
    ▼
通过 access 向用户呈现
    │
    ▼
等待用户回复（默认超时 600s）
    │
    ├── 超时 ──▶ 默认行为：暂停等待
    │
    └── 用户回复
        │
        ├── 选择某选项 ──▶ 继续执行对应分支
        ├── 自定义指令 ──▶ 解析指令，更新规划
        └── 拒绝 ──▶ 取消当前步骤/任务
        │
        ▼
    更新 task_planner 规划
        │
        ▼
    task_scheduler 继续调度
```

---

## 5. 能力缺口流

**场景**：现有角色/插件无法处理用户需求

```
suri 分析需求 → 遍历角色能力索引
    │
    ├── 有匹配角色 ──▶ 标准任务流
    │
    └── 无匹配角色
        │
        ▼
    识别能力缺口
        │
        ▼
    向用户展示缺口说明
        │
        ├─ 现有角色能力清单
        ├─ 缺口描述
        └─ 建议方案（创建新角色 / 扩展现有角色 / 使用通用工具）
        │
        ▼
    用户确认创建新角色
        │
        ▼
    调用 role_manager.create_role()
        │
        ├─ 分析需求
        ├─ 设计能力矩阵
        ├─ 生成 Soul 文件
        └─ 初始化角色目录
        │
        ▼
    通知 suri 新角色就绪
        │
        ▼
    重新调度任务 → 标准任务流
```

---

## 6. 自优化上报流

**场景**：系统通过元学习发现改进机会

```
PluginSelfLearning / RoleLearner / ProgramLearner 分析
    │
    ▼
生成 UpgradeReport / FrameworkImprovementReport
    │
    ▼
upgrade_manager.save_report()
    │
    ▼
状态: PENDING → SUBMITTED
    │
    ▼
upgrade_manager 定期 check_and_notify()
    │
    ▼
汇总待处理报告
    │
    ▼
suri 角色汇总，向用户呈现升级方案
    │
    ├─ 变更原因
    ├─ 具体变更内容
    ├─ 影响范围
    ├─ 回滚策略
    └─ 风险评估
    │
    ▼
用户确认
    │
    ├── 拒绝 ──▶ upgrade_manager.update_status(REJECTED)
    ├── 延期 ──▶ upgrade_manager.update_status(DEFERRED)
    │
    └── 确认
        │
        ▼
    执行代码/配置变更
        │
        ├─ IDE 模式生成变更文件
        ├─ 或代码补丁热更新
        └─ suri_core 变更需冒烟测试
        │
        ▼
    验证（健康检查 / 冒烟测试）
        │
        ├── 通过 ──▶ upgrade_manager.update_status(IMPLEMENTED)
        │
        └── 失败 ──▶ 执行回滚策略
```

**闭环规则**：
- 报告生命周期必须走完状态机
- 无报告可长期处于 PENDING 状态（定期检查）
- 实施失败必须回滚并记录原因

---

## 7. 角色删除流程

```
删除发起（admin / suri / 用户）
    │
    ▼
检查目标角色类型
    │
    ├── core（suri）──▶ 拒绝（核心角色不可删除）
    │
    └── 其他类型
        │
        ▼
    检查活跃 Agent
        │
        ├── 有活跃 Agent ──▶ 等待完成 / 强制取消
        │
        └── 无活跃 Agent
            │
            ▼
    归档角色数据
        ├─ Soul → _archived/{role_id}/soul.md
        ├─ memories → _archived/{role_id}/memories/
        ├─ skills → _archived/{role_id}/skills/
        └─ insights → _archived/{role_id}/insights/
        │
        ▼
    发布 role.destroyed 事件
        │
        ▼
    清理运行时数据（30 天后自动物理删除）
```

**规则**：
- 只有 `admin` 和 `suri` 可发起角色删除
- 删除前必须归档，保留期 30 天
- 项目总监（project_director）在项目归档时可选择保留或归档，但不可删除自身
