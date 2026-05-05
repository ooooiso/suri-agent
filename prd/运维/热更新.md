# 热更新基础规则

> 定义 suri-agent 中所有"新建角色、新增数据、新增文件"等操作的自动维护和热更新机制。

---

## 一、核心原则

1. **零硬编码** — 所有可变数据必须外部化到文件/数据库/配置中，禁止硬编码在 Python 代码中
2. **事件驱动热更新** — 数据变更后通过 EventBus 发布事件，相关插件自动刷新
3. **版本协商** — 插件间通过 manifest.json 声明兼容版本，启动时校验
4. **统一升级通道** — 所有运行时自修改通过 upgrade_manager 统一管理

---

## 二、数据外部化清单

### 2.1 当前硬编码问题

| # | 位置 | 硬编码内容 | 应外部化到 | 优先级 |
|---|------|-----------|-----------|--------|
| 1 | `plugins/role_manager/plugin.py` | `SOUL_TEMPLATE` 字符串 | `~/.suri/data/templates/soul_template.md` | 🔴 高 |
| 2 | `plugins/role_manager/plugin.py` | `_get_system_prompt()` 中的工具调用说明 | `~/.suri/data/templates/tool_descriptions.yaml` | 🔴 高 |
| 3 | `plugins/task_planner/plugin.py` | `_load_builtin_templates()` 中的内置模板 | `~/.suri/data/templates/task_templates.yaml` | 🔴 高 |
| 4 | `plugins/interrupt_handler/plugin.py` | `_classify_reason()` 中的关键词列表 | `~/.suri/data/configs/interrupt_keywords.yaml` | 🟡 中 |
| 5 | `plugins/access/plugin.py` | 通道路由逻辑 | `~/.suri/data/configs/channel_routes.yaml` | 🟡 中 |
| 6 | `plugins/role_manager/plugin.py` | `_create_suri()` 中的 fallback 文本 | `~/.suri/data/templates/suri_fallback.md` | 🟢 低 |

### 2.2 外部化数据目录结构

```
~/.suri/data/
├── templates/                    # 模板文件
│   ├── soul_template.md          # 角色 Soul 模板
│   ├── tool_descriptions.yaml    # 工具调用说明
│   ├── task_templates.yaml       # 任务规划模板
│   └── suri_fallback.md          # suri 角色 fallback
├── configs/                      # 配置文件
│   ├── interrupt_keywords.yaml   # 中断关键词
│   └── channel_routes.yaml       # 通道路由
└── plugins/                      # 插件数据
    └── {plugin_name}/
        └── data.yaml
```

---

## 三、热更新事件流

### 3.1 配置热更新

```
用户/角色修改配置文件
    │
    ▼
config_service 检测文件变更
    │
    ▼
config_service 发布 config.updated 事件
    │   payload: { "plugin_id": "task_planner", "config_key": "templates", ... }
    ▼
相关插件订阅 config.updated
    │
    ├── 重新加载配置
    ├── 更新内存状态
    └── 继续处理新请求（不影响正在进行的任务）
```

### 3.2 模板热更新

```
用户/角色新增任务模板
    │
    ▼
code_tool 写入 ~/.suri/data/templates/task_templates.yaml
    │
    ▼
hooks_service 检测文件变更
    │
    ▼
发布 task_planner.templates_updated 事件
    │
    ▼
task_planner 重新加载模板
    ├── 保留内置模板（不可覆盖）
    ├── 合并外部模板
    └── 更新内存索引
```

### 3.3 三清单热更新

三清单（Role Registry / Plugin Registry / Tool Registry）的变更通过广播机制热更新：

