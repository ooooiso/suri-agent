# Suri-Agent 可执行开发计划

> **依据**：全部 37 份 PRD 文档交叉审计结果
> **文档交叉引用**：每项任务标注了来源文档的精确章节
> **底库状态**：12/20 插件已实现（含核心框架618行），8个缺失
> **总工时**：~28 开发日（P1 9天 + P2 19天）

---

## 零、开发规则总纲

### 0.1 不可违反的架构约束（来源于 PRD）

| # | 约束 | 来源文档§ | 违反后果 |
|---|------|----------|---------|
| C1 | 角色数据全在 `roles/`（Git管理） | directory-structure.md:12, design-principles.md:271+ | 换设备丢失记忆 |
| C2 | 系统配置在 `~/.suri/`（不纳入Git） | directory-structure.md:17, framework-rules.md:176+ | API Key泄漏 |
| C3 | 通信全走EventBus，禁止直接方法调用 | framework-rules.md §6, suri_core.md:37 | 无法解耦 |
| C4 | 插件只响应事件/角色调用，不主动决策 | framework-rules.md:33+, plugins/README.md | 逻辑混乱 |
| C5 | 所有代码自修改须用户确认 | framework-rules.md:49+, coevolution.md:74+ | 不可控变更 |
| C6 | 订阅事件时禁止重新发布同名事件（防循环） | plugin-development.md:140-155 | EventBus死循环 |
| C7 | LLM请求全走llm_gateway | architecture.md:240, framework-rules.md:187 | 绕过速率控制 |
| C8 | 所有数据写入必须幂等 | framework-rules.md:212+ | 重试导致重复 |

### 0.2 核心流程执行链（串行依赖）

```
启动（startup.md §2-4）
  → 系统就绪，发布 system.started（program-flow.md §1）
  → 等待 user.input（system-flow.md §1）
    → suri分析需求 → 创建角色/分配任务（system-flow.md §3）
      → 单角色执行（system-flow.md §2）
        → 步骤受阻 → 异常处理（system-flow.md §6）
        → 步骤完成 → 角色学习（system-flow.md §4）
      → suri升级自身（system-flow.md §5）
      → 多角色协作（system-flow.md §7）
```

### 0.3 插件分层加载顺序（Program-flow.md §1固定）

```
Layer 0:  suri_core（main.py自举）
Layer 1:  config_service → log_service → security_service（基础服务）
Layer 2:  task_scheduler → task_planner → agent_registry → role_comm → interrupt_handler → code_tool（执行层）
Layer 3:  llm_gateway → memory_service → role_manager → role_learner → mcp_framework → upgrade_manager（能力层）
Layer 4:  access（接入层）
Layer 5:  cron_service → hooks_service → test_framework → doc_sync → monitor（扩展层）
```

### 0.4 已实现 vs 缺失清单

| 状态 | 插件 | 代码行 | 测试文件 | 依赖 |
|------|------|--------|---------|------|
| ✅ | suri_core | 183行 | ✓ | 无 |
| ✅ | config_service | 125行 | ✗ | 无 |
| ✅ | log_service | 89行 | ✗ | 无 |
| ✅ | security_service | 174行 | ✓ | 无 |
| ✅ | task_scheduler | 433行 | ✗ | 无 |
| ✅ | task_planner | 599行 | ✓ | llm_gateway, role_manager |
| ✅ | agent_registry | 244行 | ✓ | 无 |
| ✅ | interrupt_handler | 532行 | ✓ | 无 |
| ✅ | code_tool | 176行 | ✓ | 无 |
| ✅ | llm_gateway | 432行 | ✓ | 无 |
| ✅ | role_manager | 461行 | ✓ | llm_gateway |
| ✅ | access | 246行 | ✓ | 无 |
| ✅ | test_framework | 172行 | ✓ | 无 |
| ❌ | **role_comm** | 0行 | ✗ | 无 |
| ❌ | **memory_service** | 0行 | ✗ | 无 |
| ❌ | **role_learner** | 0行 | ✗ | llm_gateway |
| ❌ | **upgrade_manager** | 0行 | ✗ | 无 |
| ❌ | **mcp_framework** | 0行 | ✗ | 无 |
| ❌ | **cron_service** | 0行 | ✗ | 无 |
| ❌ | **hooks_service** | 0行 | ✗ | 无 |
| ❌ | **doc_sync** | 0行 | ✗ | 无 |
| ❌ | **monitor** | 0行 | ✗ | log_service |

---

## 一、P0 — 紧急修复（2天，与P1并行）

> 修复 PRD 审计发现的阻塞性问题，确保开发基础正确。

### P0-1 启动自检（healthcheck）— 1天

**来源**：startup.md §4 定义7项自检 → suri_core.md §3 → 代码缺失

**文件修改**：
```
agent_framework/core/suri_core/plugin.py
├── `bootstrap()` 第4步（加载插件后）插入 `await self._healthcheck()`
├── `_healthcheck()` — 调用6项子检查
│   ├── `_check_environment()` — 检查运行时目录权限、roles/suri/完整性
│   │   ├── ~/.suri/runtime/ 可读写
│   │   ├── roles/suri/soul.md 存在
│   │   ├── roles/suri/memories/ 存在
│   │   └── roles/suri/skills/ 存在
│   ├── `_check_database()` — 打开SQLite、验证迁移已执行、检查表存在
│   │   └── 检查 plugins表、events表是否存在
│   ├── `_check_config()` — 检查必要配置项是否存在
│   │   ├── config.json 存在
│   │   ├── 至少有一个LLM配置（provider + api_key）
│   │   └── access 通道配置（至少CLI启用）
│   ├── `_check_role()` — 检查suri角色完整性
│   │   ├── soul.md 解析正常
│   │   └── meta.json 存在
│   ├── `_check_plugins()` — 检查核心插件就绪状态
│   │   ├── 检查已实现的12个插件已加载
│   │   └── 缺失插件记录warning但不阻断
│   └── `_check_system()` — 系统资源检查
│       ├── 磁盘剩余 > 100MB
│       └── 内存 > 50MB
└── 自检失败的处理策略：
    ├── 警告项 → 记录warning，继续启动
    └── 错误项 → 记录error，继续启动但标记系统降级状态
```

