# 模块索引

> 记录 suri 平台所有目录/文件的功能、接口、所有权和最新变更。

---

## suri-agent/ （主程序 — suri-dev 维护）

| 路径 | 功能 | 关键接口 | 最新变更 |
|------|------|---------|---------|
| `access/tui/cli.py` | 终端命令行客户端 | `SuriTerminal.initialize()`, `handle_user_input()`, `handle_command()` | 新增 model_manager 集成、首次运行引导、/model 命令、/sync 命令 |
| `access/tui/server.py` | JSON-RPC 服务端 | — | 无 |
| `core/task_dispatcher.py` | 任务调度器 | `TaskService.receive_task()` | 无 |
| `core/model_router.py` | 模型路由（内部） | `ModelService` | 无 |
| `core/context.py` | 上下文管理 | `ContextService` | 无 |
| `core/approval.py` | 审批引擎 | `ApprovalService` | 无 |
| `core/tool_executor.py` | 工具执行器 | `ToolService` | 无 |
| `core/doc_sync.py` | 文档同步服务 | `DocSyncService.run_sync()` | **新增** |
| `infrastructure/config.py` | 配置加载器 | `ConfigService.load_all()` | 移除 manifest/ 扫描 |
| `infrastructure/memory.py` | 记忆服务（角色级独立存储） | `RoleMemoryManager` | 角色独立 db |
| `infrastructure/security.py` | 安全服务 | `SecurityService.check_permission()` | 代码化规则 |
| `infrastructure/filesystem.py` | 文件服务 | `FileService` | 无 |
| `model/manager.py` | 模型配置与调用管理 | `ModelManager.setup_wizard()`, `chat()` | **新增** |
| `memory/ai-dev-memory/` | AI 开发记忆库 | 开发上下文权威源 | **新增** |
| `role/coordinator.py` | 角色协同调度器 | `dispatch_task()` | 无 |
| `role/messenger.py` | 角色通信管理器 | `send_message()` | 无 |
| `role/builder.py` | 角色搭建规则执行器 | `create_role()` | 无 |
| `rules/` | 业务规则代码 | `RuleEngine` | 代码化 |
| `process/` | 平台流程代码 | `ProcessEngine` | 代码化 |

## group/ （角色目录 — 各角色自我管理）

| 路径 | 角色 | 职能 | 最新变更 |
|------|------|------|---------|
| `central/suri/` | suri | 中枢调度 | 无 |
| `central/suri-hr/` | suri-hr | 人力资源 | 无 |
| `central/suri-dev/` | suri-dev | 程序维护 | 无 |
| `central/document-review/` | document-review | 文档审核 | **新增** |

## wiki/ （知识库 — 用户面向，可编辑）

| 路径 | 功能 | 最新变更 |
|------|------|---------|
| （已清空） | 原 core-memory/ 已迁移至 suri-agent/memory/ai-dev-memory/ | **迁移** |
