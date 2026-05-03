# 角色工作流（Agent 版）

> 描述单个角色在 suri-agent 中的标准工作流程。每个角色是独立的 Agent，主动驱动任务执行。

---

## 核心原则

```
角色 = 独立的 Agent（智能体）
  ├── 主动驱动任务，不需要 suri 介入每一步
  ├── 通过自己的技能调用插件/MCP 工具
  ├── 可以自学、自增技能
  ├── 可以与其他角色通信协作
  └── 在所有不知道怎么做时，可以主动申请升级
```

---

## 1. 角色接收任务

```
角色通过订阅事件接收任务
    │
    ├── role.task_assigned ──▶ suri 分配的任务
    ├── role_comm.message_received ──▶ 其他角色的协作请求
    ├── user.input ──▶ 直接用户请求（通过 role_manager 路由）
    └── cron_service.task ──▶ 定时触发的任务
    │
    ▼
角色读取自身上下文
    │
    ├── Soul 文件（soul.md）— 自我定义
    ├── 技能列表（skills/）— 已掌握的技能
    ├── 历史记忆（memories/）— 经验积累
    ├── 学习洞察（insights/）— 最近高置信度洞察
    └── 当前任务信息
    │
    ▼
角色分析需求
```

---

## 2. 角色分析并分解任务

```
角色分析接收到的任务
    │
    ├── 判断：这个任务我能用现有技能直接处理吗？
    │       │
    │       ├── 能 ──▶ 直接执行（步骤 3）
    │       │
    │       └── 不能
    │           │
    │           ├── 调用 task_planner 分解任务
    │           │   └── 生成 TaskPlan（步骤序列 + 依赖）
    │           │
    │           ├── 调用 agent_registry.create_agent() 创建执行实例
    │           │
    │           └── 按步骤执行循环（步骤 3）
    │
    └── 判断：是否需要其他角色协作？
            │
            ├── 不需要 ──▶ 自行执行
            │
            └── 需要 ──▶ 调用 role_comm.send() 委派子任务
                    │
                    └── 等待其他角色返回结果，汇总
```

---

## 3. 角色执行步骤

```
角色按 TaskPlan 执行当前步骤
    │
    ▼
步骤执行循环：
    │
    ├── 获取当前步骤（agent_registry.get_progress()）
    │
    ├── 判断步骤类型：
    │       │
    │       ├── 需要 LLM ──▶ 调用 llm_gateway（发布 llm.request）
    │       ├── 需要工具 ──▶ 调用 mcp_framework（发布 tool.call）
    │       ├── 需要技能 ──▶ 调用自己的技能（技能→工具→插件）
    │       ├── 需要记忆 ──▶ 调用 memory_service 读写
    │       └── 纯逻辑 ──▶ 角色自行处理
    │
    ├── 等待结果
    │
    ├── 更新步骤状态（agent_registry.update_step()）
    │       │
    │       ├── 成功 ──▶ completed → 进入下一步骤
    │       │
    │       └── 失败 ──▶ blocked → 中断处理流程
    │
    └── 检查是否还有步骤
            │
            ├── 有 ──▶ 继续循环
            │
            └── 无 ──▶ 任务完成（步骤 4）
```

---

## 4. 角色返回结果

```
所有步骤完成
    │
    ▼
汇总执行结果
    │
    ▼
调用 agent_registry.complete_agent()
    │
    ▼
发布 task.completed 事件
    │
    ▼
结果路由：
  ├─ suri 分配的任务 ──▶ 返回给 suri（suri 汇总后给用户）
  ├─ 直接用户请求 ──▶ 通过 role_manager 返回给 access → 用户
  ├─ 协作子任务 ──▶ role_comm 返回给父角色
  └─ 定时任务 ──▶ 记录日志，等待下次触发
    │
    ▼
触发 role_learner 异步学习
```

---

## 5. 角色自学与技能提升

```
task.completed 事件触发 role_learner
    │
    ▼
role_learner 异步分析（不阻塞主流程）
    │
    ▼
读取角色记忆（memory_service）
  ├─ experiences 表 — 最近执行记录
  ├─ messages — 通信记录
  └─ insights — 已有洞察
    │
    ▼
LLM 分析（llm_gateway）
  ├─ 生成结构化洞察
  │     ├─ success_pattern — 成功的模式
  │     ├─ improvement — 改进方向
  │     ├─ pitfall — 陷阱教训
  │     └─ preference — 偏好总结
  │
  └─ 检测技能形成模式（≥3 次重复的工具/流程组合）
    │
    ▼
保存洞察到 roles/{role_id}/memories/insights/
    │
    ▼
如有新技能模式 → 发布 role.skill_suggested 事件
    │
    ▼
suri 汇总 → 向用户呈现技能建议
    │
    ├── 用户确认 ──▶ 技能激活，写入 roles/{role_id}/skills/
    ├── 用户修改 ──▶ 完善后激活
    └── 用户拒绝 ──▶ 标记为 ignored
    │
    ▼
下次任务时，相关洞察自动注入角色上下文
```

