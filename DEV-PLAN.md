# Suri-Agent 可执行开发计划

> **依据**：全部 37 份 PRD 文档交叉审计结果
> **文档交叉引用**：每项任务标注了来源文档的精确章节
> **底库状态**：12/20 插件已实现（含核心框架618行），8个缺失
> **仓库结构**：`plugins/` 已合并到 `agent_framework/plugins/`（统一管理）
> **总工时**：~28 开发日（P0 2天 + P1 9天 + P2 19天）

---

## 零、仓库结构

```
suri-agent/
├── agent_framework/              # ⭐ 全部核心代码 + 插件（统一管理）
│   ├── __init__.py
│   ├── README.md
│   ├── core/                     # 内核 - 自举注册的 SuriCorePlugin
│   │   └── suri_core/
│   │       ├── __init__.py
│   │       ├── plugin.py         # EventBus + PluginManager 的协调者
│   │       └── manifest.json
│   ├── event_bus/                # EventBus 实现（独立模块，被 suri_core 使用）
│   │   ├── __init__.py
│   │   └── bus.py
│   ├── plugin_manager/           # PluginManager 实现（独立模块，被 suri_core 使用）
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── plugins/                  # ⭐ 全部 20 个插件
│   │   ├── README.md
│   │   ├── access/               # 接入层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   ├── plugin.py
│   │   │   ├── cli.py
│   │   │   ├── telegram.py
│   │   │   ├── telegram_bot.py
│   │   │   ├── wizard.py
│   │   │   ├── config_editor.py
│   │   │   ├── formatter.py
│   │   │   └── base.py
│   │   ├── agent_registry/       # 执行层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── code_tool/            # 执行层 - 安全文件读写
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   ├── plugin.py
│   │   │   ├── reader.py
│   │   │   ├── writer.py
│   │   │   ├── explorer.py
│   │   │   ├── search.py
│   │   │   └── stats.py
│   │   ├── config_service/       # 基础服务层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── cron_service/         # 扩展层 [预留]
│   │   ├── doc_sync/             # 扩展层 [预留]
│   │   ├── hooks_service/        # 扩展层 [预留]
│   │   ├── interrupt_handler/    # 执行层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── llm_gateway/          # 能力层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── log_service/          # 基础服务层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── mcp_framework/        # 能力层 [预留]
│   │   ├── memory_service/       # 能力层 [预留]
│   │   ├── monitor/              # 扩展层 [预留]
│   │   ├── role_comm/            # 执行层 [预留]
│   │   ├── role_learner/         # 能力层 [预留]
│   │   ├── role_manager/         # 能力层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   ├── plugin.py
│   │   │   └── soul_parser.py
│   │   ├── security_service/     # 基础服务层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── task_planner/         # 执行层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── task_scheduler/       # 执行层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   ├── test_framework/       # 扩展层
│   │   │   ├── __init__.py
│   │   │   ├── manifest.json
│   │   │   └── plugin.py
│   │   └── upgrade_manager/      # 能力层 [预留]
│   ├── shared/                   # ⭐ 公共层（接口定义、工具函数、事件类型）
│   │   ├── __init__.py
│   │   ├── interfaces/
│   │   │   ├── __init__.py
│   │   │   └── plugin.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── event_types.py
│   └── migrations/               # 数据库迁移脚本
│       ├── 001_initial.sql
│       └── 002_agents.sql
├── main.py                       # 入口（<20行）
├── roles/                        # 角色数据（Git管理）
├── tests/                        # 测试代码
│   ├── __init__.py
│   ├── framework/
│   │   ├── __init__.py
│   │   └── base.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_event_bus.py
│   │   ├── test_plugin_manager.py
│   │   └── test_code_tool_modules.py
│   ├── integration/
│   │   └── __init__.py
│   └── plugin/
│       ├── __init__.py
│       ├── test_access.py
│       ├── test_access_events.py
│       ├── test_agent_registry.py
│       ├── test_code_tool.py
│       ├── test_code_tool_events.py
│       ├── test_interrupt_handler.py
│       ├── test_llm_gateway.py
│       ├── test_role_manager.py
│       └── test_security_service.py
├── prd/                          # 产品文档
├── AUDIT-REPORT.md               # PRD审计报告
└── DEV-PLAN.md                   # 本文件
```

