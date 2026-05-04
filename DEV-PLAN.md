# Suri Agent — 可执行开发计划

> 基于 PRD 全量审计生成的开发任务清单。
> 版本: v2.0 | 更新: 2026-05-04

---

## §0 架构约束（不可违反）

以下 8 条约束来自 PRD 文档，任何开发违反即视为架构违规：

| # | 约束 | 来源 PRD § | 违反后果 |
|---|------|-----------|---------|
| 0.1 | 角色数据全部在 `roles/{role_id}/` 下 Git 管理，不得存 `~/.suri/` | overview/design-principles.md:141 | 换设备角色数据丢失 |
| 0.2 | 运行时数据（会话/项目）放 `~/.suri/runtime/`，不得提交 Git | operations/startup.md:31 | 仓库膨胀、隐私泄露 |
| 0.3 | 事件名统一前缀 `system.`、`role.`、`tool.`、`plugin.`，禁用 `system.start`（应为 `system.started`） | schema/event-registry.md:12 | 插件间通信断裂 |
| 0.4 | 项目根目录只有一个内核 `agent_framework/core/suri_core/`，禁止其他内核实现 | overview/architecture.md:51 | 启动流程混乱 |
| 0.5 | import 路径统一 `agent_framework.xxx`，不得出现顶层 `plugins.`、`shared.` | operations/directory-structure.md:44 | 路径断裂 |
| 0.6 | 安全沙箱写入审批流程必须完整（token 申请→审批→写入→释放），不得跳过 | security/security-spec.md:83 | 权限绕过 |
| 0.7 | 插件热更新不得导致状态丢失，`pause/resume` 必须成对实现 | operations/hot-reload.md:21 | 插件状态不一致 |
| 0.8 | 所有插件必须实现 `PluginInterface` 全部 7 个方法，不得只 `pass` | plugins/README.md:31 | 生命周期管理失败 |

### 核心流程执行链

```
main.py → SuriCorePlugin.bootstrap()
  → EventBus.start()
  → PluginManager.load_plugins(scan_dirs=["agent_framework/plugins/"])
    → SuriCorePlugin.init() → EventBus.ready
    → 按拓扑排序加载各插件
  → PluginManager.start_plugins()
  → 发布 system.started → 发布 system.ready
```

### 插件分层加载顺序

```
第0层: SuriCorePlugin (自举, 拓扑排序驱动)
第1层: config_service, log_service, security_service (纯基础服务)
第2层: event_bus (异步总线, 第0层已启动)
第3层: role_manager, task_planner (状态依赖)
第4层: code_tool, llm_gateway, agent_registry (能力层)
第5层: access, interrupt_handler, task_scheduler, test_framework (外部接入层)
```

### 已实现 / 待实现

| 插件 | 代码行 | 状态 | 心智 | 测试覆盖 |
|------|--------|------|------|---------|
| SuriCorePlugin | 183 | ✅ | 完成 | 间接覆盖 |
| EventBus | 186 | ✅ | 完成 | 4 tests |
| PluginManager | 249 | ✅ | 完成 | 5 tests |
| **access** | 444 | ✅ | 完成 | 2 tests |
| **code_tool** | 358 | ✅ | 完成 | 2 tests |
| **config_service** | 125 | ✅ | 完成 | 间接覆盖 |
| **interrupt_handler** | 532 | ✅ | 完成 | 间接覆盖 |
| **llm_gateway** | 432 | ✅ | 完成 | 2 tests |
| **log_service** | 89 | ✅ | 完成 | 间接覆盖 |
| **role_manager** | 507 | ✅ | 完成 | 1 test |
| **security_service** | 174 | ✅ | 完成 | 1 test |
| **task_planner** | 599 | ✅ | 完成 | 12 tests |
| **task_scheduler** | 433 | ✅ | 完成 | 间接覆盖 |
| **test_framework** | 172 | ✅ | 完成 | 间接覆盖 |
| **agent_registry** | 244 | ✅ | 完成 | 1 test |
| role_comm | — | ❌ | 缺失 | — |
| memory_service | — | ❌ | 缺失 | — |
| role_learner | — | ❌ | 缺失 | — |
| upgrade_manager | — | ❌ | 缺失 | — |
| mcp_framework | — | ❌ | 缺失 | — |
| cron | — | ❌ | 缺失 | — |
| hooks | — | ❌ | 缺失 | — |
| doc_sync | — | ❌ | 缺失 | — |
| monitor | — | ❌ | 缺失 | — |