**测试文件**：`tests/unit/test_suri_core_healthcheck.py`
```python
class TestHealthCheck:
    async def test_healthcheck_passes_on_first_run(self):  # 验证新环境自检通过
    async def test_healthcheck_reports_missing_soul(self):  # 删除soul.md后自检警告
    async def test_healthcheck_reports_db_missing_table(self):  # 删除表后自检警告
    async def test_healthcheck_reports_config_missing(self):  # 无config时自检警告
    async def test_system_started_only_after_healthcheck(self):  # 验证system.started在自检后发布
```

**验收**：
- `python -m pytest tests/unit/test_suri_core_healthcheck.py -v` 全部通过
- `bootstrap()` 在新环境执行无报错
- 删除 `~/.suri/config.json` 后启动看到 warning（不崩溃）

---

### P0-2 PluginManager 依赖拓扑排序 + 循环依赖检测 — 0.5天

**来源**：startup.md §3 → suri_core.md:55 → plugin-development.md §12.1 → 代码缺失

**文件修改**：
```
agent_framework/plugin_manager/manager.py
├── `load_all()` 改为拓扑排序加载
│   ├── 扫描所有 manifest.json → 提取 dependencies
│   ├── 构建有向图：graph[name] = downstream_set（依赖该插件的集合）
│   ├── 计算入度：in_degree[name] = len(dependencies)
│   ├── 入度=0入队列 → 逐个加载 → 更新下游入度
│   └── 循环检测：加载数 < 总数 → 发布 error.plugin 事件，报告循环路径
├── `_load_single(plugin_dir)` — 从`load_all()`拆分出单插件加载逻辑
│   ├── 读取 manifest.json
│   ├── AST安全扫描（复用security_service接口）
│   ├── 检查依赖是否就绪
│   ├── import + init + register_events + start
│   └── 发布 system.plugin_loaded 事件
└── 新增异常类 `PluginDependencyCycleError`（在文件顶部定义）
```

**测试文件**：
```
tests/unit/test_plugin_manager.py（追加）
├── test_topological_sort_simple(self):
│   # A依赖B → 加载顺序 [B, A]
├── test_topological_sort_complex(self):
│   # A依赖B, B依赖C → [C, B, A]
├── test_cycle_detection(self):
│   # A依赖B, B依赖C, C依赖A → 抛出PluginDependencyCycleError
├── test_missing_dependency_skipped(self):
│   # A依赖缺失插件B → A跳过加载，记录warning
├── test_no_dependencies_loaded_first(self):
│   # A无依赖, B依赖A → [A, B]
└── test_manifest_without_dependencies_still_valid(self):
│   # manifest.json无dependencies字段 → 视为无依赖，正常加载
```

**验收**：
- 循环依赖时抛出明确异常并报告循环路径
- 缺失依赖插件跳过加载并记录 warning
- 已有测试全部通过（`tests/unit/test_plugin_manager.py`）

---

### P0-3 事件注册表与event_types.py对齐 — 0.5天

**来源**：coevolution.md §7 → event-registry.md → shared/utils/event_types.py → 检查对齐

**检查项**：
```python
# shared/utils/event_types.py 中定义的 EventType
# 必须与 event-registry.md 完整对齐
# 两者不一致的立即修复
```

**文件修改**：
```
shared/utils/event_types.py
├── 按 event-registry.md 分类补充缺失的事件类型
│   ├── 补全 upgrade.* 事件族（6个）
│   ├── 补全 interrupt.* 事件族（2个）
│   ├── 补全 doc_sync.* 事件族
│   └── 无冗余未使用的事件
└── 确保 EventType 枚举值 == 字符串事件名

prd/schema/event-registry.md
├── 补充每个事件的 Payload Schema（JSON格式）
├── 补充发布者/订阅者/触发条件
└── 与 event_types.py 完全对齐
```

**验收**：
- `grep -c "EventType\." shared/utils/event_types.py` 与 event-registry.md 事件数一致
- 无冗余事件定义

---

## 二、P1 — 基础强化（7天）

> 修复当前实现与 PRD 文档之间的差距，补齐缺失的核心功能。

### P1-1 code_tool 追加 `create_file` + 幂等写入 — 1天

**来源**：code_tool PRD → framework-rules.md:212 数据写入幂等规则 → directory-structure.md 目录创建时机

**文件修改**：
```
plugins/code_tool/writer.py
├── `write_file(path, content)` 改为使用临时隔离空间
│   ├── tmp = path + ".tmp.{uuid4}"
│   ├── 写入tmp文件
│   ├── os.rename(tmp, path) — 原子操作
│   └── 写入后 fsync 确保持久化
├── `append_file(path, content)` — 追加内容
│   ├── 检查文件是否存在（不存在则创建）
│   ├── 追加写入
│   └── 幂等校验：同一内容重复追加 → 跳过（基于最后N行hash）
├── `create_file(path, content)` — 仅当文件不存在时创建
│   ├── 先检查os.path.exists(path)
│   ├── 已存在 → 返回已存在的提示，不覆盖
│   └── 不存在 → 调用 write_file
└── 所有操作统一返回：{"success": bool, "path": str, "size": int, "hash": str}
```

**测试文件**：`tests/plugin/test_code_tool.py`（追加）
```python
class TestWriterPowerIdempotent:
    async def test_write_then_read_atomic(self):  # 写入后读取内容一致
    async def test_append_duplicate_skipped(self):  # 重复追加被跳过
    async def test_create_file_exists_error(self):  # 创建已存在文件返回提示
    async def test_create_file_new_success(self):  # 创建新文件成功
    async def test_write_concurrent_safety(self):  # 并发写入不互相覆盖
```

**验收**：
- `create_file` 幂等：第2次调用不覆盖内容
- `append_file` 幂等：完全相同的追加被跳过
- 原子写入：写入过程中断电不产生损坏文件