```
角色/工具/插件注册变更
    │
    ├─ 1. 变更 Registry 数据（文件/数据库持久化）
    │
    ├─ 2. 发布对应变更事件：
    │      ├── role.registered / role.updated / role.deprecated
    │      ├── plugin.registered / plugin.updated / plugin.deprecated
    │      └── tool.registered / tool.updated / tool.deprecated
    │
    ├─ 3. 广播通知所有相关订阅者：
    │      ├── suri（用户认知更新 → 用户可见通知）
    │      ├── role_manager（角色能力索引刷新）
    │      ├── agent_registry（可用角色/插件列表更新）
    │      ├── mcp_framework（工具列表刷新）
    │      └── memory_service（项目上下文索引更新）
    │
    ├─ 4. 各插件异步重新加载相关数据：
    │      ├── role_manager → 重新生成 tool_descriptions
    │      ├── agent_registry → 更新注册表快照
    │      └── mcp_framework → 更新工具路由表
    │
    └─ 5. 广播同步完成事件（triple.registry.synced）
         → log_service 记录变更日志
         → access 层通知用户
```

### 3.4 三层上下文热更新

当用户切换项目或角色时，三层上下文隔离体系热更新：

```
用户切换项目（从 project_A 到 project_B）
    │
    ├─ 1. session-hub 更新 session.isolation_layer = "project"
    │      └─ session.project_id = "project_B"
    │
    ├─ 2. memory_service 切换角色记忆库：
    │      └─ 从 ad-hoc/{role_id}.db → project_B/{role_id}.db
    │
    ├─ 3. role_manager 切换角色 context.md：
    │      └─ 加载 project_B 的 context.md
    │
    ├─ 4. wiki_service 切换知识库路径：
    │      └─ 从 /works/project_A/wiki/ → /works/project_B/wiki/
    │
    ├─ 5. 发布 project.switched 事件（带新旧 project_id）
    │
    └─ 6. 下次 LLM 调用注入新项目上下文
```

### 3.5 角色热更新

```
用户/角色创建新角色
    │
    ▼
role_manager.create_role()
    ├── 生成角色目录 ~/.suri/runtime/roles/{role_id}/
    ├── 写入 soul.md（使用外部模板）
    ├── 写入 meta.json
    └── 发布 role.created 事件
    │
    ▼
其他插件订阅 role.created
    ├── task_planner → 更新角色能力索引
    ├── agent_registry → 更新可用角色列表
    └── access → 更新角色路由
```

### 3.6 工具热更新

```
新增工具（通过 mcp_framework 或 code_tool）
    │
    ▼
工具注册到 ~/.siri/data/tools/{tool_name}.json
    │
    ▼
发布 tool.registered 事件
    │
    ▼
role_manager 更新工具调用说明
    ├── 重新生成 _get_system_prompt()
    └── 下次 LLM 请求自动包含新工具
```

---

## 四、插件版本协商

### 4.1 manifest.json 版本声明

```json
{
  "name": "task_planner",
  "version": "1.2.0",
  "min_suri_version": "1.0.0",
  "api_version": "1.0",
  "provides_interfaces": ["TaskPlanner"],
  "requires_interfaces": {
    "llm_gateway": ">=1.0.0",
    "role_manager": ">=1.0.0"
  },
  "event_contract": {
    "publishes": ["task.planned", "task.plan_updated"],
    "subscribes": ["task.plan_requested", "task.replan_requested"]
  }
}
```

### 4.2 版本校验规则

| 场景 | 行为 |
|------|------|
| 插件版本 < 最低要求 | 拒绝加载，报错 "plugin X requires version >= Y" |
| 插件版本 >= 最低要求 | 正常加载 |
| 缺少依赖插件 | 拒绝加载，报错 "plugin X requires Y, but Y is not loaded" |
| 事件契约不匹配 | 警告但不阻止加载（兼容模式） |

### 4.3 接口版本化

```python
# agent_framework/shared/interfaces/plugin.py

class PluginInterface:
    """插件基类"""
    API_VERSION = "1.0"  # 插件接口版本
    
    async def init(self, event_bus, config): ...
    def register_events(self): ...
    async def start(self): ...
    async def pause(self): ...
    async def resume(self): ...
    async def stop(self): ...
    async def cleanup(self): ...
```

**版本升级规则**：
- 新增方法 → 小版本升级（如 1.0 → 1.1），向后兼容
- 修改方法签名 → 大版本升级（如 1.0 → 2.0），不向后兼容
- 删除方法 → 大版本升级

---

## 五、插件升级通知机制

### 5.1 升级事件流

