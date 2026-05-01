# Suri 开发任务看板

> 按 development-plan 文档排序拆分
>
> **原始规格文档已归档至 `归档/` 目录：**
> - `归档/1.SELF_LEARNING_SPEC.md` — 自学习模块（✅ 已完成）
> - `归档/2.TELEGRAM_INTEGRATION_SPEC.md` — Telegram 集成（✅ 已完成）
> - `归档/3.细节处理.md` — 细节处理（✅ 已完成）
> - `归档/基础设施搭建完成.md` — 前置基础设施（✅ 已完成）
>
> 本文件保留为活跃索引和后续任务追踪。

---

## 📋 前置基础设施（已归档）

| 任务 | 状态 | 归档时间 |
|------|------|---------|
| 项目基础框架搭建（main.py 初始化流程、消息队列、终端输入） | ✅ 已完成 | 2026-05-01 |
| ConfigService（配置加载、索引、查询） | ✅ 已完成 | 2026-05-01 |
| MemoryService（角色级 SQLite、消息/任务/会话管理） | ✅ 已完成 | 2026-05-01 |
| LoggerService（分类日志、业务事件快捷方法） | ✅ 已完成 | 2026-05-01 |
| SecurityService（文件权限、安全校验） | ✅ 已完成 | 2026-05-01 |
| FileService（文件操作） | ✅ 已完成 | 2026-05-01 |
| ModelManager / ModelService（模型路由、智能选择、降级） | ✅ 已完成 | 2026-05-01 |
| ContextService（角色 Soul、规则、文件权限、历史记忆组装） | ✅ 已完成 | 2026-05-01 |
| TaskService（任务状态机、三级部门匹配、调度分发） | ✅ 已完成 | 2026-05-01 |
| CommService（通信骨架、StandardMessage、Telegram 占位） | ✅ 已完成 | 2026-05-01 |
| ApprovalService（审批流程） | ✅ 已完成 | 2026-05-01 |
| ToolService（工具执行） | ✅ 已完成 | 2026-05-01 |
| RoleMessenger（角色间消息路由、格式校验、权限检查） | ✅ 已完成 | 2026-05-01 |
| CommunicationRule（通信协议、通道、跨部门权限） | ✅ 已完成 | 2026-05-01 |
| MCPRegistry（MCP 预留） | ✅ 已完成 | 2026-05-01 |
| 基础测试（model_manager、task_dispatcher） | ✅ 已完成 | 2026-05-01 |

---

## 📘 文档 1：自学习模块（SELF_LEARNING_SPEC）— ✅ 已完成

### 1.1 新增文件

| 任务 | 文件 | 状态 |
|------|------|------|
| 自学习模块入口 | `suri-agent/learning/__init__.py` | ✅ 已完成 |
| 学习器基类 | `suri-agent/learning/base.py` | ✅ 已完成 |
| 反馈收集器 | `suri-agent/learning/feedback_collector.py` | ✅ 已完成 |
| 经验提取器（含 Prompt 模板、解析器） | `suri-agent/learning/experience_extractor.py` | ✅ 已完成 |
| 角色自学习引擎 | `suri-agent/learning/role_learner.py` | ✅ 已完成 |
| 主程序自学习引擎 | `suri-agent/learning/platform_learner.py` | ✅ 已完成 |
| 自学习模块文档 | `suri-agent/learning/learning.md` | ✅ 已完成 |

### 1.2 现有文件修改

| 任务 | 文件 | 修改点 | 状态 |
|------|------|--------|------|
| MemoryService 扩展 | `suri-agent/infrastructure/memory.py` | 新增 save_role_insight、list_role_insights、get_recent_insights_for_context、update_insight_trigger 等方法 | ✅ 已完成 |
| ContextService 扩展 | `suri-agent/core/context.py` | build_context 中注入学习经验段（_get_learning_insights） | ✅ 已完成 |
| TaskService 扩展 | `suri-agent/core/task_dispatcher.py` | dispatch 后异步触发学习（_learner.learn_from_task） | ✅ 已完成 |
| LoggerService 扩展 | `suri-agent/infrastructure/logger.py` | 新增 log_learning、log_learning_error | ✅ 已完成 |
| main.py 扩展 | `suri-agent/main.py` | 初始化 RoleLearner，传入 TaskService | ✅ 已完成 |