---

## 一、开发规则总纲

### 1.1 不可违反的架构约束（来源于 PRD）

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
| **C9** | **插件统一在 `agent_framework/plugins/` 下管理** | directory-structure.md (本次重构) | 路径混乱无法同步 |

### 1.2 核心流程序列

```
启动（startup.md §2-4）
  → 系统就绪，发布 system.started
  → 等待 user.input
    → suri分析需求 → 创建角色/分配任务
      → 单角色执行
        → 步骤受阻 → 异常处理
        → 步骤完成 → 角色学习
      → suri升级自身
      → 多角色协作
```

### 1.3 插件分层加载顺序

```
Layer 0:  core/suri_core（main.py自举）
Layer 1:  基础服务层（config → log → security）
Layer 2:  执行层（task_scheduler → task_planner → agent_registry → role_comm → interrupt_handler → code_tool）
Layer 3:  能力层（llm_gateway → memory_service → role_manager → role_learner → mcp_framework → upgrade_manager）
Layer 4:  接入层（access）
Layer 5:  扩展层（cron_service → hooks_service → test_framework → doc_sync → monitor）
```

### 1.4 已实现 vs 缺失清单

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
| ❌ | role_comm | 0行 | ✗ | 无 |
| ❌ | memory_service | 0行 | ✗ | 无 |
| ❌ | role_learner | 0行 | ✗ | llm_gateway |
| ❌ | upgrade_manager | 0行 | ✗ | 无 |
| ❌ | mcp_framework | 0行 | ✗ | 无 |
| ❌ | cron_service | 0行 | ✗ | 无 |
| ❌ | hooks_service | 0行 | ✗ | 无 |
| ❌ | doc_sync | 0行 | ✗ | 无 |
| ❌ | monitor | 0行 | ✗ | log_service |

---

## 二、P0 — 紧急修复（2天，与P1并行）

### P0-1 启动自检（healthcheck）— 1天

**来源**：startup.md §4 → suri_core.md §3 → 代码缺失

**文件修改**：
```
agent_framework/core/suri_core/plugin.py
├── `bootstrap()` 第4步（加载插件后）插入 `await self._healthcheck()`
├── `_healthcheck()` — 调用6项子检查
│   ├── `_check_environment()` → ~/.suri/runtime/ 可读写、roles/suri/ 完整性
│   ├── `_check_database()` → SQLite验证迁移已执行
│   ├── `_check_config()` → config.json存在 + LLM配置
│   ├── `_check_role()` → soul.md + meta.json
│   ├── `_check_plugins()` → 核心12个插件已加载
│   └── `_check_system()` → 磁盘>100MB + 内存>50MB
└── 失败策略：警告→warning继续，错误→error标记降级
```

**测试文件**：`tests/unit/test_suri_core_healthcheck.py`
```python
class TestHealthCheck:
    async def test_healthcheck_passes_on_first_run(self)
    async def test_healthcheck_reports_missing_soul(self)
    async def test_healthcheck_reports_db_missing_table(self)
    async def test_healthcheck_reports_config_missing(self)
    async def test_system_started_only_after_healthcheck(self)
```

---

### P0-2 PluginManager 依赖拓扑排序 — 0.5天

**来源**：startup.md §3 → suri_core.md:55 → plugin-development.md §12.1

**文件修改**：
```
agent_framework/plugin_manager/manager.py
├── `load_all()` 改为拓扑排序加载
│   ├── 构建有向图 → 入度=0入队列 → 逐个加载 → 更新下游入度
│   └── 循环检测：加载数<总数 → error.plugin
├── `_load_single(plugin_dir)` — 单插件加载（AST扫描+依赖检查+启动）
└── 新增 `PluginDependencyCycleError` 异常
```