---

### P1-2 数据外部化（去硬编码）— 1.5天

**来源**：hot-reload.md §2.1（6个硬编码项）→ framework-rules.md 零硬编码原则

**文件修改**（3个文件，6个模板/配置）：

```
#1 plugins/role_manager/plugin.py
├── 删除 SOUL_TEMPLATE 硬编码字符串（~80行）
├── `_get_default_soul_template()` → 改为从 ~/.suri/data/templates/soul_template.md 读取
└── 如果文件不存在 → 从内置 fallback 写入到文件（一次性的初始化）

#2 plugins/role_manager/plugin.py
├── `_get_system_prompt()` 中的工具调用说明硬编码
├── 改为从 ~/.suri/data/templates/tool_descriptions.yaml 读取
├── 格式：yaml 列表，每个工具 {name, description, params}
└── hot-reload.md §3.4：发布 tool.registered 时自动更新此文件

#3 plugins/task_planner/plugin.py
├── `_load_builtin_templates()` 中的内置模板硬编码
├── 改为从 ~/.suri/data/templates/task_templates.yaml 读取
└── 首次运行时将内置模板写入该文件

#4 plugins/interrupt_handler/plugin.py
├── `_classify_reason()` 中的关键词列表硬编码
├── 改为从 ~/.suri/data/configs/interrupt_keywords.yaml 读取
└── hot-reload.md §2.1 #4

#5 plugins/access/plugin.py
├── 通道路由逻辑硬编码
├── 改为从 ~/.suri/data/configs/channel_routes.yaml 读取
└── hot-reload.md §2.1 #5

#6 plugins/role_manager/plugin.py
├── `_create_suri()` 中的 fallback 文本
├── 改为从 ~/.suri/data/templates/suri_fallback.md 读取
└── hot-reload.md §2.1 #6
```

**新增文件**（首次运行时自动创建）：
```
~/.suri/data/templates/soul_template.md
~/.suri/data/templates/tool_descriptions.yaml
~/.suri/data/templates/task_templates.yaml
~/.suri/data/configs/interrupt_keywords.yaml
~/.suri/data/configs/channel_routes.yaml
~/.suri/data/templates/suri_fallback.md
```

**测试文件**：
```
tests/unit/test_hot_reload_externalization.py
├── test_soul_template_loaded_from_file(self):
│   # 有外部文件 → 从文件读
├── test_soul_template_fallback_written(self):
│   # 无外部文件 → 写入内置fallback
├── test_hot_reload_detected(self):
│   # 修改外部文件 → 插件重新加载
├── test_keywords_updated_during_reload(self):
│   # 修改 keywords.yaml → interrupt_handler 实时更新
```

**验收**：
- 删除 `~/.suri/data/templates/soul_template.md` 后启动 → 自动从内置fallback重建
- 修改 `interrupt_keywords.yaml` 后重新加载插件 → 新关键词生效
- Python代码中无残留的业务数据硬编码

---

### P1-3 优雅关闭 + 数据持久化 — 1.5天

**来源**：program-flow.md §5 → suri_core.md §3

**文件修改**：
```
agent_framework/core/suri_core/plugin.py
├── `stop()` 方法增强：
│   ├── 1. 设置内部标志停止接收新事件（event_bus.pause()）
│   ├── 2. 发布 system.shutdown（reason="user_request", force=False, timeout=30）
│   ├── 3. 等待运行中任务完成（task_scheduler.wait_for_completion(timeout=30)）
│   ├── 4. 按依赖反向卸载所有插件（plugin_manager.unload_all(reverse=True)）
│   ├── 5. 持久化 EventBus 队列剩余事件到 SQLite（event_bus.flush_pending()）
│   ├── 6. 关闭 EventBus worker（event_bus.stop()）
│   ├── 7. 归档会话日志（log_service.archive_session()）
│   ├── 8. 如果没有 force 标记，清理 /tmp/suri-agent/ 临时文件
│   └── 9. 系统退出

agent_framework/plugin_manager/manager.py
├── `unload_all(reverse=True)` — 按加载顺序的反向卸载
│   ├── 每步调用 plugin.stop() + plugin.cleanup()
│   └── 超时30秒强制终止

plugins/log_service/plugin.py（如果已实现stop/cleanup）
├── `stop()`：刷新日志缓冲区
├── `cleanup()`：关闭文件句柄
└── `archive_session()`：将当前会话日志归档
```

**测试**：
```
tests/integration/test_graceful_shutdown.py
├── test_shutdown_completes_all_tasks(self):
│   # 发布 system.shutdown → 等待 → 检查所有task.state == completed
├── test_shutdown_timeout_force_stop(self):
│   # task运行超时 → force=True → 强制终止
├── test_shutdown_events_persisted(self):
│   # 队列中未处理事件 → 关闭后SQLite可查到
├── test_shutdown_twice_no_error(self):
│   # 连续调用2次 → 第2次不报错
```

**验收**：
- `Ctrl+C` 触发 SIGINT → 优雅关闭（所有插件stop/cleanup被调用）
- 关闭后 EventBus 队列中未处理事件已持久化到 SQLite
- 再次启动后未处理事件可恢复

---

### P1-4 消除文档重复 — 1天

**来源**：AUDIT-REPORT.md §3.1（3组重复）

**文件修改**：
```
prd/operations/startup.md（保留为启动流程唯一权威文档）
├── §1 和 §2 保持完整（启动架构 + 分层加载）
├── §3 用户初始化场景（完整保留）
├── §4 启动自检（完整保留）
├── §5 迁移场景（完整保留）
└── §6 开发者调试（完整保留）

prd/operations/program-flow.md（删除重复的启动描述）
├── §1 启动流程 改为：
│   "启动流程详见 startup.md §2-4。本节仅保留程序级流程图。"
├── 保留 §3 插件加载流程（此部分不重复，是程序级描述）
├── 保留 §4 插件卸载流程
├── 保留 §5 系统关闭流程（与 startup.md 不重叠）
├── 保留 §6 配置热更新
└── 保留 §7 错误处理

prd/overview/architecture.md（删除与 framework-rules.md 重叠的架构分层）
├── §2 系统架构分层 改为：
│   "分层详见 framework-rules.md §二。本节仅保留概念定义。"
├── 保留 §1 核心架构理念（suri定位/多Agent，不重复）
├── 保留 §5 四维协同进化（框架规则中没有）
├── 保留 §6 角色通信模型（框架规则中没有）
├── 保留 §7 并发与上下文控制（框架规则中没有）
└── 保留 §8 关键约束（框架规则中没有）

prd/operations/framework-rules.md（保留为框架规则唯一权威文档）
├── §一 核心架构原则（保留，不删除）
├── §二 系统架构（完整保留，不与architecture.md重复）
└── 其他部分不变
```