---

## 📗 文档 2：Telegram 集成（TELEGRAM_INTEGRATION_SPEC）— ✅ 已完成

### 2.1 新增/重构文件

| 任务 | 文件 | 状态 |
|------|------|------|
| Bot 真连接重构 | `suri-agent/access/telegram/bot.py` | ✅ 已完成 |
| Bot 命令处理器 | `suri-agent/access/telegram/commands.py` | ✅ 已完成 |
| 投影服务 | `suri-agent/access/projection.py` | ✅ 已完成 |

### 2.2 现有文件修改

| 任务 | 文件 | 修改点 | 状态 |
|------|------|--------|------|
| Messenger 投影钩子 | `suri-agent/role/messenger.py` | send() 末尾加投影触发 + _get_project_targets | ✅ 已完成 |
| 通信规则扩展 | `suri-agent/rules/communication.py` | 新增 project_to 字段，跨部门不抄送 suri | ✅ 已完成 |
| main.py 扩展 | `suri-agent/main.py` | 初始化 ProjectionService | ✅ 已完成 |
| Telegram 配置文档 | `wiki/communication/telegram.md` | 更新配置格式、命令列表、投影规则 | ✅ 已完成 |

---

## 📙 文档 3：细节处理 — ✅ 已完成

| # | 任务 | 涉及文件 | 状态 |
|---|------|---------|------|
| 1 | 终端模式角色自治：所有操作由角色完成 | `group/central/suri/suri.md`（明确定位） | ✅ 已完成 |
| 2 | 终端连接失败抛出明确错误 + 终端命令系统 | `suri-agent/main.py`（_fallback_reply 增强 + /model /status /test /reload /logs /help） | ✅ 已完成 |
| 3 | Token 消耗统计与记录 | `suri-agent/model/manager.py`, `suri-agent/core/model_router.py`, `suri-agent/infrastructure/logger.py` | ✅ 已完成 |
| 4 | 整理需求复盘，完善代码和文档说明 | `development-plan/TASK_BOARD.md`, `development-plan/归档/` | ✅ 已完成 |
| 5 | 工具集清单 + MCP 链接 | `suri-agent/tools/TOOL_REGISTRY.md` | ✅ 已完成 |
| 6 | 核心 suri 定位为任务分析+调度 | `group/central/suri/suri.md` | ✅ 已完成 |
| 7 | HR 核心定义（行政+人力） | `group/central/suri-hr/suri-hr.md` | ✅ 已完成 |
| 8 | 文件审核工作流（document-review 角色） | `group/central/document-review/document-review.md` | ✅ 已完成 |
| 9 | 连接测试（终端 + Telegram）+ 模型诊断脚本 | `scripts/test_connections.py`、`scripts/diagnose_model.py` | ✅ 已完成 |

---

---

## 🔧 2026-05-01 修复记录

