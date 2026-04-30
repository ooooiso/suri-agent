# 开发日志

> 按时间线记录每次开发的内容、影响范围和待办事项。

---

## 2026-04-30

### 模型对接模块

**变更内容**:
- 新增 `suri-agent/model/` 目录：`__init__.py`、`model.md`、`manager.py`
- `ModelManager` 实现：模型配置增删改查、首次运行引导向导、OpenAI 兼容格式 / Anthropic API 调用
- `cli.py` 集成：初始化时检测首次运行并引导配置、`/model` 系列命令、用户输入后调用模型生成回复
- 配置保存在 `model_config.json`（根目录）和 `.env`

**影响范围**:
- `suri-agent/access/tui/cli.py` — 新增 model_manager 初始化、首次运行引导、/model 命令
- `suri-agent/model/` — 新增模块
- `suri-agent/suri-agent.md` — 目录结构、架构、启动顺序更新
- `suri-agent/process/process.md` — 首次运行初始化流程详细化

**待办**:
- [ ] 接入更多模型提供商（Google Gemini、Azure OpenAI 等）
- [ ] 模型调用失败时的自动降级机制
- [ ] 流式输出（streaming）支持

### AI 开发记忆库与文档审核角色

**变更内容**:
- 新增 `suri-agent/memory/ai-dev-memory/` 目录（原 `wiki/core-memory/` 已迁移删除）
  - `ai-dev-memory.md`：总览与读取建议
  - `architecture.md`：架构决策记录（ADR-001 ~ ADR-005）
  - `development-log.md`：开发日志（本文档）
  - `module-index.md`：模块索引
- 新增 `suri-agent/memory/memory.md`：记忆总目录说明
- 新增 `group/central/document-review/` 角色：Soul 文件、技能、参考目录
- 新增 `suri-agent/core/doc_sync.py`：文档同步服务
  - 检测代码变更（文件修改时间快照）
  - 调用大模型生成文档更新建议（JSON 格式）
  - 向用户汇报审核结果，请求确认
  - 用户确认后执行文档写入
- `cli.py` 集成 `/sync` 命令触发文档同步

**影响范围**:
- `suri-agent/memory/ai-dev-memory/` — 新增 AI 开发记忆库
- `suri-agent/memory/memory.md` — 新增记忆总目录说明
- `group/central/document-review/` — 新增角色
- `suri-agent/core/doc_sync.py` — 新增文档同步服务
- `suri-agent/core/core.md` — 新增 doc_sync.py 说明
- `suri-agent/access/tui/cli.py` — 新增 DocSyncService 集成、/sync 命令
- `group/group_function.md` — 新增 document-review 角色索引
- `suri-agent/suri-agent.md` — 新增核心记忆同步规则、document-review 角色、变更日志
- `suri-agent/rules/rules.md` — 新增核心记忆同步规则

**待办**:
- [ ] 实现 document-review 自动检测文件变更并触发审核流程（目前通过 /sync 手动触发）
- [ ] 大模型辅助生成 development-log 更新摘要时更精确地定位插入位置
- [ ] 考虑在退出 cli 时自动提示是否执行 /sync

### 架构重构：四大模块分离与 suri 角色核心地位

**变更内容**:
- `cli.py` 架构重构：
  - `initialize()` 新增 suri 角色 mandatory 检查：`group/central/suri/suri.md` 不存在则程序直接退出
  - `handle_user_input()` 不再直接调用模型，只负责"接收输入 → 交给 suri → 显示结果"
  - 新增 `suri_process()`：代表 suri 角色的完整处理流程
    - 调用模型分析需求（suri 的系统提示体现其中枢调度角色定位）
    - 判断直接回复 or 派发任务
    - 关键词启发式检测调度意图
  - 新增 `_attempt_dispatch()`：根据 suri 分析结果匹配部门，记录调度意图
- `suri-agent.md` 架构文档更新：
  - 新增"四大模块分离"表：主程序/角色/知识库/资源库
  - suri 角色标注 **mandatory**，其他角色标注可选
  - 明确调度链：用户 → suri → 部门总监 → 成员 → 结果回流 suri → 用户
  - 明确接入层（cli.py）只负责接收和显示，不处理业务逻辑

