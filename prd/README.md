# Suri Agent PRD 文档索引

> 本文档是 `suri-agent/prd/` 目录下所有 PRD 文档的统一索引和导航入口。

---

## 文档总览

| 类别 | 数量 | 说明 |
|------|------|------|
| 框架文档 | 13 | 架构、目录、流程、规则、部署、开发规范、学习机制、数据库 schema、事件注册表、安全规范 |
| 插件 PRD | 21 | 21 个插件的详细设计 |
| **总计** | **34** | |

---

## 框架文档

| 文件 | 说明 | 状态 |
|------|------|------|
| [`framework.md`](framework.md) | 框架核心说明：架构、存储、启动流程、插件生命周期、安全沙箱 | ✅ 完整 |
| [`file_directory.md`](file_directory.md) | 项目完整目录结构规范 | ✅ 完整 |
| [`process.md`](process.md) | 系统工作流程定义：标准/多角色/异常/决策/能力缺口/自优化 | ✅ 完整 |
| [`program_flow.md`](program_flow.md) | 程序工作流：系统启动/事件循环/插件加载/关闭 | ✅ 完整 |
| [`role_workflow.md`](role_workflow.md) | 角色工作流：接收任务/分析/执行/返回/学习/通信 | ✅ 完整 |
| [`work_flow.md`](work_flow.md) | 项目工作流：创建/单角色/多角色/进度/异常/归档 | ✅ 完整 |
| [`rules.md`](rules.md) | 系统运行规则：通信/安全/学习/调度/中断/Agent | ✅ 完整 |
| [`deployment.md`](deployment.md) | 部署安装指南：系统要求、安装、首次运行、升级、故障排查 | ✅ 完整 |
| [`plugin_development.md`](plugin_development.md) | 插件开发规范：目录结构、manifest、接口、事件模式、自修改、共享模块 | ✅ 完整 |
| [`learning_flow.md`](learning_flow.md) | 角色与插件学习机制：经验提取、技能进化、全局分析、自修改闭环 | ✅ 完整 |
| [`database_schema.md`](database_schema.md) | 统一数据库 Schema：所有 SQLite 表的 CREATE TABLE + 索引 + 归属 | ✅ 完整 |
| [`event_registry.md`](event_registry.md) | 事件注册表：40+ 事件的发布者/订阅者矩阵 + 路由规则 + 统一错误基类 | ✅ 完整 |
| [`security_spec.md`](security_spec.md) | 安全规范：AST 扫描器、文件沙箱、资源限制、审批令牌状态机 | ✅ 完整 |
| [`code_tool.md`](plugins/code_tool.md) | 代码工具：安全文件读写、代码搜索、测试执行 | ✅ 完整 |

---

## 插件 PRD（20 个）

> 所有插件 PRD 位于 [`plugins/`](plugins/) 目录。

### 插件总览

```
20 个插件分 5 层：
├─ 内核层（1）    suri_core
├─ 基础服务层（3） config_service / log_service / security_service
├─ 执行层（5）    task_scheduler / task_planner / agent_registry / role_comm / interrupt_handler
├─ 能力层（6）    llm_gateway / memory_service / role_manager / role_learner / mcp_framework / upgrade_manager
├─ 接入层（1）    access
└─ 扩展层（4）    cron_service / hooks_service / test_framework / doc_sync
```

### 按层级索引

#### 内核层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| **suri_core** | [`plugins/suri_core.md`](plugins/suri_core.md) | **内核插件**。EventBus（含分发）+ PluginManager。启动时自举注册 | 核心 |

#### 基础服务层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| config_service | [`plugins/config_service.md`](plugins/config_service.md) | 统一配置中心 | 核心 |
| log_service | [`plugins/log_service.md`](plugins/log_service.md) | 分级日志、分类归档 | 核心 |
| security_service | [`plugins/security_service.md`](plugins/security_service.md) | 权限校验、审批流程 | 核心 |

#### 执行层（新增）