```
插件代码变更（通过 upgrade_manager）
    │
    ▼
upgrade_manager 执行验证
    ├── 运行测试
    ├── 检查 manifest.json 版本
    └── 发布 plugin.upgraded 事件
    │
    ▼
其他插件订阅 plugin.upgraded
    ├── 检查依赖版本是否满足
    ├── 如有不兼容 → 发布 plugin.incompatible 事件
    └── 框架自动协调（回滚或通知用户）
```

### 5.2 事件定义

```python
# plugin.upgraded
{
  "plugin_id": "task_planner",
  "old_version": "1.1.0",
  "new_version": "1.2.0",
  "changes": [
    "新增外部模板支持",
    "修复 depends_on 自引用 bug"
  ],
  "breaking_changes": false,
  "requires_restart": false
}

# plugin.incompatible
{
  "plugin_id": "task_scheduler",
  "dependency_id": "task_planner",
  "required_version": ">=1.1.0",
  "actual_version": "1.0.0",
  "action_required": "upgrade_dependency"
}
```

### 5.3 自动协调策略

| 场景 | 策略 |
|------|------|
| 依赖插件升级（兼容） | 自动适配，无需操作 |
| 依赖插件升级（不兼容） | 阻止升级，通知用户手动协调 |
| 被依赖插件降级 | 阻止降级，通知用户 |
| 新增插件 | 正常加载，通知相关插件刷新索引 |

---

## 六、运行时自修改规则

### 6.1 允许的自修改

| 操作 | 允许 | 说明 |
|------|------|------|
| 修改自身配置 | ✅ | 通过 config_service |
| 注册新模板 | ✅ | 通过 task_planner.register_template() |
| 注册新工具 | ✅ | 通过 mcp_framework |
| 创建新角色 | ✅ | 通过 role_manager.create_role() |
| 修改自身代码 | ⚠️ | 必须通过 upgrade_manager，用户确认 |
| 修改其他插件代码 | ❌ | 禁止 |
| 删除其他插件数据 | ❌ | 禁止 |

### 6.2 自修改流程

```
插件检测到优化机会
    │
    ▼
生成升级方案（含变更原因、具体变更、回滚策略、风险评估）
    │
    ▼
发布 plugin.upgrade_proposed 事件
    │
    ▼
upgrade_manager 接收
    ├── 创建 UpgradeReport
    ├── 状态: PENDING
    └── 向用户呈现
    │
    ▼
用户确认 → APPROVED
    │
    ▼
upgrade_manager 执行
    ├── 备份当前代码
    ├── 应用变更
    ├── 运行测试验证
    ├── 成功 → 标记 IMPLEMENTED
    └── 失败 → 回滚
```

---

## 七、热更新级别与一致性检查

### 7.1 热更新三级定义

| 级别 | 名称 | 范围 | 是否需要重启 | 说明 |
|------|------|------|-------------|------|
| L1 | **配置热更新** | 配置文件、模板、关键词等 | ❌ 不需要 | 修改 `~/.suri/data/` 下的配置/模板文件，插件自动监听重载 |
| L2 | **数据热更新** | 三清单、角色定义、工具注册 | ❌ 不需要 | 新增角色/工具/插件时，广播事件更新索引，无需重启 |
| L3 | **代码热更新** | 插件代码变更 | ⚠️ 视情况 | 通过 upgrade_manager 审批后执行，部分场景需重启插件 |

### 7.2 L1 实现指南 — 文件监听热更新

#### 7.2.1 实现技术选型

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|---------|
| `watchdog` 库（inotify/FSEvents/kqueue） | 操作系统级事件通知，延迟低 | 需安装 C 扩展 | 生产部署 |
| `asyncio` 定时轮询（`os.stat()` 比对 mtime） | 零依赖，纯 Python | 延迟高（2-5s），IO 开销 | ✅ **当前实现**（开发阶段） |
| 手动触发 `reload` API | 用户精确控制 | 无自动化 | 备选 |

**当前实现**（`agent_framework/shared/hot_reload.py`）使用**轮询方案**，原因：
- 零外部依赖（不需要 `watchdog` 库）
- 开发阶段足够使用（2 秒轮询间隔）
- 未来可无缝切换到 `watchdog`（接口兼容）