**架构原则**:
- 终端(cli)默认连接 suri 角色，suri 是唯一用户交互入口
- suri 是 central 部门负责人，也是所有部门的中枢
- 其他角色（suri-hr、suri-dev、document-review）可删除，不影响终端对话
- 任何角色无法解决的问题最终回流到 suri，由 suri 返回给用户决策
- 模型调用在 suri 处理流程中，不在 cli.py 接入层

### 根目录文件梳理：源代码 vs 运行时生成

**变更内容**:
- **`.env` 清空**：移除所有预设值（TELEGRAM_* 群组、OPENAI_KEY 等），程序运行前应为空
  - 创建 `.env.example` 作为配置模板，仅含注释说明和空变量名
- **`config.yaml` 重构**：移除已废弃配置项
  - 移除 `plugins` 列表（已代码化）、`gateway`（未实现）、`memory.database_path`（已改为 role.db）
  - 保留：`platform`（name/version/mode/debug）
- **运行时文件迁移**：
  - 删除根目录 `suri-agent.log`、`suri-agent.pid`
  - `daemon.py` PID 文件改为 `resources/.suri.pid`
  - `daemon.py` 日志改为 `resources/logs/suri-daemon.log`
- **`state_schema.md` 更新**：从 `state.db` 全局数据库说明 → 角色级独立 `role.db` 说明
- **根目录文档同步**：更新 `suri-agent/suri-agent.md` 目录结构说明，明确标注哪些是源代码、哪些是运行时生成

**设计原则**：
- 程序运行前，根目录只应存在源代码、配置模板和空目录
- 运行时数据（.env、config.yaml、model_config.json、日志、PID）由程序自动写入
- Token/密钥不在源代码中预设，首次运行引导或角色连接后动态写入角色记忆或 .env

### 文档同步自动化规则

**变更内容**:
- 新增 `suri-agent/rules/doc_sync_rule.py` — `DocSyncRule` 文档同步规则引擎：
  - 建立代码目录 ↔ 同名 .md 文件的映射关系
  - `scan()` 全面扫描 suri-agent/、group/、wiki/，检测"缺失"和"过时"文档
  - `quick_check()` 单个文件变更的即时检测
  - `generate_sync_plan()` 生成同步计划报告（供大模型/document-review 使用）
  - `is_compliant()` / `get_unsynced_dirs()` 合规性检查
  - 违规状态持久化到 `.doc_sync_rule_state.json`
- 新增 `suri-agent/hooks/doc_watcher.py` — `DocWatcher` 文件监控钩子：
  - 后台线程监控文件系统变更（2秒轮询）
  - 维护待同步队列，去重、延迟检测
  - 启动/停止可控
- `cli.py` 集成：
  - 初始化时加载 DocSyncRule 和 DocWatcher
  - `/sync` 命令升级为：先执行 DocSyncRule 扫描违规项 → 打印检测结果 → 再执行传统 doc_sync
  - 退出时优雅停止 DocWatcher
- 规则总览更新：新增"文档同步自动化规则"定义

**设计目标**:
实现"代码变更即文档更新"的自动化闭环，未来由角色（document-review）调用大模型自动完成文档更新，无需人工记忆和手动执行。

**影响范围**:
- `suri-agent/rules/doc_sync_rule.py` — **新增**
- `suri-agent/hooks/doc_watcher.py` — **新增**
- `suri-agent/rules/rules.md` — 新增规则定义
- `suri-agent/hooks/hooks.md` — 更新说明
- `suri-agent/access/tui/cli.py` — 集成 DocSyncRule、DocWatcher、升级 /sync 命令
- `suri-agent/suri-agent.md` — 规则表、扩展机制、变更日志更新

### 日志服务