**测试**：`tests/unit/test_plugin_manager.py`（追加6个测试用例）

---

### P0-3 事件注册表与event_types.py对齐 — 0.5天

**来源**：coevolution.md §7 → event-registry.md → shared/event_types.py

**文件修改**：
```
agent_framework/shared/utils/event_types.py
├── 补全 upgrade.*(6)、interrupt.*(2)、doc_sync.* 事件族
└── EventType 枚举值 == 字符串事件名

prd/schema/event-registry.md
├── 补充每个事件的 Payload Schema
└── 与 event_types.py 完全对齐
```

---

## 三、P1 — 基础强化（7天）

### P1-1 code_tool 追加 `create_file` + 幂等写入 — 1天

**文件修改**：
```
agent_framework/plugins/code_tool/writer.py
├── `write_file()` → 临时隔离空间 + os.rename 原子操作 + fsync
├── `append_file()` → 幂等校验（最后N行hash匹配则跳过）
└── `create_file()` → 仅文件不存在时创建
```

**测试**：`tests/plugin/test_code_tool.py`（追加5个用例）

---

### P1-2 数据外部化（去硬编码）— 1.5天

**来源**：hot-reload.md §2.1（6项）

**文件修改**（3个插件文件，6个外部化点）：
```
agent_framework/plugins/role_manager/plugin.py
  │   ├── SOUL_TEMPLATE → ~/.suri/data/templates/soul_template.md
  │   ├── 工具调用说明 → ~/.suri/data/templates/tool_descriptions.yaml
  │   └── suri_fallback → ~/.suri/data/templates/suri_fallback.md
agent_framework/plugins/task_planner/plugin.py
  │   └── 内置模板 → ~/.suri/data/templates/task_templates.yaml
agent_framework/plugins/interrupt_handler/plugin.py
  │   └── 关键词 → ~/.suri/data/configs/interrupt_keywords.yaml
agent_framework/plugins/access/plugin.py
  │   └── 通道路由 → ~/.suri/data/configs/channel_routes.yaml
```

---

### P1-3 优雅关闭 + 数据持久化 — 1.5天

**来源**：program-flow.md §5 → suri_core.md §3

**文件修改**：
```
agent_framework/core/suri_core/plugin.py — stop()增强8步骤
agent_framework/plugin_manager/manager.py — unload_all(reverse=True)
agent_framework/plugins/log_service/plugin.py — archive_session()
```

---

### P1-4 消除文档重复 — 1天

**来源**：AUDIT-REPORT.md §3.1

```
startup.md ← 保留启动唯一权威
program-flow.md §1 → 改为引用 startup.md
architecture.md §2 → 改为引用 framework-rules.md §二
```

---

### P1-5 修复文档交叉引用 — 1天

```bash
grep -rn "prd/" --include="*.md" . | grep -E "\[.*\]\(.*\)"
# 修复所有失效路径
```

---

## 四、P2 — 缺失插件实现（19天）

### P2-1 role_comm（角色通信）— 3天

**新增**：`agent_framework/plugins/role_comm/`

```python
# 订阅：role.message, role.messages_query, role.messages_consume, role.messages_summary
# 发布：role.message_received, role.messages_result, role.messages_consumed, role.messages_summary_result
```

**SQLite** → `migrations/003_role_comm.sql`

**测试**：10个用例

---

### P2-2 memory_service（记忆存储）— 3天

**新增**：`agent_framework/plugins/memory_service/`

- 每个角色独立 `roles/{role_id}/memories/role.db`
- 角色隔离：路径注入防护
- WAL模式并发读写

**测试**：12个用例

---

### P2-3 agent_registry SQLite 持久化 — 1天

**修改**：`agent_framework/plugins/agent_registry/plugin.py`
- 内存 → SQLite 双轨
- 启动时恢复活跃Agent

---

### P2-4 role_learner（角色学习引擎）— 3天

**新增**：`agent_framework/plugins/role_learner/`

完全对齐 system-flow.md §4：
1. task.completed → 读7天experiences → LLM分析 → 保存洞察 → 检测技能模式
2. 采样策略：24h内100%，24h~7d 10%，每次≤20条