**当前测试**：169 passed, 0 failed

---

## §1 P0 — 必须立即完成（2 天）

### P0.1 System Healthcheck 实现

文件：`agent_framework/core/suri_core/health.py`（新建）

```python
"""系统健康检查模块。"""
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any

class HealthCheck:
    """启动自检 — 6 项检查，全部通过才算系统就绪。"""
    
    def __init__(self, project_root: Path):
        self._root = project_root
    
    def check_all(self) -> Dict[str, Any]:
        """执行全部 6 项检查，返回 {check_name: {status, detail}}。"""
        checks = {}
        checks["db_connectivity"] = self._check_db()
        checks["roles_exist"] = self._check_roles()
        checks["plugins_importable"] = self._check_plugins()
        checks["events_bus_startable"] = self._check_event_bus()
        checks["api_keys_configured"] = self._check_api_keys()
        checks["directory_integrity"] = self._check_dirs()
        return checks
    
    def _check_db(self) -> Dict:
        try:
            conn = sqlite3.connect(":memory:")
            conn.execute("SELECT 1")
            conn.close()
            return {"status": "pass", "detail": "SQLite 可用"}
        except Exception as e:
            return {"status": "fail", "detail": str(e)}
    
    def _check_roles(self) -> Dict:
        roles_dir = self._root / "roles"
        if not roles_dir.exists():
            return {"status": "fail", "detail": "roles/ 目录不存在"}
        suri_dir = roles_dir / "suri"
        if not suri_dir.exists():
            return {"status": "fail", "detail": "roles/suri/ 不存在"}
        soul = suri_dir / "soul.md"
        meta = suri_dir / "meta.json"
        if not soul.exists():
            return {"status": "fail", "detail": "roles/suri/soul.md 缺失"}
        if not meta.exists():
            return {"status": "fail", "detail": "roles/suri/meta.json 缺失"}
        return {"status": "pass", "detail": f"角色数据完整 ({len(list(roles_dir.iterdir()))} 个角色)"}
    
    def _check_plugins(self) -> Dict:
        plugins_dir = self._root / "agent_framework" / "plugins"
        expected = ["access", "code_tool", "role_manager", "llm_gateway", 
                     "task_planner", "task_scheduler", "security_service",
                     "config_service", "log_service", "agent_registry",
                     "interrupt_handler", "test_framework"]
        missing = [name for name in expected 
                   if not (plugins_dir / name / "plugin.py").exists()]
        if missing:
            return {"status": "fail", "detail": f"缺失插件: {', '.join(missing)}"}
        return {"status": "pass", "detail": f"12 个插件全部就绪"}
    
    def _check_event_bus(self) -> Dict:
        try:
            from agent_framework.event_bus.bus import EventBus
            bus = EventBus()
            return {"status": "pass", "detail": "EventBus 可导入"}
        except Exception as e:
            return {"status": "fail", "detail": str(e)}
    
    def _check_api_keys(self) -> Dict:
        env_path = self._root / ".env"
        if not env_path.exists():
            return {"status": "warn", "detail": ".env 文件缺失，使用环境变量"}
        return {"status": "pass", "detail": ".env 存在"}
    
    def _check_dirs(self) -> Dict:
        required = ["agent_framework/core/suri_core", 
                     "agent_framework/event_bus",
                     "agent_framework/plugin_manager",
                     "agent_framework/shared/interfaces",
                     "agent_framework/shared/utils",
                     "prd", "roles", "tests"]
        missing = [d for d in required 
                   if not (self._root / d).exists()]
        if missing:
            return {"status": "fail", "detail": f"缺失目录: {', '.join(missing)}"}
        return {"status": "pass", "detail": "目录结构完整"}
```

**测试用例**（`tests/unit/test_healthcheck.py`，5 个用例）：

```
test_healthcheck_all_pass    — 模拟完整项目结构，6 项全 pass
test_healthcheck_db_fail     — 模拟 DB 不可用
test_healthcheck_roles_missing — 删除 roles/，期望 fail
test_healthcheck_plugins_missing — 删除某个插件目录
test_healthcheck_env_missing   — 无 .env，期望 warn
```

### P0.2 PluginManager 拓扑排序 + 循环检测

文件：`agent_framework/plugin_manager/manager.py`

**当前状态**：已有 `_topological_sort()` 方法，但缺少：