**验收**：
- `startup.md` vs `program-flow.md` §1 内容不重叠
- `architecture.md` vs `framework-rules.md` 内容重合度 < 30%

---

### P1-5 修复文档交叉引用 — 1天

**来源**：AUDIT-REPORT.md §3.4

**文件修改**：
```bash
# 扫描所有文档中的引用路径，修复失效链接
# 执行命令：
# grep -rn "prd/" --include="*.md" . | grep -E "\[.*\]\(.*\)"

prd/agents/skill-spec.md → template-spec.md → 修复为 prd/schema/template-spec.md
prd/plugins/README.md → 修复prd/plugins/下文件的引用路径
（其他扫描结果按实际修复）
```

**验收**：
- 所有文档间的 `[链接文本](路径)` 路径有效
- `broken-link-checker` 扫描无 404

---

## 三、P2 — 缺失插件实现（19天）

> 实现 PRD 中定义但代码中缺失的 8 个插件。按依赖顺序排列。

### P2-1 role_comm（角色通信）— 3天

**来源**：role_comm.md（完整PRD 241行）→ architecture.md §6（角色通信模型）→ system-flow.md §7（多角色协作流依赖）

**前置依赖**：无
**被依赖**：所有可能参与协作的角色

**新增文件**：
```
plugins/role_comm/
├── __init__.py              # from .plugin import RoleCommPlugin
├── manifest.json            # type: execution, dependencies: []
├── plugin.py                # 主实现（~350行）
└── tests/
    └── test_plugin.py       # 10个测试用例
```

**`plugin.py` 实现细节**：

```python
class RoleCommPlugin(PluginInterface):
    """角色通信服务。纯事件驱动，全部通过EventBus交互。"""
    
    # --- EventBus 接口（订阅）---
    # 订阅事件：
    #   role.message            → _on_message(sender→receiver, 存储+转发)
    #   role.messages_query     → _on_query(角色查询未读消息)
    #   role.messages_consume   → _on_consume(角色标记已读)
    #   role.messages_summary   → _on_summary(获取消息摘要)
    #   
    # 发布事件：
    #   role.message_received   → 通知接收方有未读消息
    #   role.messages_result    → 响应查询
    #   role.messages_consumed  → 响应消费
    #   role.messages_summary_result → 响应摘要
    
    async def _on_message(self, event: Event):
        """处理 role.message 事件。
        
        Payload:
        - from_role: str
        - to_role: str
        - session_id: str（格式: {role_A}↔{role_B}__{project}_{topic}）
        - content: str（自然语言消息）
        - reply_to: Optional[str]（回复链，默认None）
        
        流程：
        1. 存储到SQLite messages表
        2. 长内容（>500字符）自动生成摘要（调llm_gateway）
        3. 发布 role.message_received → to_role
        """
    
    async def _on_query(self, event: Event):
        """处理角色查询。
        
        Payload:
        - role_id: str
        
        返回按 session_id 分组的未读消息列表。
        每条消息带 summary（如有）。
        """
    
    async def _on_consume(self, event: Event):
        """标记消息已读。
        
        Payload:
        - role_id: str
        - session_id: str（可选，不传则消费所有）
        - msg_ids: List[str]（可选，不传则消费全部）
        """
    
    # --- 批处理（role_comm.md §4.2）---
    # batch_window_ms: 2000（等2秒攒多条）
    # max_batch_size: 5（或攒够5条再处理）
    # 实现：asyncio.create_task 延迟处理 + 计数器
```

**SQLite 表**（database.md 定义的 messages 表）：
```sql
-- agent_framework/migrations/003_role_comm.sql
CREATE TABLE IF NOT EXISTS messages (
    msg_id TEXT PRIMARY KEY,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    timestamp REAL NOT NULL,
    consumed INTEGER DEFAULT 0,
    reply_to TEXT
);
CREATE INDEX idx_messages_session ON messages(session_id, consumed, timestamp);
CREATE INDEX idx_messages_receiver ON messages(to_role, consumed, timestamp);
```

**测试（10个用例）**：
```python
class TestRoleComm:
    # 基础功能
    async def test_send_message_stored(self):  # 发送消息→存储到SQLite
    async def test_receive_notification(self):  # 存储后→发布 role.message_received
    async def test_query_unread(self):  # 查询未读消息返回正确
    async def test_consume_message(self):  # 标记已读后不再返回
    
    # session 隔离
    async def test_session_isolation(self):  # 不同session消息隔离
    async def test_session_grouped_query(self):  # 查询结果按session分组
    
    # 消息摘要
    async def test_long_message_summary(self):  # 长消息自动生成摘要
    async def test_summary_in_result_not_full(self):  # 查询返回summary非全文
    
    # 边界
    async def test_concurrent_messages(self):  # 并发发送不丢失
    async def test_retention_cleanup(self):  # 过期消息被清理
```

---

### P2-2 memory_service（记忆存储）— 3天

**来源**：memory_service.md（完整PRD）→ system-flow.md §4（角色学习读写记忆）→ directory-structure.md roles/{role_id}/memories/

**前置依赖**：无
**被依赖**：role_learner（P2-4）、role_manager