| # | 问题 | 涉及文件 | 修复内容 | 状态 |
|---|------|---------|---------|------|
| 1 | `/model` 在 cli.py 中仍显示旧逻辑 | `suri-agent/access/tui/cli.py` | `/model` 无参数时启动 wizard；`/model add` 改为品牌选择+API Key+自动测试 fallback | ✅ 已完成 |
| 2 | 模型调用失败后无引导 | `suri-agent/access/tui/cli.py`, `suri-agent/main.py` | 失败时自动提示"是否立即配置新模型"，输入 Y 直接启动 wizard | ✅ 已完成 |
| 3 | suri 把闲聊/元信息问题错误调度 | `suri-agent/access/tui/cli.py` | 系统提示词注入当前模型信息，明确规则：关于自身状态的问题直接回答，不调度 | ✅ 已完成 |
| 4 | 主循环/suri_process 缺少异常防护 | `suri-agent/access/tui/cli.py` | 添加 try-catch，防止任何未预料异常导致程序崩溃 | ✅ 已完成 |
| 5 | 终端输出过于冗长 | `suri-agent/access/tui/cli.py`, `suri-agent/infrastructure/logger.py`, `suri-agent/model/manager.py` | 去掉"已接收任务"、"调度意图"、LoggerService 控制台 print、ModelManager 运行时调用日志等所有非对话输出，终端只保留 `[suri] 回复内容` | ✅ 已完成 |
| 6 | 新增模型分类体系与 `/models` 命令 | `suri-agent/model/manager.py`, `suri-agent/access/tui/cli.py`, `suri-agent/main.py` | ModelConfig 新增 `model_type` 字段，支持 6 大类型；新增 `/models` 交互式切换命令 | ✅ 已完成 |
| 7 | 全面清理终端非对话输出 | 多个核心模块 | 清理所有核心模块中的 `print`，只保留日志文件写入；清理 `__pycache__` 缓存 | ✅ 已完成 |
| 8 | 多 Agent 调度闭环优化 | `suri-agent/access/tui/cli.py`, `suri-agent/core/context.py`, `suri-agent/main.py` | 增强 suri 系统提示；`_attempt_dispatch` 改为真正执行调度；`context.py` 增加全局组织记忆注入 | ✅ 已完成 |
| 9 | 模型管理 Tool 化 | `suri-agent/tools/model_manager/`, `suri-agent/access/tui/cli.py`, `suri-agent/main.py` | 创建 `model_manager` 工具（list/switch/classify/generate_docs），`/models` 命令通过 ToolService 调用，CLI 只做交互封装 | ✅ 已完成 |
| 10 | 工具权限体系 | `group/central/*/`, `suri-agent/core/context.py`, `suri-agent/core/tool_executor.py`, `suri-agent/tools/tool_registry.md` | 每个角色 soul 增加 `tools` 字段；ContextService 注入角色可用工具列表；ToolService.execute() 增加 `caller_role` 权限检查；更新权限矩阵和申请流程文档 | ✅ 已完成 |
| 11 | 工具同步规则（自动维护） | `suri-agent/rules/tool_sync_rule.py`, `suri-agent/hooks/doc_watcher.py`, `suri-agent/rules/rules.md` | 创建 ToolSyncRule 引擎：扫描 tools/ 目录和角色 soul，自动生成/更新 tool_registry.md；DocWatcher 增加 tools/ 监控；写入 rules.md | ✅ 已完成 |
| 12 | 技能-工具-任务闭环 | `group/central/suri-hr/skills/templates/role_skills.md`, `suri-agent/learning/experience_extractor.py`, `suri-agent/learning/role_learner.py`, `suri-agent/rules/tool_sync_rule.py`, `suri-agent/core/tool_executor.py` | 技能模板增加 `tools` 字段和调用方式；ExperienceExtractor 提取工具使用模式和技能建议；RoleLearner 检测技能更新建议；ToolSyncRule 检查技能依赖；ToolService 记录工具调用历史 | ✅ 已完成 |
| 5 | 文档同步 | `suri-agent/model/model.md`, `development-plan/TASK_BOARD.md` | 更新 CLI 命令说明和失败自动引导说明 | ✅ 已完成 |

---

## 🎉 所有任务已完成

- 新增文件：17 个
- 修改文件：14 个（含本次 2 个）
- 归档文档：1 个
- 全量语法检查：✅ 通过

---

---

## 📘 文档 4：Web UI 仪表盘（WEB_UI_SPEC）— 🔄 待开发

> 规格文档：`development-plan/4.WEB_UI_SPEC.md`
> 目标：在网页中可视化角色任务、机能能力、部门指派；支持跨平台桌面封装