| 插件 | 文件 | 职责 | 优先级 |
|------|------|------|--------|
| **task_scheduler** | [`plugins/task_scheduler.md`](plugins/task_scheduler.md) | 任务优先级队列、并发控制、超时重试、LLM 响应等待 | **P0** |
| **task_planner** | [`plugins/task_planner.md`](plugins/task_planner.md) | 任务分解、DAG 依赖管理、预设模板、LLM 辅助规划 | **P0** |
| **agent_registry** | [`plugins/agent_registry.md`](plugins/agent_registry.md) | Agent 生命周期、子 Agent、状态跟踪、进度查询、父子关系 | **P0** |
| **role_comm** | [`plugins/role_comm.md`](plugins/role_comm.md) | 角色间点对点/广播消息、权限规则、持久化队列、留存策略 | **P0** |
| **interrupt_handler** | [`plugins/interrupt_handler.md`](plugins/interrupt_handler.md) | 受阻原因分类、用户建议生成、升级通道 | **P1** |

#### 能力层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| llm_gateway | [`plugins/llm_gateway.md`](plugins/llm_gateway.md) | 大模型统一网关 | 必备 |
| memory_service | [`plugins/memory_service.md`](plugins/memory_service.md) | 角色级 SQLite 记忆存储 | 必备 |
| role_manager | [`plugins/role_manager.md`](plugins/role_manager.md) | 角色生命周期、Soul 管理 | 必备 |
| role_learner | [`plugins/role_learner.md`](plugins/role_learner.md) | 角色自学习 + ProgramLearner 全局分析 | 成长 |
| mcp_framework | [`plugins/mcp_framework.md`](plugins/mcp_framework.md) | MCP 协议 + 工具注册中心 + 内置服务 | 必备 |
| upgrade_manager | [`plugins/upgrade_manager.md`](plugins/upgrade_manager.md) | 升级报告状态机、闭环检查、Finding/UpgradeReport 模型 | **P1** |

#### 接入层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| access | [`plugins/access.md`](plugins/access.md) | 统一接入（CLI/Web/Telegram/Lark/API） | 默认启用 |

#### 扩展层

| 插件 | 文件 | 职责 | 状态 |
|------|------|------|------|
| cron_service | [`plugins/cron_service.md`](plugins/cron_service.md) | 定时触发事件（只触发，不执行） | 运维 |
| hooks_service | [`plugins/hooks_service.md`](plugins/hooks_service.md) | 事件钩子、拦截扩展 | 扩展 |
| test_framework | [`plugins/test_framework.md`](plugins/test_framework.md) | 自动化测试框架 | 质量 |
| doc_sync | [`plugins/doc_sync.md`](plugins/doc_sync.md) | 文件变更监控、LLM 生成文档更新建议、用户确认写入 | **P2** |

---

---

## 快速导航

### 按开发阶段

| 阶段 | 参考文档 |
|------|---------|
| 了解架构 | [`framework.md`](framework.md) → [`plugins/suri_core.md`](plugins/suri_core.md) |
| 了解流程 | [`process.md`](process.md) → [`rules.md`](rules.md) |
| 开发插件 | [`plugins/README.md`](plugins/README.md) → 具体插件 PRD |
| 开发执行层 | [`plugins/task_scheduler.md`](plugins/task_scheduler.md) → [`plugins/task_planner.md`](plugins/task_planner.md) → [`plugins/agent_registry.md`](plugins/agent_registry.md) |
| 开发通信层 | [`plugins/role_comm.md`](plugins/role_comm.md) |
| 元学习闭环 | [`plugins/role_learner.md`](plugins/role_learner.md) → [`plugins/upgrade_manager.md`](plugins/upgrade_manager.md) |

### 关键设计原则

1. **一切功能基于插件调用，无硬编码耦合**
2. **一切任务基于角色协同，和程序无关**
3. **所有插件（包括 suri_core）概念统一，无特殊分类**
4. **无实体可私自修改代码，所有变更须经用户确认**

---

## 文档维护

- 新增插件 PRD 必须同步更新本索引和 [`plugins/README.md`](plugins/README.md)
- 分析文档（`ai_out/`）为工作草稿，用户审阅后可归档
- `问题集-关于不修改删除.md` 为早期草稿，保留不修改
