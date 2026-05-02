# 角色工作流

> 描述单个角色在 suri-agent 中的标准工作流程。所有流程由角色通过调用插件能力完成，和程序无关。

---

## 1. 角色接收任务

```
角色通过 EventBus 订阅相关事件
    │
    ├── user.input ──▶ 直接用户请求（通常路由给项目总监）
    ├── role_comm.message_received ──▶ 其他角色的消息
    ├── task_scheduler.task.started ──▶ 被分配的任务
    └── cron_service.cron.* ──▶ 定时触发任务
    │
    ▼
角色读取上下文（memory_service）
    │
    ├─ 角色 Soul 文件（soul.md）
    ├─ 历史记忆（memories/）
    ├─ 学习洞察（insights/）
    └─ 当前任务信息
    │
    ▼
角色分析需求
```

## 2. 角色分析需求

```
角色分析接收到的任务
    │
    ├── 判断任务类型（code / review / statistics / ...）
    │
    ├── 判断是否需要分解
    │       │
    │       ├── 简单任务 ──▶ 直接执行（步骤 3）
    │       │
    │       └── 复杂任务 ──▶ 调用 task_planner.plan()
    │               │
    │               ▼
    │           获取 TaskPlan（步骤序列 + 依赖关系）
    │               │
    │               ▼
    │           调用 agent_registry.create_agent()
    │               │
    │               ▼
    │           进入步骤执行循环（步骤 3）
    │
    └── 判断是否需要其他角色协作
            │
            ├── 不需要 ──▶ 自行执行
            │
            └── 需要 ──▶ 调用 role_comm.send() 委派子任务
                    │
                    └── 等待其他角色返回结果
```

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
    │       │
    │       ├── 需要工具 ──▶ 调用 mcp_framework（发布 tool.call）
    │       │
    │       ├── 需要记忆 ──▶ 调用 memory_service 读写
    │       │
    │       └── 纯逻辑 ──▶ 角色自行处理
    │
    ├── 等待结果（asyncio.Event / 事件回调）
    │
    ├── 更新步骤状态（agent_registry.update_step()）
    │       │
    │       ├── 成功 ──▶ completed → 进入下一步骤
    │       │
    │       └── 失败 ──▶ blocked → 触发 interrupt_handler
    │
    └── 检查是否还有步骤
            │
            ├── 有 ──▶ 继续循环
            │
            └── 无 ──▶ 任务完成（步骤 4）
```

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
  ├─ 项目群内任务 ──▶ 返回给项目总监（由项目总监汇总后播报给用户）
  ├─ 直接用户请求 ──▶ access 返回给用户
  ├─ 子任务 ──▶ role_comm 返回给父角色
  └─ 定时任务 ──▶ 记录日志，等待下次触发
    │
    ▼
触发 role_learner 异步学习（task.completed 事件订阅）
```

## 5. 角色自学习流程

```
task.completed / task.failed 事件
    │
    ▼
role_learner 异步触发（不阻塞主流程）
    │
    ▼
读取角色记忆（memory_service）
  ├─ experiences 表
  ├─ messages
  └─ insights
    │
    ▼
LLM 分析（llm_gateway）
  ├─ 生成结构化洞察
  │     ├─ success_pattern
  │     ├─ improvement
  │     ├─ pitfall
  │     └─ preference
  │
  └─ 检测技能形成模式（≥3 次重复）
    │
    ▼
保存洞察到 roles/{role_id}/memories/insights/
    │
    ▼
上报技能建议（role.skill_suggested → role_manager）
    │
    ▼
下次任务时，相关洞察自动注入角色上下文
```

## 6. 角色通信流程

```
角色需要与其他角色通信
    │
    ▼
调用 role_comm.send() 或 role_comm.broadcast()
    │
    ▼
role_comm 校验通信权限
    │
    ├── 权限不足 ──▶ 拒绝，发布 role.message_rejected
    │
    └── 权限通过 ──▶ 继续
    │
    ▼
消息持久化到 SQLite
    │
    ▼
发布 role.message_received 给接收者
    │
    ▼
接收者角色处理消息
```

**项目群内通信（外部投影）**：

```
项目总监在群内播报进度
    │
    ▼
access/telegram 将播报内容发送到项目 Telegram 群
    │
    ▼
用户和其他角色在群中可见
    │
    ▼
用户 @实现角色 直接对话
    │
    ▼
access/telegram 捕获 @提及，路由给对应角色
    │
    ▼
角色回复通过 access/telegram 发回群中，带角色身份标识
```

## 7. 角色中断处理流程

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
项目总监先尝试协调解决
    │
    ├── 能解决 ──▶ 重新调度或调整规划
    │
    └── 无法解决
        │
        ▼
    interrupt_handler 介入
        │
        ▼
    分类受阻原因：
      ├─ missing_tool ──▶ 汇报 suri，请求开发
      ├─ knowledge_gap ──▶ 搜索 / 升级给用户决策
      ├─ permission_denied ──▶ 申请权限
      ├─ dependency_failed ──▶ 重试 / 升级
      ├─ timeout ──▶ 重试 / 调整超时
      └─ resource_exhausted ──▶ 等待 / 汇报 suri
        │
        ▼
    生成决策建议
        │
        ▼
    项目总监在群中向用户呈现选项
```

## 8. 角色创建新插件流程

```
角色发现现有工具/插件不满足需求
    │
    ▼
生成新插件代码（Python 模块 + manifest.json）
    │
    ▼
向 security_service 申请文件变更审批
    │
    ▼
审批通过
    │
    ▼
存入 ~/.suri/runtime/plugins/{plugin_name}/
    │
    ▼
向 suri_core 申请注册
    │
    ▼
suri_core AST 安全扫描
    │
    ▼
PluginManager 动态加载
    │
    ▼
新插件通过 event_bus 与其他插件协同
```

## 9. 角色创建流程（终端简化版）

```
用户终端输入：
/create_role 昵称 "一句话定义"
    │
    ▼
access 转换为 user.command 事件
    │
    ▼
suri 接收，调用 llm_gateway 丰富 Soul：
  ├─ 根据昵称和定义生成完整职责描述
  ├─ 生成能力清单（capabilities）
  ├─ 生成关键词（keywords）
  ├─ 生成工作方法论
  └─ 生成示例任务
    │
    ▼
suri 向用户呈现完整 Soul 草案：
"角色草案：
━━━━━━━━━━━━━━━━
昵称：前端开发
定义：负责网页前端开发，使用 React/Vue

Soul 内容：
你是前端开发专家，专注于...
能力：React、Vue、CSS、响应式设计...
━━━━━━━━━━━━━━━━
是否确认创建？[确认] [修改] [取消]"
    │
    ▼
用户确认
    │
    ▼
role_manager.create_role(role_id, soul_content)
  ├─ 创建目录结构
  ├─ 写入 soul.md
  ├─ 初始化 memories/
  └─ 更新 registry.md
    │
    ▼
发布 role.created 事件
    │
    ▼
角色就绪，可被项目总监调用
```

**创建所需信息**：

| 输入 | 用户提供 | suri 自动生成 |
|------|---------|--------------|
| 昵称 | ✅ 必填 | — |
| 一句话定义 | ✅ 必填 | — |
| 完整职责描述 | — | ✅ LLM 生成 |
| 能力清单 | — | ✅ LLM 生成 |
| 关键词 | — | ✅ LLM 生成 |
| 工作方法论 | — | ✅ LLM 生成 |
| Soul 文件 | — | ✅ 基于以上组装 |