**新增文件**：
```
plugins/memory_service/
├── __init__.py              # from .plugin import MemoryServicePlugin
├── manifest.json            # type: capability
├── plugin.py                # 主实现（~400行）
├── store.py                 # SQLite WAL模式封装（~100行）
├── retriever.py             # 记忆检索（~80行）
└── tests/
    └── test_plugin.py       # 12个测试用例
```

**`plugin.py` 实现细节**：

```python
class MemoryServicePlugin(PluginInterface):
    """角色记忆存储服务。每个角色独立的SQLite数据库。"""
    
    def init(self, event_bus, config):
        # 连接角色级数据库
        # roles/{role_id}/memories/role.db（每个角色独立）
    
    # --- 事件接口 ---
    # 订阅：
    #   system.started → 初始化所有角色的数据库
    #   role.created → 创建新角色的数据库
    #   memory.* 事件族 → 记忆CRUD
    # 发布：
    #   memory.stored → 记忆已存储
    #   memory.retrieved → 检索结果
    
    # --- 对外接口（角色直接调用的方法）---
    async def get_messages(role_id: str, session_id: str, limit: int = 20):
        """获取角色在session中的历史消息"""
    async def get_insights(role_id: str, keyword: str = None, limit: int = 5):
        """获取角色洞察（关键词筛选）"""
    async def get_facts(role_id: str, domain: str = None):
        """获取角色已确认事实"""
    async def set_fact(role_id: str, key: str, value: str, confidence: float):
        """设置事实（幂等：key相同则覆盖）"""
    async def store_experience(role_id: str, task_id: str, experience: str):
        """存储角色经验"""
    async def add_insight(role_id: str, insight_type: str, content: str, 
                          relevance_keywords: List[str]):
        """添加学习洞察"""
    async def search_memories(role_id: str, query: str, top_k: int = 5):
        """语义检索记忆（按关键词匹配+时间排序）"""
```

**SQLite 表**（database.md 定义的角色级模型）：
```sql
-- 每个角色独立 database（roles/{role_id}/memories/role.db）
CREATE TABLE insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,  -- success_pattern / improvement / pitfall / preference
    content TEXT NOT NULL,
    keywords TEXT,        -- 逗号分隔的关键词，用于检索
    created_at TEXT NOT NULL
);

CREATE TABLE facts (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    domain TEXT,           -- 领域分类
    confidence REAL DEFAULT 0.5,
    updated_at TEXT NOT NULL
);

CREATE TABLE experiences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    experience TEXT NOT NULL,  -- 经验总结（LLM生成的简短描述）
    timestamp TEXT NOT NULL
);
```

**角色隔离铁律**：
- 每个角色只能读写自己的 role.db
- 路径注入防护：role_id 中不能包含 `../` 或 `/`
- 测试验证：角色A试图读写角色B的数据库 → 拒绝

**测试（12个用例）**：
```python
class TestMemoryService:
    # CRUD
    async def test_store_and_retrieve_insight(self):
    async def test_set_and_get_fact(self):
    async def test_store_experience(self):
    async def test_search_by_keyword(self):
    
    # 角色隔离
    async def test_role_isolation_prevented(self):  # 跨角色读写 → 拒绝
    async def test_path_injection_blocked(self):  # role_id="../evil" → 拒绝
    
    # 启动
    async def test_db_created_on_role_created(self):  # 新角色创建时自动建库
    async def test_db_initialized_on_startup(self):  # 启动时初始化所有角色DB
    
    # 边界
    async def test_concurrent_read_write(self):  # 并发读写不阻塞（WAL模式）
    async def test_empty_search_returns_empty(self):  # 无匹配检索 → []
    async def test_large_content_stored(self):  # 存储长内容不截断
```

---

### P2-3 agent_registry SQLite 持久化 — 1天

**来源**：agent_registry.md → database.md 表结构 → plugin-development.md §12.4（已知问题）

**文件修改**：
```
plugins/agent_registry/plugin.py
├── 新增 SQLite 表管理（在 manifest.json 目录下建 own.db 或复用 suri.db）
│   └── CREATE TABLE IF NOT EXISTS agents (...)
│   └── CREATE TABLE IF NOT EXISTS agent_steps (...)
├── `create_agent(role_id, task_id)` → 写入SQLite
├── `get_agent(agent_id)` → 从SQLite读取
├── `update_agent_state(agent_id, state, progress)` → 更新SQLite
├── `block_agent(agent_id, reason)` → 更新状态为 blocked + 记录原因
├── `cancel_agent(agent_id)` → 更新状态为 cancelled
├── `list_agents(role_id=None, state=None)` → 按条件查询
├── `on_startup()` → 从SQLite恢复所有活跃Agent（状态为 in_progress 或 waiting）
└── 原有内存字典保留为 L1 缓存，SQLite 为 L2 持久化层
```

**SQLite 表**（用已有 migration `002_agents.sql`）：
```sql
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    progress REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_info TEXT
);

CREATE TABLE IF NOT EXISTS agent_steps (
    step_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    started_at TEXT,
    completed_at TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
```

**测试（追加）**：
```python
class TestAgentPersistence:
    async def test_create_and_persist(self):  # 创建Agent后SQLite可查
    async def test_recover_on_startup(self):  # 重启后恢复活跃Agent
    async def test_state_transition_persisted(self):  # 状态变更写入SQLite
    async def test_cancelled_agent_not_recovered(self):  # 取消的Agent不恢复
    async def test_memory_to_sqlite_migration(self):  # 内存数据→SQLite迁移正确
```

---

### P2-4 role_learner（角色学习引擎）— 3天

**来源**：role_learner.md → system-flow.md §4（完整自学流程6步）→ coevolution.md §3.1（Skill进化事件链）

**前置依赖**：memory_service（P2-2）、llm_gateway
**被依赖**：upgrade_manager（P2-5）

**新增文件**：
```
plugins/role_learner/
├── __init__.py              # from .plugin import RoleLearnerPlugin
├── manifest.json            # type: capability, dependencies: [memory_service, llm_gateway]
├── plugin.py                # 主实现（~350行）
├── learner.py               # 采样+分析逻辑（~200行）
└── tests/
    └── test_plugin.py       # 10个测试用例
```