### 4.1 架构决策

| 决策项 | 方案 | 理由 |
|--------|------|------|
| UI 目录 | `ui/` 独立文件夹 + `suri-agent/webui/` API 扩展 | 物理隔离，可一键删除 |
| 前端技术 | 纯 HTML/CSS/JS（零框架） | 无 npm、无构建步骤、可控 |
| 通信方式 | JSON-RPC over HTTP（复用现有 `:8080`） | 后端零改造 |
| 实时推送 | SSE `/events`（可选） | 不强制，轮询可替代 |
| 桌面封装 | Tauri（可选 Phase 4） | ~5MB、Win/macOS 零依赖、Linux 需 webkit2gtk |

### 4.2 功能模块

| 模块 | 说明 | Phase |
|------|------|-------|
| Dashboard 首页 | 系统状态、活跃任务统计、模型池状态 | Phase 2 |
| 任务看板（Kanban） | 四栏（pending/in_progress/completed/failed）、筛选、搜索 | Phase 2 |
| 角色面板 | Soul、技能、模型、工具权限、记忆统计、近期任务 | Phase 2 |
| 组织架构图 | 部门-角色层级树、调度路径可视化 | Phase 2 |
| 审批中心 | 待审批列表、Approve/Reject、历史记录 | Phase 2 |
| 交互终端 | 网页版聊天框、/命令支持 | Phase 2 |
| 实时推送 | SSE 状态变更自动刷新 | Phase 3 |
| 桌面封装 | Tauri 打包 Win/macOS/Linux | Phase 4 |

### 4.3 主程序改造清单

#### 新建文件

| 任务 | 文件 | 状态 |
|------|------|------|
| UI API 桥接包 | `suri-agent/webui/__init__.py` | 🔄 待开发 |
| UI 专用 API 方法 | `suri-agent/webui/api_bridge.py`（getDashboardStats / getAllTasks / getTaskById / getPendingApprovals / getDepartmentTree） | 🔄 待开发 |
| UI 前端入口 | `ui/index.html` | 🔄 待开发 |
| UI 样式 | `ui/css/dashboard.css` | 🔄 待开发 |
| UI 逻辑模块 | `ui/js/rpc.js`、`ui/js/app.js`、`ui/js/dashboard.js`、`ui/js/tasks.js`、`ui/js/roles.js`、`ui/js/org.js` | 🔄 待开发 |
| UI 服务 | `ui/server.py`（静态文件 + /rpc 代理 + /events SSE） | 🔄 待开发 |
| UI 架构文档 | `ui/ui.md` | 🔄 待开发 |

#### 修改现有文件（新增方法，不动现有逻辑）

| 任务 | 文件 | 修改点 | 状态 |
|------|------|--------|------|
| MemoryService 扩展 | `suri-agent/infrastructure/memory.py` | 新增 `get_all_tasks()` — 遍历所有角色 role.db 聚合 tasks 表；新增 `get_pending_approvals()` — 查询 approvals 表 | 🔄 待开发 |

#### 修复现有 Bug（TODO）

| 任务 | 文件 | 修复点 | 状态 |
|------|------|--------|------|
| get_tasks 返回空 | `suri-agent/access/tui/rpc_methods.py` | 从 `return []` 改为实际聚合查询 | 🔄 待开发 |
| get_task_detail 缺少 role_id | `suri-agent/access/tui/rpc_methods.py` | 修复 `memory.get_task(task_id)` → 遍历所有角色数据库搜索 | 🔄 待开发 |
| get_task_messages 缺少 role_id | `suri-agent/access/tui/rpc_methods.py` | 修复 `memory.get_task_messages(task_id)` → 遍历所有角色数据库搜索 | 🔄 待开发 |
| get_pending_approvals 返回空 | `suri-agent/access/tui/rpc_methods.py` | 从 `return []` 改为实际查询 ApprovalService | 🔄 待开发 |