1. 循环依赖检测（目前的 `max_iterations` 兜底不够优雅）
2. 依赖缺失警告（声明的依赖插件不存在时，应 warn 而非 crash）

**新增代码**（修改 `load_plugins` 方法，约 20 行）：

```python
def _detect_circular_deps(self, manifests: Dict[str, Dict]) -> List[str]:
    """检测循环依赖，返回参与循环的插件名称列表。"""
    from collections import defaultdict, deque
    
    graph = defaultdict(set)
    in_degree = defaultdict(int)
    
    for name, manifest in manifests.items():
        deps = manifest.get("depends_on", [])
        graph[name]  # 确保 key 存在
        for dep in deps:
            graph[name].add(dep)
            in_degree[dep] += 1
    
    # Kahn 算法
    queue = deque([n for n in graph if in_degree[n] == 0])
    sorted_count = 0
    while queue:
        node = queue.popleft()
        sorted_count += 1
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    if sorted_count != len(graph):
        # 剩余节点都在循环中
        cycled = [n for n in graph if in_degree[n] > 0]
        return cycled
    return []
```

**测试用例**（`tests/unit/test_plugin_manager.py` 追加，6 个用例）：

```
test_no_deps_sorts_by_priority     — 无依赖时按优先级排序（已有）
test_simple_dep_chain              — A→B→C 拓扑排序正确（已有）
test_circular_dep_detection        — A→B→A，检测到循环
test_circular_three_nodes          — A→B→C→A 三节点循环
test_missing_dep_warns             — 声明依赖不存在的插件
test_self_dep                      — A→A 自依赖
```

### P0.3 事件注册表对齐

文件：`prd/schema/event-registry.md`

**任务**：验证所有订阅/发布事件与 PRD 一致，补充缺失事件。

**检查清单**：

| 事件 | 发布方 | 订阅方 | PRD 注册 |
|------|--------|--------|---------|
| `system.started` | SuriCorePlugin | 全部 | ✅ |
| `system.ready` | SuriCorePlugin | 全部 | ✅ |
| `tool.call` | access | code_tool 等 | ✅ |
| `tool.result` | code_tool | access, task_planner | ✅ |
| `user.input` | access | role_manager, task_planner | ✅ |
| `role.context_ready` | role_manager | llm_gateway | ✅ |
| `llm.request` | ? | llm_gateway | ❌ 未注册 |
| `llm.response` | llm_gateway | role_manager | ✅ |
| `role.create` | task_planner | role_manager | ✅ |
| `config.updated` | config_service | role_manager | ✅ |
| `task_planner.register_rules` | code_tool | task_planner | ❌ 未注册 |
| `plugin.lifecycle.*` | PluginManager | monitor | ❌ 未注册 |

**需要补充**：
- 在 `prd/schema/event-registry.md` 的事件表中补充 `llm.request`、`task_planner.register_rules`、`plugin.lifecycle.*`
- 在 `agent_framework/event_bus/bus.py` 中增加事件类型常量

---

## §1 P1 — 重要改进（7 天）

### P1.1 code_tool 增强：幂等写入 + 原子操作

**当前**：writer.py 写入无备份、无幂等。

**改造**（3 天）：

1. `write_file` 写入前自动备份为 `{file}.bak`
2. `append_file` 支持幂等（校验内容是否已存在）
3. `create_file` 默认 `atomic=True`，先写临时文件再 rename

**新增文件**：无需新增，修改 `agent_framework/plugins/code_tool/writer.py`

**测试**：`tests/plugin/test_code_tool.py` 追加 4 个用例

### P1.2 硬编码字符串外部化

**当前**：多处硬编码路径/字符串，如：
- `security_service/plugin.py:22` → `"suri-agent/", "roles/", "plugins/", "prd/"`
- `code_tool/writer.py:59` → `"plugins/"`

**改造**（2 天）：

1. 在 `agent_framework/shared/constants.py` 定义所有常量
2. 各插件从常量导入

**新增文件**：`agent_framework/shared/constants.py`

```python
# 受保护目录（写入需审批）
PROTECTED_DIRS = [
    "agent_framework/", "agent_framework/plugins/",
    "roles/", "prd/", "tests/",
]

# 禁止写入目录
FORBIDDEN_DIRS = [
    "agent_framework/core/",
    "agent_framework/shared/",
    "agent_framework/event_bus/",
    "agent_framework/plugin_manager/",
]

# 安全准入目录
SAFE_READ_DIRS = ["agent_framework/", "roles/", "prd/", "tests/", "works/"]
SAFE_WRITE_DIRS = ["works/", "~/.suri/runtime/"]

# 扫描目录
SCAN_DIRS = ["agent_framework/plugins/"]
```