**`plugin.py` 实现细节**（完全对齐 system-flow.md §4）：

```python
class RoleLearnerPlugin(PluginInterface):
    """角色自学习引擎。异步执行，不阻塞主流程。"""
    
    # 订阅：
    #   task.completed → 触发异步学习
    #   role.learn_requested → 手动触发指定角色学习
    # 发布：
    #   role.insight_generated → 新洞察已生成
    #   role.skill_suggested → 检测到新技能模式
    
    async def _on_task_completed(self, event: Event):
        """任务完成 → 触发异步学习。
        
        Payload:
        - role_id: str（学习的角色）
        - task_id: str（刚完成的任务）
        
        流程（system-flow.md §4）：
        1. 读取角色最近7天 experiences（从memory_service）
        2. 调LLM分析（使用最便宜模型）：
           a. success_pattern — 成功模式
           b. improvement — 改进方向
           c. pitfall — 常见陷阱
           d. preference — 偏好
        3. 保存洞察到角色记忆（memory_service.add_insight()）
        4. 检测技能模式：同一工具组合出现≥3次 → 潜在技能
        5. 如发现新技能模式 → 发布 role.skill_suggested
        """
    
    # --- 采样策略（learner.py）---
    # 非全量分析（减少LLM成本）：
    # - 最近24小时：100%采样
    # - 24h~7天：10%采样
    # - >7天：不采样（但可手动触发）
    # - 每次最多分析20条经验
```

**测试（10个用例）**：
```python
class TestRoleLearner:
    async def test_task_completed_triggers_learning(self):  # task.completed → 学习
    async def test_insight_generated_and_stored(self):  # 洞察生成→存入memory
    async def test_skill_pattern_detected(self):  # 3次重复 → 技能建议
    async def test_skill_pattern_below_threshold(self):  # 2次 → 不触发
    async def test_manual_learn_request(self):  # 手动触发学习
    async def test_empty_experiences_no_crash(self):  # 无经验→不处理
    async def test_concurrent_learn_no_duplicate(self):  # 并发学习不重复
    async def test_analysis_with_cheapest_model(self):  # 使用最便宜模型
    async def test_error_in_learning_not_crash(self):  # LLM失败→记录error不崩溃
    async def test_insight_capped_at_2000_chars(self):  # 洞察字符限制
```

---

### P2-5 upgrade_manager（升级管理）— 3天

**来源**：upgrade_manager.md → system-flow.md §9（自优化上报流完整链路）→ coevolution.md §6（版本管理策略）→ hot-reload.md §6（自修改流程+用户确认闭环）

**前置依赖**：memory_service（P2-2）、role_learner（P2-4）
**被依赖**：所有支持自修改的插件

**新增文件**：
```
plugins/upgrade_manager/
├── __init__.py              # from .plugin import UpgradeManagerPlugin
├── manifest.json            # type: capability
├── plugin.py                # 主实现（~400行）
├── store.py                 # SQLite持久化（~80行）
└── tests/
    └── test_plugin.py       # 10个测试用例
```

**`plugin.py` 实现细节**（完全对齐 system-flow.md §9 自优化上报流）：

```python
class UpgradeManagerPlugin(PluginInterface):
    """升级管理。管理所有自修改请求的生命周期。"""
    
    # 订阅：
    #   plugin.upgrade_proposed → 接收升级提案
    #   upgrade.user_decision → 接收用户决策（确认/拒绝/延期）
    #   
    # 发布：
    #   upgrade.report_created → 报告已创建
    #   upgrade.status_changed → 状态变更通知
    #   upgrade.rollback_initiated → 回滚已触发
    
    # 升级报告状态机（system-flow.md §9）：
    # PENDING → SUBMITTED → APPROVED → IMPLEMENTED
    #                     → REJECTED
    #                     → DEFERRED → APPROVED → IMPLEMENTED
    #                                         → REJECTED
    # IMPLEMENTED → VERIFIED → 完成
    #             → VERIFICATION_FAILED → ROLLING_BACK → ROLLED_BACK
    
    async def _on_upgrade_proposed(self, event: Event):
        """接收升级提案。
        
        1. 创建 UpgradeReport（含变更内容、影响范围、回滚策略、风险评估）
        2. 设置状态为 SUBMITTED
        3. 通知 suri 汇总给用户
        """
    
    async def execute_upgrade(self, report_id: str):
        """执行升级（用户确认后）。
        
        1. 创建备份（代码备份到 ~/.suri/backup/{timestamp}/）
        2. 应用变更（插件代码/配置/数据）
        3. 运行验证（健康检查 + 基本功能测试）
        4. 成功 → IMPLEMENTED
        5. 失败 → ROLLING_BACK
        """
    
    async def rollback(self, report_id: str):
        """回滚到上个版本。
        
        1. 从备份恢复文件
        2. 重新加载插件
        3. 验证恢复成功
        """
    
    def generate_upgrade_report(self, proposal: Dict) -> UpgradeReport:
        """生成完整升级报告（hot-reload.md §6.2）。
        
        包含：
        - 变更原因
        - 具体变更内容（diff格式）
        - 影响范围（哪些插件/角色受影响）
        - 回滚策略（具体步骤）
        - 风险评估（低/中/高）
        - 建议执行时间（低谷/立即）
        """
```

**SQLite 表**（database.md 定义）：
```sql
CREATE TABLE IF NOT EXISTS upgrade_reports (
    report_id TEXT PRIMARY KEY,
    plugin_id TEXT NOT NULL,
    current_version TEXT NOT NULL,
    target_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    reason TEXT NOT NULL,
    changes TEXT NOT NULL,        -- JSON: 变更内容
    impact_analysis TEXT,         -- JSON: 影响分析
    rollback_plan TEXT NOT NULL,  -- JSON: 回滚策略
    risk_level TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    user_decision TEXT,            -- approved / rejected / deferred
    user_decision_at TEXT,
    implemented_at TEXT,
    verified_at TEXT
);
```