#### 7.2.2 当前实现：FileWatcher

```python
# agent_framework/shared/hot_reload.py
import os
import sys
import time
import asyncio
from pathlib import Path
import importlib
import logging

logger = logging.getLogger(__name__)


class FileWatcher:
    """文件变更监听器（轮询方案）。

    轮询指定目录下的 .py 文件，检测 mtime 变更。
    检测到变更后回调 on_change(path)。

    Args:
        watch_dirs: 要监听的目录列表
        interval: 轮询间隔（秒）
        on_change: 变更回调，接收文件路径字符串
    """

    def __init__(
        self,
        watch_dirs: list,
        interval: float = 2.0,
        on_change=None,
    ):
        self._watch_dirs = [Path(d) for d in watch_dirs]
        self._interval = interval
        self._on_change = on_change
        self._file_mtimes: dict[str, float] = {}
        self._running = False

    async def start(self):
        """启动轮询循环。"""
        self._running = True
        # 初始化 mtime 快照
        for d in self._watch_dirs:
            if d.exists():
                for f in d.rglob("*.py"):
                    try:
                        self._file_mtimes[str(f)] = os.path.getmtime(f)
                    except OSError:
                        pass

        while self._running:
            await self._poll_once()
            await asyncio.sleep(self._interval)

    def stop(self):
        """停止轮询。"""
        self._running = False

    async def _poll_once(self):
        """单次轮询：扫描文件 mtime 变更。"""
        for d in self._watch_dirs:
            if not d.exists():
                continue
            for f in d.rglob("*.py"):
                try:
                    mtime = os.path.getmtime(f)
                    path_str = str(f)
                    last = self._file_mtimes.get(path_str)
                    if last is None:
                        self._file_mtimes[path_str] = mtime  # 首次记录
                    elif mtime > last:
                        self._file_mtimes[path_str] = mtime
                        logger.info(f"[HotReload] 检测到文件变更: {path_str}")
                        if self._on_change:
                            await self._on_change(path_str)
                except OSError:
                    pass  # 文件被删除/权限问题
```

#### 7.2.3 当前实现：HotReloadManager

```python
# agent_framework/shared/hot_reload.py

class HotReloadManager:
    """热更新管理器。

    管理 FileWatcher，检测到文件变更后执行模块重载。
    支持 L1/L2/L3 三级热更新策略。

    Args:
        event_bus: 事件总线，用于发布 notification
        watch_dirs: 监听目录列表
        plugin_manager: 可选的 PluginManager，用于 L3 级插件实例替换
        interval: 轮询间隔（秒）
    """

    LEVEL_L1 = 1  # 配置热更新
    LEVEL_L2 = 2  # 数据热更新（事件广播）
    LEVEL_L3 = 3  # 代码热更新（模块重载）

    def __init__(
        self,
        event_bus=None,
        watch_dirs: list = None,
        plugin_manager=None,
        interval: float = 2.0,
    ):
        self._event_bus = event_bus
        self._plugin_manager = plugin_manager
        self._watcher = FileWatcher(
            watch_dirs=watch_dirs or [],
            interval=interval,
            on_change=self._on_file_changed,
        )
        self._changed_files: set = set()

    async def start(self):
        """启动文件监听。"""
        asyncio.create_task(self._watcher.start())
        logger.info(f"[HotReload] 热更新系统已启动，轮询间隔={self._watcher._interval}s")

    def stop(self):
        self._watcher.stop()

    async def _on_file_changed(self, path: str):
        """文件变更处理。"""
        self._changed_files.add(path)

        # L3: 代码热更新 — importlib.reload
        await self._reload_module(path)

        # L2: 通知 event_bus
        if self._event_bus:
            await self._event_bus.publish(...)

    async def _reload_module(self, path: str) -> bool:
        """尝试重载模块。"""
        path_obj = Path(path)
        module_name = path_obj.stem  # 文件名（不含 .py）

        if module_name not in sys.modules:
            return False  # 未加载的模块不做重载

        try:
            importlib.reload(sys.modules[module_name])
            logger.info(f"[HotReload] ✅ 模块重载成功: {module_name}")
            if self._event_bus:
                await self._event_bus.publish(Event(
                    event_type="system.notification",
                    source="hot_reload",
                    priority=Priority.LOW,
                    payload={
                        "title": "热更新",
                        "body": f"模块 {module_name} 已自动重载",
                    },
                ))
            return True
        except Exception as e:
            logger.error(f"[HotReload] ❌ 重载失败 {module_name}: {e}")
            return False
```