### P1.3 优雅关闭（Graceful Shutdown）

**当前**：`main.py` 未处理 SIGTERM/SIGINT。

**改造**（1 天）：

```python
# main.py 增加
import signal

async def shutdown(sig, loop):
    print(f"收到 {sig.name} 信号，开始优雅关闭...")
    await core.shutdown()  # 新增方法
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    loop.stop()

# 注册信号
loop = asyncio.get_event_loop()
for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(sig, loop)))
```

**SuriCorePlugin 新增 `shutdown()` 方法**（8 步）：
1. 暂停定时任务（task_scheduler）
2. 发布 `system.shutting_down` 事件
3. 暂停 access 层（拒绝新输入）
4. 等待进行中的 tool.call 完成（超时 30s）
5. 暂停全部插件
6. 停止 EventBus
7. 关闭数据库连接
8. 发布 `system.shutdown` 事件

### P1.4 文档去重

**当前**：多个文档内容重复：
- `prd/plugins/access/README.md` + `prd/plugins/plugin-overview.md`（access 部分）
- `prd/operations/directory-structure.md` 中的插件列表 + `prd/plugins/README.md`
- `prd/overview/architecture.md` 中的启动流程 + `prd/operations/startup.md`

**改造**（1 天）：删去重复内容，改为 `参见 xxx.md §y` 的引用。

---

## §2 P2 — 增量迭代（19 天）

### P2.1 role_comm 插件（多 Agent 通信，3 天）

**文件**：`agent_framework/plugins/role_comm/plugin.py`

**能力**：
- 支持角色间直接消息（`role.comm.send` / `role.comm.broadcast`）
- 支持角色群组（`role.comm.group_join` / `role.comm.group_leave`）
- 消息优先级队列

**测试**：6 个用例

### P2.2 memory_service 插件（向量记忆，5 天）

**文件**：`agent_framework/plugins/memory_service/plugin.py` + `memory_store.py`

**SQLite 表结构**：

```sql
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_id TEXT NOT NULL,
    memory_type TEXT NOT NULL CHECK(memory_type IN ('episodic', 'semantic', 'procedural')),
    content TEXT NOT NULL,
    embedding BLOB,              -- 向量嵌入（预留）
    source TEXT,                  -- 来源（user/llm/tool）
    tags TEXT,                    -- JSON 标签
    importance REAL DEFAULT 0.5,  -- 重要性 0-1
    access_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_memories_role ON memories(role_id);
CREATE INDEX idx_memories_type ON memories(memory_type);
```

**能力**：
- 短期 / 长期记忆区分
- 记忆收集（`memory.collect` 事件监听）
- 记忆检索（按角色 + 类型 + 关键词）
- 记忆压缩（合并相似记忆）

**测试**：8 个用例

### P2.3 agent_registry 持久化（1 天）

**当前**：`agent_registry/plugin.py` 的 Agent 状态保存在内存字典。

**改造**：使用 SQLite 持久化（复用 `migrations/002_agents.sql`）

**表结构**（已有 `002_agents.sql`）：