**测试（10个用例）**：
```python
class TestUpgradeManager:
    async def test_proposal_creates_report(self):  # 提案→报告
    async def test_full_lifecycle(self):  # PENDING→SUBMITTED→APPROVED→IMPLEMENTED→VERIFIED
    async def test_rejected_workflow(self):  # 用户拒绝→REJECTED
    async def test_deferred_then_approved(self):  # 延期→批准
    async def test_rollback_on_failure(self):  # 执行失败→回滚成功
    async def test_report_persistence(self):  # 重启后报告可查
    async def test_rollback_restores_backup(self):  # 回滚恢复备份文件
    async def test_concurrent_upgrades_blocked(self):  # 同一插件不能并发升级
    async def test_invalid_proposal_rejected(self):  # 缺回滚策略→拒绝
    async def test_risk_high_requires_admin(self):  # 高风险→需管理员确认
```

---

### P2-6 mcp_framework（MCP工具框架）— 3天

**来源**：mcp_framework.md + mcp_protocol.md → architecture.md §4.4 → coevolution.md §3.4（Tool进化事件链）

**前置依赖**：无
**被依赖**：code_tool（部分工具注册）

**新增文件**：
```
plugins/mcp_framework/
├── __init__.py              # from .plugin import MCPFrameworkPlugin
├── manifest.json            # type: capability
├── plugin.py                # 主实现（~300行）
├── registry.py              # 工具注册表 SQLite持久化（~120行）
├── services/                # 内置工具服务
│   ├── __init__.py
│   ├── filesystem.py        # 文件操作工具（与code_tool协作）
│   └── shell_exec.py        # 命令执行工具
└── tests/
    └── test_plugin.py       # 10个测试用例
```

**`plugin.py` 实现细节**：

```python
class MCPFrameworkPlugin(PluginInterface):
    """MCP工具框架。管理所有工具的注册、发现、调用、废弃。"""
    
    # 订阅：
    #   tool.call → 执行工具调用
    #   tool.register → 注册新工具
    #   tool.discover → 查询可用工具
    # 发布：
    #   tool.result → 工具执行结果
    #   tool.registered → 新工具已注册
    #   tool.deprecated → 工具已废弃
    
    async def _on_tool_call(self, event: Event):
        """执行工具调用。
        
        Payload:
        - tool_name: str
        - arguments: dict
        - call_id: str（用于匹配结果）
        
        流程：
        1. 从注册表查找工具
        2. 参数校验
        3. 执行（直接调用的service方法）
        4. 发布 tool.result
        5. 记录调用日志
        """
    
    async def register_tool(self, name: str, description: str, 
                            params_schema: dict, handler: Callable):
        """注册工具到注册表。
        
        注册信息持久化到SQLite，重启后可恢复。
        """
```

**SQLite 表**：
```sql
CREATE TABLE IF NOT EXISTS tools (
    tool_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    params_schema TEXT NOT NULL,  -- JSON
    handler_plugin TEXT NOT NULL,  -- 处理该工具的插件
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',  -- active / deprecated / removed
    created_at TEXT NOT NULL,
    deprecated_at TEXT
);
```

**测试（10个用例）**：
```python
class TestMCPFramework:
    async def test_register_and_discover(self):  # 注册→发现
    async def test_call_tool(self):  # 调用工具→返回结果
    async def test_call_missing_tool(self):  # 调用不存在的工具→错误
    async def test_deprecate_tool(self):  # 废弃工具不再可发现
    async def test_parameter_validation(self):  # 参数校验
    async def test_concurrent_calls(self):  # 并发调用
    async def test_tool_persistence(self):  # 重启后注册不丢失
    async def test_register_duplicate_name(self):  # 同名工具→拒绝
    async def test_tool_result_logging(self):  # 调用结果被记录
    async def test_services_initialized(self):  # 内置filesystem/shell_exec可用
```

**与code_tool的边界**（coevolution.md §3.4明确规定）：
- code_tool：文件读写、搜索、统计等编辑器类操作（确定性、同步）
- mcp_framework：外部工具（MCP协议、API调用、数据库查询等，可能有副作用）

---

### P2-7 cron_service（定时任务）— 1天

**来源**：plugins/README.md → directory-structure.md 扩展层

**新增文件**：
```
plugins/cron_service/
├── __init__.py              # from .plugin import CronServicePlugin
├── manifest.json            # type: extension, dependencies: []
├── plugin.py                # 主实现（~150行）
└── tests/
    └── test_plugin.py       # 5个测试用例
```

**实现**：
```python
class CronServicePlugin(PluginInterface):
    crontab: Dict[str, List[CronJob]]  # 按分钟分桶
    
    # 订阅：
    #   cron.register → 注册定时任务
    # 发布：
    #   cron.{name} → 按定义的cron表达式定时触发
    
    async def _on_register(self, event: Event):
        """注册定时任务。
        
        Payload:
        - name: str
        - cron_expr: str（5字段标准cron）
        - event_type: str（触发时发布的事件名）
        - payload: dict（触发时携带的数据）
        """
```

---

### P2-8 hooks_service（事件钩子）— 1天

**来源**：plugins/README.md → hot-reload.md §3.2（模板热更新钩子）

**新增文件**：
```
plugins/hooks_service/
├── __init__.py              # from .plugin import HooksServicePlugin
├── manifest.json            # type: extension
├── plugin.py                # 主实现（~150行）
└── tests/
    └── test_plugin.py       # 5个测试用例
```

**实现**：
```python
class HooksServicePlugin(PluginInterface):
    # 订阅：
    #   hook.register → 注册文件变更钩子
    # 发布：
    #   hook.file_changed → 目标文件变更时触发
    
    async def _on_register(self, event: Event):
        """注册文件变更钩子。
        
        Payload:
        - path: str（监控的文件路径，支持glob）
        - event_type: str（文件变更时发布的事件）
        - recursive: bool（是否递归子目录，默认False）
        """
    
    async def _watch_loop(self):
        """后台观察循环。
        
        使用 watchdog 或 poll 方式检测文件变更。
        变更后发布注册时指定的事件。
        """
```

---