### 7.3 使用方式

在 `access/plugin.py` 中启动热更新：

```python
class AccessPlugin(PluginInterface):
    async def start(self, plugin_manager=None):
        # ...
        await self._start_hot_reload(plugin_manager)

    async def _start_hot_reload(self, plugin_manager=None):
        scan_dirs = [
            str(Path(__file__).parent.parent.parent.parent / "plugins"),
        ]
        self._hot_reload = HotReloadManager(
            self._event_bus,
            watch_dirs=scan_dirs,
            plugin_manager=plugin_manager,
        )
        await self._hot_reload.start()
```

### 7.4 L2 实现指南 — 事件广播热更新

#### 7.4.1 三清单热更新机制

```
变更源（role_manager / mcp_framework / plugin_manager）
    │
    ├── 1. 先持久化到注册表（SQLite 或文件）
    │
    ├── 2. 构建变更 payload（包含旧值/新值/变更类型）
    │
    ├── 3. 发布对应变更事件
    │
    ├── 4. 各订阅者收到事件后：
    │      ├── 读取注册表最新数据
    │      ├── 更新自身内存索引（增量）
    │      └── 不影响正在进行的任务（使用旧快照）
    │
    └── 5. 发布同步完成事件
```

#### 7.4.2 角色热更新示例（role_manager）

```python
# role_manager/plugin.py
class RoleManagerPlugin:
    async def create_role(self, role_id: str, soul_content: str) -> bool:
        """创建新角色并发布热更新事件"""
        # 1. 写入角色定义文件
        role_dir = Path(f"~/.suri/runtime/roles/{role_id}").expanduser()
        role_dir.mkdir(parents=True, exist_ok=True)
        (role_dir / "soul.md").write_text(soul_content)
        (role_dir / "meta.json").write_text(json.dumps({
            "role_id": role_id, "status": "active"
        }))
        
        # 2. 持久化到角色注册表
        db = self._get_registry_db()
        db.execute(...)
        
        # 3. 发布角色创建事件
        await self.event_bus.publish(Event(
            event_type="role.created",
            source="role_manager",
            payload={"role_id": role_id, ...}
        ))
        
        return True
```

#### 7.4.3 工具热更新示例（mcp_framework）

```python
# mcp_framework/plugin.py
class MCPFrameworkPlugin:
    async def register_tool(self, tool_id: str, tool_def: dict) -> bool:
        """注册新 MCP 工具"""
        # 1. 写入工具注册表
        tool_path = Path(f"~/.suri/data/tools/{tool_id}.json")
        tool_path.write_text(json.dumps(tool_def))
        
        # 2. 持久化到 tool_registry
        self._get_tool_registry().execute(...)
        
        # 3. 发布工具注册事件
        await self.event_bus.publish(Event(
            event_type="tool.registered",
            source="mcp_framework",
            payload={"tool_id": tool_id, ...}
        ))
```

### 7.5 L3 实现指南 — 代码热更新

#### 7.5.1 实现技术选型

| 策略 | 说明 | 适用场景 | 风险 |
|------|------|---------|------|
| **函数级重载** | 使用 `importlib.reload()` 重载模块 | 非状态性逻辑（工具函数、模板加载） | 低 |
| **类级替换** | 创建新实例替换旧实例 | 有状态但无长时间运行任务的插件 | 中 |
| **插件进程重启** | 暂停 → 停止 → 加载新版 → 初始化 → 恢复 | 需要完全重置状态 | 高 |
| **系统重启** | 整个 suri-agent 重启 | 核心逻辑变更（EventBus, PluginManager） | 最高 |