**测试**：10个用例

---

### P2-5 upgrade_manager（升级管理）— 3天

**新增**：`agent_framework/plugins/upgrade_manager/`

状态机（system-flow.md §9）：
```
PENDING → SUBMITTED → APPROVED → IMPLEMENTED → VERIFIED
                     → REJECTED / DEFERRED
```

**测试**：10个用例

---

### P2-6 mcp_framework（MCP工具框架）— 3天

**新增**：`agent_framework/plugins/mcp_framework/`

工具注册/发现/调用/废弃完整链路，与code_tool边界明确：
- code_tool：文件读写（确定性、同步）
- mcp_framework：外部协议/有副作用操作

**测试**：10个用例

---

### P2-7~P2-10 扩展层插件 — 每项1天

| 插件 | 路径 | 核心逻辑 |
|------|------|---------|
| cron_service | `agent_framework/plugins/cron_service/` | 5字段cron定时触发 |
| hooks_service | `agent_framework/plugins/hooks_service/` | 文件变更监听+事件发布 |
| doc_sync | `agent_framework/plugins/doc_sync/` | 代码变更→文档更新建议 |
| monitor | `agent_framework/plugins/monitor/` | 错误率统计+健康报告 |

---

## 五、依赖关系与时间线

```
P0-1 healthcheck ─↓ P1-1 code_tool幂等 ─↓ P1-2 数据外部化 ─↓
P0-2 拓扑排序 ────┘                                            
P0-3 事件对齐 ────────────────────── P1-3优雅关闭 ── P1-4文档去重 ── P1-5引用修复
                                                                 │
                                                                 ▼
                                                            ═════ P2 ═════
                                                                 │
                                                            P2-1 role_comm(3d)
                                                             │         │
                                                         P2-2 mem    P2-3 agent
                                                          (3d)       (1d)
                                                             └──┬───┘
                                                                │
                                                            P2-4 learner(3d)
                                                                │
                                                            P2-5 upgrade(3d)
                                                                │
                                                  ┌─────────────┼─────────┐
                                                  ▼             ▼         ▼
                                             P2-6 mcp(3d)  P2-7 cron  P2-8 hooks
                                                                       │
                                                                    P2-9 doc_sync
                                                                       │
                                                                    P2-10 monitor
```

### 关键路径（阻塞高风险）
```
P0-1 → P1-1 → P1-2 → P2-1 → P2-2 → P2-4 → P2-5 → P2-6
```

### 可并行组
- **组A**：P0-1 + P0-2 + P0-3
- **组B**：P1-3 + P1-4 + P1-5
- **组C**：P2-2 + P2-3（依赖P2-1但不互相依赖）
- **组D**：P2-7~P2-10（扩展层无内部依赖）

---

## 六、每次迭代验收

```bash
# 1. 运行全部测试
python -m pytest tests/ -v --tb=short

# 2. 事件命名一致性
grep -rn "system\.start[^e]" --include="*.py" --include="*.md" . | 
  grep -v "system\.started" | grep -v "\.git"
# 预期：空输出

# 3. 角色数据路径
grep -rn "runtime/roles" --include="*.md" . | grep -v "\.git"
# 预期：空输出

# 4. 无硬编码
grep -rn "SOUL_TEMPLATE\|_load_builtin_templates" --include="*.py" . | grep -v "\.pyc"
# 预期：空输出

# 5. 代码可导入
python -c "from agent_framework.core.suri_core.plugin import SuriCorePlugin; print('OK')"

# 6. 文档引用检查
python -c "
import re, os
for root, dirs, files in os.walk('prd'):
    for f in files:
        if f.endswith('.md'):
            with open(os.path.join(root, f)) as fp:
                for i, line in enumerate(fp, 1):
                    for m in re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', line):
                        ref = m.group(2)
                        if not os.path.exists(os.path.join(root, ref)):
                            print(f'{root}/{f}:{i}: broken ref: {ref}')
"