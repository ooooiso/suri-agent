# PRD 文档与代码实现交叉分析报告

> 反推代码实现，找出 PRD 文档缺失项与需要更新的内容。

---

## 一、代码已实现但 PRD 文档缺失

### 🔴 严重缺失（影响系统可用性和用户体验）

| # | 缺失文档 | 代码位置 | 实现内容 | 建议 |
|---|---------|---------|---------|------|
| 1 | **CLI 通道实现规范** | `channels/cli/channel.py` | PromptManager、三种交互范式、输入路由、Tab 补全、命令缓存、面板刷新策略 | 新建 `prd/plugins/access/channels/cli-implementation.md` |
| 2 | **LLM 健康追踪机制** | `llm_gateway/plugin.py` 的 `get_health()` / `_health` | 每次 API 调用后记录 `last_success_timestamp` / `last_error_timestamp` | 补充到 `prd/plugins/capability/llm_gateway.md` |
| 3 | **Session 统计分析 API** | `session_hub.py` 的 `get_stats()` | 会话数量、活跃数、通道分布、内存缓存统计 | 补充到 `prd/plugins/access/session-hub.md` |
| 4 | **format_startup_panel 面板** | `formatter.py` | 启动面板（按层分组 + LLM 模型状态合并展示） | 新建或补充 `prd/terminal/startup-panel.md` |
| 5 | **插件详情 7 区块格式** | `formatter.py` 的 `format_plugin_detail()` | 基本信息、依赖关系、能力边界、命令、事件契约、配置项、操作 | 补充到 `prd/terminal/plugin-detail-spec.md` |

### 🟡 中等缺失（优化功能，不影响启动）

| # | 缺失文档 | 代码位置 | 实现内容 | 建议 |
|---|---------|---------|---------|------|
| 6 | **热更新模块内部架构** | `shared/hot_reload.py` | FileWatcher 轮询 + HotReloadManager EventBus 集成 + L1/L2/L3 分级 | `prd/operations/hot-reload.md` 已有框架，补充实现细节 |
| 7 | **LLM Gateway 命令路由 /switch /setkey** | `channels/cli/channel.py` 的 `_handle_switch/_handle_setkey` | CLI 侧完整实现（含配置持久化） | 补充到 `prd/plugins/capability/llm_gateway.md` |
| 8 | **异步输入安全守卫** | `channel.py` 的 `_start_input_async()` | `sys.stdin.isatty()` 非 TTY 跳过，避免 `connect_read_pipe` 永久阻塞 | 补充到 CLI 通道文档 |
| 9 | **manifest.json 命令自动注册** | `commands.py` + `manager.py` | 插件启动时 scan manifests → `load_commands_from_manifests()` | 补充到 `prd/terminal/plugin-commands-interface.md` |

### 🟢 低优先级缺失

| # | 缺失文档 | 代码位置 | 实现内容 |
|---|---------|---------|---------|
| 10 | `/hotreload` 命令交互 | `channel.py` `_handle_hotreload()` | 显示热更新 L1/L2/L3 支持状态、FileWatcher 轮询间隔 |
| 11 | `/plugin start/stop/restart` 管理 | `channel.py` `_handle_plugin_manage()` | 插件启动/暂停/重启/升级/删除操作 |
| 12 | `/status` 系统状态命令 | `channel.py` `_handle_status()` | LLM 状态、插件数量、会话 ID |

---

## 二、PRD 文档已存在但代码未实现

| # | PRD 文档 | 代码状态 | 实现度 | 说明 |
|---|---------|---------|--------|------|
| 1 | `prd/plugins/capability/upgrade_manager.md` | ❌ 无代码 | 0% | 插件自升级、版本协商、审批流程 |
| 2 | `prd/plugins/capability/wiki_service.md` | ❌ 无代码 | 0% | 知识库索引 |
| 3 | `prd/plugins/capability/knowledge_base.md` | ❌ 无代码 | 0% | 知识库基础框架 |
| 4 | `prd/plugins/extension/cron_service.md` | ❌ 无代码 | 0% | 定时任务 |
| 5 | `prd/plugins/extension/doc_sync.md` | ❌ 无代码 | 0% | 文档同步 |
| 6 | `prd/plugins/extension/monitor.md` | ❌ 无代码 | 0% | 监控 |
| 7 | `prd/plugins/access/channels/desktop.md` | ❌ 无代码 | 0% | 桌面端通道 |
| 8 | `prd/plugins/access/channels/web.md` | ❌ 无代码 | 0% | Web 通道 |
| 9 | `prd/plugins/access/channels/telegram.md` | ⚠️ 部分实现 | ~30% | Telegram 通道（有 `telegram.py/telegram_bot.py` 但未集成 session-hub） |

---

## 三、代码与 PRD 描述不一致（需更新 PRD）

| # | PRD 文档 | PRD 描述 | 代码实际情况 | 建议更新 |
|---|---------|---------|-------------|---------|
| 1 | `channel-capabilities.md` | CLI "面板渲染 ✅ 新增"、"编号快速查看 ✅ 新增"、"Tab 命令补全 ✅ 新增" | 已稳定实现 | 改为 ✅ 已实现 |
| 2 | `hot-reload.md` | 列出各插件热更新状态："llm_gateway ⏳ 待适配" | `get_health()` 已实现健康追踪 | 更新为 ✅ 已完成 |
| 3 | `hot-reload.md` | 列出各插件热更新状态："agent_registry ⏳ 待适配"、"code_tool ⏳ 待适配" | 确实未适配 | 保持 ⏳ 待适配 |
| 4 | `hot-reload.md` | 代码示例中 `logger.info` | 实际代码使用 `print()`（无 logging 模块） | 更新代码示例 |
| 5 | `hot-reload.md` | `FileWatcher` 参数签名 `on_change` | 实际代码使用事件注册 `self._watcher.on("manifest", callback)` | 更新 API 文档 |
| 6 | `startup.md` | 启动流程前几步与当前 `plugin.py` 的 `bootstrap()` 步骤数可能不对应 | Step 9/10/11 有调整 | 需对齐步骤号 |
| 7 | `access/README.md` | 通道注册示例使用 `hub.register_channel()` | 实际使用 `session_hub.register_channel()` | 更新方法名 |