### 角色主动申请升级

```
角色发现现有技能不足以完成任务
    │
    ├── 调用 role_learner 分析缺口
    │
    ├── 生成技能升级方案
    │   ├─ 技能名称
    │   ├─ 触发条件
    │   ├─ 需要的工具/权限
    │   └─ 预期效果
    │
    ├── 通过 upgrade_manager 提交方案
    │
    ▼
suri 评估 → 向用户呈现
    │
    ├── 确认 ──▶ 技能激活，角色可立即使用
    └── 拒绝 ──▶ 记录原因
```

---

## 6. 角色通信与协作

```
角色需要与其他角色通信
    │
    ▼
调用 role_comm.send()（点对点）或 role_comm.broadcast()（广播）
    │
    ▼
role_comm 校验通信权限
    │
    ├── 权限不足 ──▶ 拒绝，记录审计
    │
    └── 权限通过
        │
        ▼
    消息持久化到 SQLite
        │
        ▼
    发布 role.message_received 给接收角色
        │
        ▼
    接收角色处理消息
```

**跨角色协作场景**：

```
项目总监在 Telegram 群播报进度
    │
    ▼
用户 @对应角色 直接对话
    │
    ▼
access 捕获 @提及 → 路由给对应角色
    │
    ▼
角色回复通过 access 发回群中，带角色身份标识
```

---

## 7. 中断与异常处理

```
角色执行步骤时受阻
    │
    ▼
agent_registry.block_agent(reason)
    │
    ▼
发布 agent.blocked 事件
    │
    ▼
角色先尝试自己解决
    │
    ├── 能解决 ──▶ 继续执行（更新状态为 in_progress）
    │
    └── 无法解决
        │
        ▼
    interrupt_handler 介入
        │
        ▼
    分类受阻原因：
      ├─ missing_tool ──▶ 汇报 suri，请求新工具
      ├─ knowledge_gap ──▶ 搜索 / 向用户求助
      ├─ permission_denied ──▶ 申请权限
      ├─ dependency_failed ──▶ 尝试自动重试（最多3次）
      ├─ timeout ──▶ 尝试重试 / 调整超时
      └─ resource_exhausted ──▶ 等待 / 汇报 suri
        │
        ▼
    生成决策建议 → 向用户呈现选项
        │
        ├── 继续重试 ──▶ 重新调度
        ├── 升级方案 ──▶ suri 创建新 Agent 或角色自增技能
        └── 取消任务 ──▶ agent_registry.cancel_agent()
```

---

## 8. 角色自我管理

### 8.1 角色空闲检查

```
角色完成所有任务后
    │
    ▼
agent_registry 检测到无活跃 Agent
    │
    ▼
角色进入空闲状态
    │
    ├── 定期保存会话上下文快照
    ├── 优化内存占用（释放缓存）
    └── 等待下次被调度
```

### 8.2 角色版本管理

```
角色可以保留多个技能版本
    │
    ▼
skill_{name}_v1.0.json（原始版本）
    │
    ▼
skill_{name}_v1.1.json（优化版本，用户确认后生效）
    │
    ▼
upgrade_manager 管理版本回滚
```

### 8.3 角色自检

```
角色定期自检（可选，由 cron_service 触发）
    │
    ├── 检查 soul.md 是否一致
    ├── 检查技能是否过时（长期未使用）
    ├── 检查记忆空间是否整理（清理重复/低质量数据）
    └── 生成自检报告 → 汇报给 suri
```

---

## 9. 角色生命周期

```
角色创建（suri → role_manager）
    │
    ▼
角色就绪（等待任务分配）
    │
    ▼
角色执行任务（循环：分析→执行→学习）
    │
    ▼
角色升级（自学/自增技能）
    │
    ▼
角色删除（suri 或用户发起）
    │
    ▼
角色数据归档（_archived/{role_id}/）
```

### 角色状态的可见性

- suri 通过 agent_registry 可查看所有角色的状态
- 用户通过 access 可查看角色的活跃/空闲/受阻状态
- 角色之间通过 role_comm 可查看协作角色的任务进度
