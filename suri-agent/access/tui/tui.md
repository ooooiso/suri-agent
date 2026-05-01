# tui/

> 关联代码: suri-agent/access/tui/cli.py, suri-agent/access/tui/server.py, suri-agent/access/tui/rpc_methods.py

终端用户界面（Terminal User Interface）：命令行交互入口。

## 功能

- `cli.py` — 终端命令行客户端，直接调用 suri-agent 核心服务
- `server.py` — JSON-RPC 服务端，供后台 daemon 调用
- `rpc_methods.py` — RPC 方法定义
- `middleware.py` — 请求中间件

## 事件记录

- 新增模型管理集成（model_manager 初始化、首次运行引导）
- 新增 /model 系列命令（add/set/del/list）
- 新增 /sync 文档同步命令
- `/reload` 服务重载命令 — **进程级热重载**：使用 `os.execv()` 重启当前进程，加载全新代码，无需手动退出再启动
- 代码变更检测机制（`_compute_code_snapshot` / `_check_code_change`）— 检测到代码修改后提示用户执行 `/reload`
- **角色上下文注入模型信息**：`_execute_dispatch()` 调用 `ContextService.build_context()` 构建完整角色上下文，包含当前使用的模型名称/ID/提供商
- 未配置模型时阻止普通输入，引导用户配置
- **底层调用升级**：模型调用支持智能路由，任务调度自动按内容选模（用户无感知）
- **多角色并行调度**：`_detect_dispatch_target()` 返回 `List[str]`（原 `Optional[str]`），支持复杂需求调度至多个角色依次执行，结果汇总后回流给用户
- **角色上下文注入**：`_execute_dispatch()` 构建角色上下文时注入 `current_task`，支持任务级多轮记忆
- **多用户并发隔离**：`suri_process()` 支持 `user_id` 参数，通过 `_get_or_create_session()` 为每个用户维护独立 session；`build_context()` 按 `session_id` 过滤历史记忆，避免用户间上下文混淆；SQLite 启用 WAL 模式支持读写并发
- **代码变更自动刷新**：任务完成后 `suri_process()` 自动调用 `_check_code_change()` 检测核心代码是否变更；若变更则自动执行 `_perform_reload()`（os.execv 进程热重载），无需用户手动输入 /reload
- **手动刷新命令**：`/reload` 调用 `_perform_reload()` 立即热重载，清理资源后通过 os.execv 重启进程，角色记忆等 SQLite 持久化数据保留
- **统一输出框架集成**：`SuriTerminal` 初始化 `OutputRouter`，所有角色输出通过 `OutputRouter.deliver_text()` / `deliver_code()` / `deliver_alert()` 统一路由；终端输出保留角色彩色标识（suri=青/suri_dev=绿/suri_hr=黄/suri_review=紫/suri_stats=蓝），代码自动保存到 `group/central/suri_dev/output/`（suri_dev）或 `group/central/suri_review/reports/`（suri_review），告警（urgent）自动触发 Telegram 通道预留
- **V3.0 任务状态管理集成**：`SuriTerminal` 初始化 `TaskStateService`、`AgentRegistry`、`StateCardRenderer`、`DepartmentRegistry`、`MessageBus`、`InterruptHandler`
- **V3.0 任务处理流程**：`suri_process()` 自动执行：创建 TaskPlan → 创建 Agent → 调度执行 → 结果回流 → 追加状态卡片 → 保存经验
- **V3.0 Agent 上下文隔离**：`_execute_dispatch()` 通过 Agent 独立上下文执行，messages 列表与 suri 主上下文隔离
- **V3.0 多任务并行**：中途新需求自动创建并行 Agent，状态卡片汇总展示所有活跃任务进度
- **V3.0 状态卡片自动注入**：每次输出后自动追加 `state_card.render_terminal()`，显示所有活跃 Agent 的进度看板
- **V3.0 消息总线**：角色执行完成后通过 `message_bus.broadcast_status()` 广播状态更新，suri 订阅汇总