---

## 四、PRD 文档目录结构应补充的文件

### 4.1 终端 / Terminal 独立目录

当前 `prd/` 下没有 terminal 目录，但代码中存在大量终端特有功能：

```
prd/terminal/                          # 新建
├── README.md                          # 终端交互体系总览
├── prompt-manager.md                  # 提示符管理（PromptManager）
├── plugin-detail-spec.md              # 插件详情 7 区块（已引用但不存在）
├── plugin-commands-interface.md       # 命令注册接口（已引用但不存在）
├── model-status-spec.md               # 模型状态面板（已引用但不存在）
├── ux-requirements.md                 # 三种交互范式
└── startup-panel.md                   # 启动面板格式
```

### 4.2 热更新实现细节

```
prd/operations/
└── hot-reload-implementation.md       # 新增：FileWatcher/HotReloadManager 实现细节
```

---

## 五、立即应补充的 PRD 文档（按优先级）

### P0 — 影响系统理解

1. **`prd/terminal/plugin-detail-spec.md`** — 补充插件详情 7 区块渲染规范
2. **`prd/terminal/model-status-spec.md`** — 补充 LLM 模型状态面板渲染规范
3. **`prd/plugins/capability/llm_gateway.md` 更新** — 补充 `get_health()` API 和健康状态生命周期

### P1 — 影响功能完整性

4. **`prd/plugins/access/session-hub.md` 更新** — 补充 `get_stats()` API
5. **`prd/operations/hot-reload.md` 更新** — 同步 FileWatcher 实际 API（event 回调模式）
6. **`prd/plugins/access/channel-capabilities.md` 更新** — CLI 能力从"新增"改为"已实现"

### P2 — 影响扩展开发

7. **`prd/plugins/access/channels/cli-implementation.md`** — 新建，记录 CLI 通道实现细节
8. **`prd/terminal/prompt-manager.md`** — 新建，记录 PromptManager 设计
9. **`prd/terminal/startup-panel.md`** — 新建，记录启动面板渲染策略

---

## 六、代码与 PRD 的架构偏离

### 6.1 已发生的架构偏离（无 PRD 但代码已实现）

```
代码实现                          PRD 状态
──────────────────────────────────────────────
commands.py 命令注册表            无对应 PRD 文档
format_startup_panel 启动面板    无对应 PRD 文档
format_plugin_detail 7 区块      无对应 PRD 文档
get_health() 健康追踪             无对应 PRD 文档
channel.py 三种交互范式           无对应 PRD 文档
SSE/subprocess 事件监听          无对应 PRD 文档
```

### 6.2 PRD 中规划但未实现的架构

```
PRD 规划                          代码状态
──────────────────────────────────────────────
upgrade_manager                   完全未实现
wiki_service                     完全未实现
knowledge_base                   完全未实现
cron_service                     完全未实现
doc_sync                         完全未实现
monitor                          完全未实现
Web 通道                         完全未实现
桌面端通道                        完全未实现
Telegram 通道集成 session-hub    只实现了基础 bot 功能
```

---

## 七、总结

### 需要新建的 PRD 文档

| 文档路径 | 优先级 | 对应代码 |
|---------|--------|---------|
| `prd/terminal/plugin-detail-spec.md` | P0 | `formatter.py::format_plugin_detail()` |
| `prd/terminal/model-status-spec.md` | P0 | `formatter.py::format_model_status()` |
| `prd/terminal/startup-panel.md` | P1 | `formatter.py::format_startup_panel()` |
| `prd/terminal/prompt-manager.md` | P1 | `channel.py::PromptManager` |
| `prd/terminal/plugin-commands-interface.md` | P1 | `commands.py::CommandInfo/register_command()` |

### 需要更新的 PRD 文档

| 文档路径 | 更新内容 | 优先级 |
|---------|---------|--------|
| `prd/plugins/capability/llm_gateway.md` | 补充 `get_health()` API、健康状态生命周期 | P0 |
| `prd/plugins/access/session-hub.md` | 补充 `get_stats()` API | P1 |
| `prd/operations/hot-reload.md` | 同步 FileWatcher API（事件回调模式）、代码示例、各插件适配状态 | P1 |
| `prd/plugins/access/channel-capabilities.md` | CLI 能力状态改为"已实现" | P1 |

### 长期路线图

| 方向 | 说明 | 建议阶段 |
|------|------|---------|
| 补 P0 PRD 文档 | plugin-detail-spec.md、model-status-spec.md、llm_gateway.md 更新 | 立即 |
| 补 P1 PRD 文档 | startup-panel.md、prompt-manager.md、commands-interface.md | 迭代 1 |
| 补 P2 PRD 文档 | hot-reload 同步、session-hub 补充、channel-capabilities 更新 | 迭代 2 |
| 实现 PRD 规划 | upgrade_manager、Telegram 集成、Web 通道 | 迭代 3+ |