#### 可选修改

| 任务 | 文件 | 修改点 | 条件 |
|------|------|--------|------|
| SSE 端点 | `suri-agent/access/tui/server.py` | 新增 `/events` 路由 | Phase 3 实时推送时 |

### 4.4 实施路径

```
Phase 1: API 补强（后端）
  ├─ 新建 suri-agent/webui/api_bridge.py
  ├─ 修复 rpc_methods.py 的 4 个 TODO
  ├─ 扩展 memory.py（+ get_all_tasks, + get_pending_approvals）
  └─ 验证：所有 RPC 方法返回真实数据

Phase 2: Web Dashboard（前端）
  ├─ 新建 ui/ 目录结构
  ├─ 实现 Dashboard 首页、任务看板、角色面板、组织架构、审批中心、交互终端
  └─ 验证：浏览器访问 localhost:3000 功能正常

Phase 3: 实时化（可选）
  ├─ server.py 新增 /events SSE 端点
  ├─ 前端接入 EventSource
  └─ 验证：任务状态变更自动刷新

Phase 4: 跨平台封装（可选）
  ├─ 安装 Rust + Tauri CLI
  ├─ 创建 src-tauri/ 配置
  ├─ 打包 Windows (.msi) / macOS (.dmg) / Linux (.AppImage)
  └─ 验证：桌面程序运行正常
```

### 4.5 启动方式

```bash
# 终端1：启动 suri-agent JSON-RPC API（现有）
python suri-agent/access/tui/server.py --port 8080

# 终端2：启动 UI 服务（新增）
python ui/server.py --port 3000

# 浏览器打开
open http://localhost:3000
```

### 4.6 回滚方式

```bash
rm -rf ui/ suri-agent/webui/
# 主程序完全恢复，CLI/Telegram/JSON-RPC 不受影响
```

---

## 📊 统计角色（Analyst）— ✅ 已完成（2026-05-01）

> 新增角色：统计分析师，用于统计 Token 消耗、文件创建、任务完成情况

### 实现清单

**Phase 1: 主程序补日志**

| 改造点 | 文件 | 状态 |
|--------|------|------|
| CLI 4处模型调用改 chat_with_usage + log_token_usage | `suri-agent/access/tui/cli.py` | ✅ |
| LoggerService 增强（JSON结构化日志 + role_id参数） | `suri-agent/infrastructure/logger.py` | ✅ |
| FileChannel 文件创建日志 | `suri-agent/access/output/output_channel.py` | ✅ |
| OutputRouter FileChannel 传入 logger | `suri-agent/access/output/output_router.py` | ✅ |
| TaskDispatcher 修复 update_task_status + 任务失败日志 | `suri-agent/core/task_dispatcher.py` | ✅ |

**Phase 2: 创建统计角色**

| 文件 | 状态 |
|------|------|
| `group/central/analyst/analyst.md` (Soul) | ✅ |
| `group/central/analyst/skills/skills.md` | ✅ |
| `group/group_function.md` 更新 | ✅ |

**Phase 3: MemoryService 增强**

| 改造点 | 文件 | 状态 |
|--------|------|------|
| 新增 statistics 表 | `suri-agent/infrastructure/memory.py` | ✅ |
| 新增 save_statistic / get_statistics | `suri-agent/infrastructure/memory.py` | ✅ |
| 新增 get_all_tasks / get_pending_approvals | `suri-agent/infrastructure/memory.py` | ✅ |
| 修复 rpc_methods.py 4个TODO | `suri-agent/access/tui/rpc_methods.py` | ✅ |

### 验证结果

- **语法检查**: 所有修改文件通过 ✅
- **输出框架测试**: 28/28 通过 ✅
- **角色发现**: ConfigService 正确识别 analyst ✅
- **关键词匹配**: "统计"/"token"/"报告" 正确调度到 analyst ✅
- **路由注册**: OutputRouter DEFAULT_ROUTES 包含 analyst ✅

 