**变更内容**:
- 新增 `suri-agent/infrastructure/logger.py` — `LoggerService`：
  - 日志目录：`resources/logs/`，按天轮转 `suri-YYYY-MM-DD.log`
  - 全中文输出：级别（信息/警告/错误/调试）、模块、消息
  - 业务事件快捷方法：log_startup、log_shutdown、log_user_input、log_task_created/dispatched、log_model_call/error、log_role_message、log_command、log_config、log_doc_sync
- `cli.py` 集成日志：
  - 初始化时创建 LoggerService，最先初始化确保全程可记录
  - 用户输入、命令执行、模型调用、代码变更、服务重载均记录日志
  - 新增 `/logs` 命令查看今日日志路径和最近 10 条记录
- `core/task_dispatcher.py` 集成日志：
  - `TaskService` 接收 logger 参数
  - `receive_task()` 记录任务创建和调度分发日志

**影响范围**:
- `suri-agent/infrastructure/logger.py` — **新增**
- `suri-agent/access/tui/cli.py` — 集成日志、新增 /logs 命令
- `suri-agent/core/task_dispatcher.py` — 集成日志
- `resources/logs/logs.md` — 新增日志目录说明
- `suri-agent/suri-agent.md` — 基础设施层加入 logger.py

### 文档同步规则全面梳理

**变更内容**:
- 重写 `suri-agent/model/model.md`：补充完整功能说明、支持的提供商列表、CLI 集成细节、事件记录
- 补充 `suri-agent/` 下所有缺失的同名 `.md` 文档：
  - `access/feishu/feishu.md`
  - `access/telegram/telegram.md`
  - `access/tui/tui.md`
  - `mcp/services/services.md`
  - `mcp/services/code_execution/code_execution.md`
  - `mcp/services/filesystem/filesystem.md`
  - `mcp/services/web_search/web_search.md`
- 更新 `suri-agent/suri-agent.md` 大框架：
  - 目录结构总览加入 `memory/`、`doc_sync.py`、`document-review/`
  - 分层架构表去重、加入记忆中枢、规则数更新为 8 条
  - 模块职责加入 `doc_sync.py` 和 `memory/` 详细描述
- 更新 `suri-agent/rules/rules.md`：规则数从 7 条更新为 8 条（含核心记忆同步规则）

**新增规则**:
- **"更改即更新"**：`suri-agent/` 下任何目录发生代码变更时，必须同步更新该目录的同名 `.md` 文件。文档是代码的权威描述，不可滞后。

### 代码变更检测与会话刷新机制

**变更内容**:
- `cli.py` 新增代码变更检测机制：
  - `_compute_code_snapshot()` — 计算 `suri-agent/` 下所有 `.py` 文件修改时间哈希
  - `_check_code_change()` — 对比当前快照与启动时快照
  - 主循环每次输入前自动检测，代码变更后提示用户输入 `/reload`
- 新增 `/reload` 命令：重新调用 `initialize()` 加载所有服务
  - ConfigService、MemoryService、SecurityService 等全部重新初始化
  - 角色记忆（`role.db`）不受影响 — SQLite 文件级持久化，重新初始化只是重建连接
  - `_code_changed_notified` 标记避免重复提示

**设计原因**:
每次核心主代码调整后，运行中的 cli 进程不会自动感知变更。`/reload` 机制让角色在保留记忆的前提下进入新代码会话，无需重启整个进程。

**影响范围**:
- `suri-agent/access/tui/cli.py` — 新增代码变更检测、/reload 命令

### 清理遗留角色目录

**变更内容**:
- 删除 `group/suri-hr/` 遗留目录（角色精简/迁移时未清理的旧目录）
- 将 `group/suri-hr/memories/role.db` 迁移至 `group/central/suri-hr/memories/role.db`
- `group/central/suri-hr/` 下新建 `memories/` 目录

**原因**:
当前角色规范要求所有角色必须存放在 `group/<department>/<role_id>/` 下，`group/suri-hr/` 直接位于 group/ 根目录，不符合规范，是早期目录结构调整时的遗留。

**影响范围**:
- `group/suri-hr/` — **已删除**
- `group/central/suri-hr/memories/` — **新增**，继承原 role.db 数据