当前实现使用 `importlib.reload()` 进行函数级重载（L3），已在 `HotReloadManager._reload_module()` 中实现。

### 7.6 热更新一致性检查

每次热更新执行前必须通过一致性检查：

```
热更新触发
    │
    ├─ 1. 检查版本兼容性
    │      ├── 新配置与当前插件 API 版本兼容
    │      └── 新模板不破坏现有任务状态
    │
    ├─ 2. 检查数据完整性
    │      ├── 新角色创建时必填字段完整（soul.md + meta.json）
    │      ├── 新工具注册时分发 schema 正确
    │      └── 配置更新时格式校验通过
    │
    ├─ 3. 检查引用完整性
    │      ├── 新注册的工具引用的插件必须已加载
    │      ├── 新角色引用的技能需要对应工具已注册
    │      └── 移除的三清单项不能有活跃引用
    │
    ├─ 4. 检查状态一致性
    │      ├── 配置更新不会导致插件进入不一致状态（如模板加载半截）
    │      ├── 批量更新使用"快照 + 全量替换"策略
    │      └── 更新失败自动回滚到上一版本
    │
    └─ 5. 检查并发安全
           ├── 热更新期间正在进行的任务不受影响（使用旧版本快照）
           └── L3 代码热更新时需等待当前事件处理链完成
```

**一致性检查失败处理**：

| 检查失败类型 | 处理策略 |
|-------------|---------|
| 版本不兼容 | ❌ 拒绝热更新，发布 error.incompatible 事件 |
| 数据不完整 | ❌ 拒绝热更新，提示缺少字段 |
| 引用不完整 | ❌ 拒绝热更新，列出缺失依赖 |
| 状态不一致 | ⚠️ 拒绝热更新 + 快照回滚 |
| 并发冲突 | ⏳ 等待后重试（最多重试 3 次） |

### 7.7 热更新性能保障

```
热更新操作的限制策略：

1. 节流（Throttle）
   - 同一配置文件 3 秒内多次修改 → 只触发一次更新
   - 三清单批量变更 → 合并为一次广播事件

2. 优先级
   - L1 配置热更新：高优先级（瞬时完成）
   - L2 数据热更新：中优先级（异步，不影响正在处理的事件）
   - L3 代码热更新：低优先级（需要用户审批 + 任务等待）

3. 资源限制
   - 单次热更新处理时间 ≤ 200ms（超时标记失败）
   - 并行热更新数 ≤ 3
```

---

## 八、各插件热更新适配清单

| 插件 | 需外部化数据 | 热更新事件 | 适配优先级 | 状态 |
|------|-------------|-----------|-----------|------|
| role_manager | Soul 模板、工具说明 | `config.updated`, `role_manager.templates_updated` | 🔴 迭代 2 | ✅ 已完成 |
| task_planner | 任务模板 | `config.updated`, `task_planner.templates_updated` | 🔴 迭代 2 | ✅ 已完成 |
| interrupt_handler | 关键词列表 | `config.updated`, `interrupt_handler.keywords_updated` | 🟡 迭代 2 | ✅ 已完成 |
| access（CLI） | 通道路由 | `config.updated` | 🟡 迭代 5 | ✅ 已完成（FileWatcher + HotReloadManager） |
| llm_gateway | 模型配置 | `config.updated` | 🟢 迭代 5 | ⏳ 待适配 |
| agent_registry | — | `role.created` | 🟢 迭代 5 | ⏳ 待适配 |
| code_tool | — | `tool.registered` | 🟢 迭代 5 | ⏳ 待适配 |

---

## 九、热更新排查指南

> 为什么改了代码后终端没有自动重载？本节列出最常见原因及解决方案。

### 9.1 `importlib.reload()` 的已知限制