### P2-9 doc_sync（文档同步）— 1天

**来源**：plugins/README.md

**新增文件**：
```
plugins/doc_sync/
├── __init__.py              # from .plugin import DocSyncPlugin
├── manifest.json            # type: extension
├── plugin.py                # 主实现（~150行）
└── tests/
    └── test_plugin.py       # 5个测试用例
```

**实现**：
```python
class DocSyncPlugin(PluginInterface):
    # 订阅：
    #   doc_sync.code_changed → 代码变更
    # 发布：
    #   doc_sync.update_suggested → 文档更新建议
    
    async def _on_code_changed(self, event: Event):
        """监控代码变更，生成文档更新建议。
        
        1. 检测变更文件是否与PRD文档相关
        2. 如果相关 → 发布 doc_sync.update_suggested
        3. suri/角色评估后决定是否更新PRD
        """
    
    async def backup_prd(self):
        """修改前备份PRD文档。"""
```

### P2-10 monitor（系统监控）— 1天

**来源**：architecture.md §4.6 → directory-structure.md

**新增文件**：
```
plugins/monitor/
├── __init__.py              # from .plugin import MonitorPlugin
├── manifest.json            # type: extension, dependencies: [log_service]
├── plugin.py                # 主实现（~120行）
└── tests/
    └── test_plugin.py       # 3个测试用例
```

**实现**：
```python
class MonitorPlugin(PluginInterface):
    # 订阅：
    #   error.* → 统计错误率
    #   system.heartbeat → 监控插件健康状态
    # 发布：
    #   monitor.health_report → 定期健康报告
    
    async def _on_error(self, event: Event):
        """记录错误到监控面板。"""
    
    async def _on_heartbeat(self, event: Event):
        """更新插件心跳状态。"""
```

---

## 四、P3 — 持续改进（无严格工时）

| 任务 | 来源 | 说明 |
|------|------|------|
| 补充API接口文档 | framework-rules.md §7 | 错误码完整列表 + 事件payload schema |
| 性能基准测试 | AUDIT-REPORT.md §4.1 | EventBus吞吐（目标>1000evt/s）、SQLite并发（WAL模式验证） |
| 补充运维手册 | missing | 故障恢复、数据修复、版本迁移步骤 |
| 细化权限模型 | permission-model.md | 角色-资源-操作三维权限矩阵实现 |
| 安全沙箱完善 | framework-rules.md §9 | 动态插件AST扫描 + 文件隔离 + 资源限制 |

---

## 五、依赖关系与时间线

```
                 P0-1 healthcheck ───── 2天 ────┐
                  │                              │
                 P0-2 拓扑排序 ── 0.5天 ─────────┤
                  │                              │
                 P0-3 事件对齐 ── 0.5天 ─────────┤
                  │                              │
    ┌─────────────┼──────────────────────────────┤
    ▼             ▼                              │
P1-1 code_tool  P1-3 优雅关闭                    │
幂等写入(1天)    持久化(1.5天)                    │
    │             │                              │
    ▼             ▼                              │
P1-2 数据外部化(1.5天)──P1-4 文档去重(1天)──P1-5 引用修复(1天)──
    │                                                    │
    └──────────────────┬─────────────────────────────────┘
                       ▼
          ═══════ P2 开始 ═══════
                       │
                       ▼
                 P2-1 role_comm(3天)
                  │            │
                  ▼            ▼
              P2-2 mem_svc   P2-3 agent_registry
               (3天)         持久化(1天)
                  │            │
                  └──────┬─────┘
                         ▼
                   P2-4 role_learner(3天)
                         │
                         ▼
                   P2-5 upgrade_manager(3天)
                         │
                         ▼
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    P2-6 mcp_fw     P2-7 cron       P2-8 hooks
     (3天)           (1天)           (1天)
                                  │
                                  ▼
                             P2-9 doc_sync
                              (1天)
                                  │
                                  ▼
                             P2-10 monitor
                              (1天)
                                  │
                                  ▼
                            ═══════ P3 ═══════
```

### 关键路径（阻塞高风险）
```
P0-1 → P1-1 → P1-2 → P2-1 → P2-2 → P2-4 → P2-5 → P2-6
```

### 可并行组
- **组A**：P0-1 + P0-2 + P0-3（3个P0可并行，都是suri_core层）
- **组B**：P1-3 + P1-4 + P1-5（无代码依赖）
- **组C**：P2-1 + P2-2 + P2-3（均可与P2并行）
- **组D**：P2-7 + P2-8 + P2-9 + P2-10（扩展层无内部依赖）

---

## 六、每次迭代验收

### 验收命令

```bash
# 1. 运行全部测试
python -m pytest tests/ -v --tb=short
# 预期：全部通过，无新增失败

# 2. 事件命名一致性检查
grep -rn "system\.start[^e]" --include="*.py" --include="*.md" . | 
  grep -v "system\.started" | grep -v "\.git" | grep -v "AUDIT-REPORT"
# 预期：空输出

# 3. 角色数据路径一致性
grep -rn "runtime/roles" --include="*.md" . | grep -v "\.git" 
# 预期：空输出（全部使用 roles/）

# 4. 无硬编码检查（检查是否还有6个P1-2的硬编码残留）
grep -rn "SOUL_TEMPLATE\|_load_builtin_templates" \
  --include="*.py" plugins/ | grep -v "\.pyc"
# 预期：空输出

# 5. 代码可导入
python -c "from agent_framework.core.suri_core.plugin import SuriCorePlugin; print('OK')"
# 预期：OK

# 6. 文档引用检查（所有 .md 交叉引用有效）
python -c "
import re
import os
for root, dirs, files in os.walk('prd'):
    for f in files:
        if f.endswith('.md'):
            with open(os.path.join(root, f)) as fp:
                for i, line in enumerate(fp, 1):
                    for m in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', line):
                        ref = m.group(2)
                        if not os.path.exists(os.path.join(root, ref)):
                            print(f'{root}/{f}:{i}: broken ref: {ref}')
print('Done')
"
# 预期：无输出（全部有效）