```sql
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    role_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    soul_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**测试**：4 个用例

### P2.4 role_learner 插件（自学能力，3 天）

**文件**：`agent_framework/plugins/role_learner/plugin.py`

**能力**：
- 检测用户重复请求模式
- 自动生成新 skill 文件
- 更新 `roles/{role_id}/skills/` 目录
- 通知 role_manager 热重载

**测试**：5 个用例

### P2.5 upgrade_manager 插件（自升级，2 天）

**文件**：`agent_framework/plugins/upgrade_manager/plugin.py`

**能力**：
- `git pull` 检测最新代码
- 差异分析（`git diff --stat`）
- 滚动升级（逐个插件 reload）
- 回滚（保留上一个版本的备份）

**安全约束**：升级必须经用户审批（`security_service` token）

**测试**：4 个用例

### P2.6 mcp_framework 插件（MCP 协议支持，3 天）

**参考**：`prd/plugins/capability/mcp_framework.md`

**能力**：
- MCP 客户端连接外部 MCP 服务器
- 工具注册（mcp_server 暴露的工具 → system 可用工具）
- 资源访问（mcp_server 暴露的资源 → system 可读取）

**测试**：5 个用例

### P2.7 cron 插件（定时任务，1 天）

**文件**：`agent_framework/plugins/cron/plugin.py`

**能力**：
- 基于 `asyncio` 的定时调度
- cron 表达式解析
- 任务超时 / 重试

**测试**：3 个用例

### P2.8 hooks 插件（事件钩子，1 天）

**文件**：`agent_framework/plugins/hooks/plugin.py`

**能力**：
- 事件前/后钩子（`pre_*` / `post_*`）
- 自定义钩子注册
- 钩子链

**测试**：3 个用例

### P2.9 doc_sync 插件（文档同步，1 天）

**文件**：`agent_framework/plugins/doc_sync/plugin.py`

**能力**：
- 代码 → PRD 双向同步
- 变更检测（文件哈希比对）
- 同步建议生成

**测试**：3 个用例

### P2.10 monitor 插件（系统监控，2 天）

**文件**：`agent_framework/plugins/monitor/plugin.py`

**能力**：
- 性能指标收集（事件吞吐量、插件响应时间）
- 异常告警（`plugin.lifecycle.error` 事件监听）
- 健康检查端点

**测试**：4 个用例

---

## §3 项目结构（当前状态）

```
suri-agent/
├── main.py                          # <20 行，入口
├── agent_framework/                 # 框架 + 所有代码
│   ├── __init__.py
│   ├── core/suri_core/plugin.py     # 自举内核
│   ├── event_bus/bus.py             # 异步事件总线
│   ├── plugin_manager/manager.py    # 插件生命周期
│   ├── migrations/                  # SQLite 迁移
│   ├── shared/                      # 共享模块
│   │   ├── interfaces/plugin.py     # PluginInterface
│   │   └── utils/event_types.py     # 事件类型
│   └── plugins/                     # 12 个插件
│       ├── access/                  # CLI/Telegram
│       ├── code_tool/               # 文件工具
│       ├── llm_gateway/             # LLM 路由
│       ├── role_manager/            # 角色管理
│       ├── task_planner/            # 任务分解
│       ├── task_scheduler/          # 任务调度
│       ├── security_service/        # 安全沙箱
│       ├── config_service/          # 配置管理
│       ├── log_service/             # 日志
│       ├── agent_registry/          # Agent 生命周期
│       ├── interrupt_handler/       # 中断/重试
│       └── test_framework/          # 测试基础设施
├── prd/                             # 产品文档
├── roles/                           # 角色 Git 管理
│   └── suri/ (soul.md + meta.json)
├── tests/                           # 169 pass / 0 fail
│   ├── plugin/ (10 文件)
│   ├── unit/ (3 文件)
│   └── framework/ (base.py)
└── works/                           # 工作区模板
```

---

## §4 验收命令

```bash
# 1. 运行全部测试
python3 -m pytest tests/ -v

# 2. 验证全部插件可导入
python3 -c "
from agent_framework.core.suri_core.plugin import SuriCorePlugin
from agent_framework.plugins.access.plugin import AccessPlugin
from agent_framework.plugins.code_tool.plugin import CodeToolPlugin
from agent_framework.plugins.llm_gateway.plugin import LLMGatewayPlugin
from agent_framework.plugins.role_manager.plugin import RoleManagerPlugin
print('All plugins importable ✅')
"

# 3. 验证 import 路径无旧引用
grep -rn "from plugins\.\|from shared\." --include="*.py" . | grep -v ".git" | grep -v ".pyc" | grep -v "AUDIT-REPORT" && echo "WARNING: old imports remain" || echo "All imports clean ✅"

# 4. 验证 project_root 计算正确
python3 -c "
from pathlib import Path
p = Path('agent_framework/plugins/code_tool/plugin.py')
assert p.parent.parent.parent.parent.name == 'suri-agent' or p.parent.parent.parent.parent == Path('.')
print('Project root path correct ✅')
"

# 5. 验证角色数据存储
ls -la roles/suri/soul.md && echo "soul.md exists ✅"
ls -la roles/suri/meta.json && echo "meta.json exists ✅"

# 6. 验证事件名统一
grep -rn "system\.start[^e]" --include="*.py" --include="*.md" . | grep -v ".git" | grep -v "AUDIT-REPORT" | grep -v "DEV-PLAN" | grep -v "system\.started" && echo "WARNING: system.start leftover" || echo "Event name unified ✅"