| # | 问题 | 原因 | 解决方案 |
|---|------|------|---------|
| 1 | **实例级代码不生效** | `reload()` 只更新模块中的函数/类定义，**已创建的实例（对象）仍使用旧代码**。插件实例在 `start()` 时已创建，修改 `plugin.py` 后实例的方法不会自动更新 | 需要手动执行 `/plugin restart <N>` 重建实例 |
| 2 | **函数以外的作用域代码不会重新执行** | 模块顶层的 `CONSTANT = ...`、`registry = {}` 等全局变量在 reload 后保持旧值 | 将全局状态封装到函数/类方法中 |
| 3 | **`from X import Y` 不会被更新** | `reload()` 更新的是 `sys.modules['X']`，但 `from X import Y` 在导入模块中创建了局部引用 `Y`，`reload()` 无法更新它 | 改用 `import X; X.Y` 访问 |
| 4 | **嵌套引用不会级联重载** | 重载 `plugin.py` 不会自动重载它 `from formatter import ...` 的模块 | 手动 `reload(formatter)` 或重启插件 |
| 5 | **`__init__.py` 更改不生效** | 包的 `__init__.py` 被 reload 后，其子模块的已导入引用不会自动更新 | 重启整个插件 |

### 9.2 热更新有限作用域

```
✅ importlib.reload() 可以更新：
   - 插件中的普通工具函数（无状态的纯函数）
   - 模板加载逻辑（从文件读取模板的代码）
   - 配置解析逻辑

❌ importlib.reload() 无法更新：
   - 已经通过 plugin.start() 创建的实例方法
   - EventBus 事件处理器的注册
   - manifest.json 中的元数据
   - 已经建立的 asyncio 任务/循环
   - 已有连接的 Session
```

### 9.3 需要热更新的正确姿势

| 变更类型 | 正确方式 | 命令 |
|---------|---------|------|
| **修改模板/配置/关键词文件** | 自动热更新（L1） | 无需操作，`FileWatcher` 自动检测 |
| **新增角色/工具/插件注册** | 自动热更新（L2） | 无需操作，EventBus 广播 |
| **修改插件工具函数（纯逻辑）** | 自动热更新（L3） | 无需操作，`importlib.reload()` |
| **修改插件类方法/事件处理** | 手动重启插件 | `/plugin restart <N>` |
| **修改 manifest.json** | 手动重启插件 | `/plugin restart <N>` |
| **修改 formatter.py（面板渲染）** | 自动热更新（L3） | 会更新，但下次调用才生效 |
| **修改事件总线/核心框架** | 重启系统 | `/quit` → `python main.py` |
| **添加新的 / 命令** | 手动重启 | `/plugin restart access` |

### 9.4 快速验证热更新是否正常

```bash
# 1. 启动系统
python main.py

# 2. 修改一个纯函数（例如 formatter.py 中的 _truncate 函数）
#    将 "…" 改为 "..."
vim agent_framework/plugins/access/formatter.py

# 3. 2 秒后终端输出：
# [HotReload] ✅ 模块重载成功: formatter

# 4. 输入 /plugins 查看效果
#    截断符号已从 … 变为 ...
```

### 9.5 热更新调试状态

| 命令 | 用途 |
|------|------|
| `/hotreload` | 查看热更新系统当前状态（监听目录、轮询间隔、最近变更列表） |
| `/hotreload toggle` | 暂停/恢复自动热更新 |
| `/hotreload status` | 显示 FileWatcher 运行状态和已检测到的文件变更记录 |

### 9.6 热更新是"开发加速器"不是"生产部署"

```
热更新定位：
  ┌───────────────────────────────────────────┐
  │  热更新 = 开发阶段的效率工具               │
  │  - 快速迭代模板/配置/工具函数              │
  │  - 减少 `Ctrl+C → 重启` 的次数            │
  │  - 不是生产环境的部署策略                  │
  │                                           │
  │  正式部署 = `/plugin upgrade <N>`          │
  │  或 `git pull && python main.py`           │
  └───────────────────────────────────────────┘

所以：
  - 修改函数逻辑 → 热更新 ✅
  - 修改类结构   → /plugin restart ✅
  - 生产部署升级 → upgrade_manager ✅
```

---

## 十、相关文档

- [cli.md §16.3 热更新架构](../plugins/access/channels/cli.md) — 热更新事件在 CLI 通道中的刷新策略
- [startup.md](./startup.md) — 系统启动流程
- [plugin-development.md](./plugin-development.md) — 插件开发指南