# suri_core 插件 PRD

## 定位

**内核插件**。概念上属于插件体系一员（有 manifest、生命周期、可被监控），但启动时由极简入口 `main.py` 实例化并自举注册，不由 PluginManager 加载。

职责仅限两件事：**事件总线** + **插件生命周期管理**。不执行业务逻辑，不处理任务，不直接调用模型。所有业务由角色通过事件协同完成。

## 特殊属性

| 属性 | 值 | 说明 |
|------|-----|------|
| `type` | `core` | 标识为内核插件，PluginManager 特殊处理 |
| `runtime_mutable` | `false` | 代码运行时不可自修改（所有插件统一约束） |
| `self_registration` | `true` | 启动时自行注册到 PluginManager，不由外部加载 |

## 启动流程

```
main.py（极简入口，<20 行，非插件）
    │
    ▼
实例化 SuriCorePlugin
    │
    ▼
自举注册：core.register_self(plugin_manager)
    │
    ▼
PluginManager 扫描并加载其他插件
    │
    ▼
系统就绪，事件总线开始分发
```

```python
# main.py
import asyncio
from suri_core import SuriCorePlugin

async def main():
    core = SuriCorePlugin()
    await core.bootstrap()  # 自举：创建 EventBus、PluginManager、自注册、加载其他插件
    await core.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## 功能需求

### 1. 事件总线（EventBus）
- 基于 `asyncio.PriorityQueue` 的异步发布/订阅模式
- 支持通配符订阅：`system.*`、`role.*`、`error.*`
- 事件优先级：CRITICAL / HIGH / NORMAL / LOW，同优先级按 FIFO 顺序（通过单调递增 counter 保证）
- 4 个工作协程并行分发
- SQLite 持久化高优先级事件，支持崩溃恢复
- **PriorityQueue tie-breaker**：入队元组为 `(priority_value, counter, event)`，避免同优先级 Event 对象不可比较导致 `TypeError`
- **事件持久化主键**：使用 SQLite 自增 ID 作为主键，`event_id` 列仅用于业务追踪，不参与主键约束。避免多个事件共享同一 `request_id` 时被 `INSERT OR IGNORE` 静默丢弃。
- 标准事件类型：system.*、user.input、role.*、task.*、agent.*、llm.request/response、tool.call/result、error.*、plugin.*、upgrade.*、interrupt.*、doc_sync.*

**关键约束**：EventBus 只做消息路由，不解析消息内容，不决定消息去向。路由目标由订阅者自己匹配。

### 2. 插件管理器（PluginManager）
- 扫描路径：`plugins/` + `~/.suri/runtime/plugins/`
- 生命周期：扫描 → 加载 → 初始化 → 注册 → 运行 → 暂停 → 卸载 → 清理
- 依赖排序加载（拓扑排序）
  - 构建反向图：`graph[name]` = 依赖 name 的节点集合
  - 入度 = 当前节点依赖的节点数
  - 入度为 0 的节点先加载（不依赖任何其他节点）
  - 确保 A 依赖 B 时，B 在 A 之前加载
- AST 静态安全扫描（禁止 socket/subprocess/eval/exec/__import__ 等）
- **匹配规则**：精确匹配 `func_name == forbidden_api` 或 `func_name.endswith(f".{forbidden_api}")`，避免子字符串误报（如 `run_in_executor` 被 `exec` 误杀）
- 配置隔离：每个插件只接收自己的配置子树
- SQLite 注册表 + 内存字典双轨
- 心跳检测：核心插件 5s，普通插件 30s，超时自动标记 ERROR

### 3. 事件分发（内置于 EventBus）
- EventBus 内部包含轻量级分发逻辑
- 根据 `event.event_type` 匹配订阅者，根据 `event.target`（如有）精确投递
- 支持通配符订阅匹配
- **不执行**任务逻辑、**不调用**LLM、**不重试**业务操作
- 任务调度由 **task_scheduler** 插件独立承担

## 接口定义

### 订阅事件
- `system.shutdown` → 优雅关闭所有子系统
- `system.heartbeat` → 响应心跳检测
- `plugin.upgrade_proposed` → 接收插件升级方案（包括 suri_core 自身）

### 发布事件
- `system.start` / `system.shutdown`
- `system.plugin_loaded` / `system.plugin_unloaded`
- `system.heartbeat` — 汇总所有插件心跳，更新 plugins 表 last_heartbeat
- `error.plugin` / `error.system`

**注意**：suri_core **不发布** task.* / agent.* / llm.* / tool.* / upgrade.* / interrupt.* / doc_sync.* 等业务事件。这些事件由对应业务插件和角色发布和订阅。

## 事件 Payload Schema

### 订阅事件

#### `system.shutdown`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `reason` | string | 否 | 关闭原因，如 "user_request" / "error" |
| `force` | boolean | 否 | 是否强制关闭，默认 false |
| `timeout` | integer | 否 | 优雅关闭超时（秒），默认 30 |

#### `system.heartbeat`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 发送心跳的插件 ID |
| `timestamp` | string | 是 | ISO 8601 时间戳 |
| `status` | string | 是 | 插件状态：running / paused / error |

#### `plugin.upgrade_proposed`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 提议升级的插件 ID |
| `current_version` | string | 是 | 当前版本 |
| `target_version` | string | 是 | 目标版本 |
| `reason` | string | 是 | 升级原因 |
| `rollback_plan` | string | 是 | 回滚策略 |

### 发布事件

#### `system.start`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `timestamp` | string | 是 | 启动时间 |
| `version` | string | 是 | 系统版本 |
| `loaded_plugins` | array | 是 | 已加载插件列表 |

#### `system.plugin_loaded`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 插件 ID |
| `version` | string | 是 | 版本 |
| `type` | string | 是 | 插件类型 |
| `load_time_ms` | integer | 否 | 加载耗时 |

#### `system.heartbeat`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 发送心跳的插件 ID |
| `timestamp` | string | 是 | ISO 8601 时间戳 |
| `status` | string | 是 | 插件状态：running / paused / error |
| `queue_depth` | integer | 否 | 事件队列深度（如适用） |
| `memory_mb` | integer | 否 | 内存占用（MB） |

**心跳机制**：每个插件每 30 秒通过 EventBus 发布 `system.heartbeat`。suri_core 接收后更新 `plugins` 表的 `last_heartbeat` 字段。超过 120 秒未收到心跳的插件标记为 `stale`，触发 `error.plugin`。

#### `system.plugin_unloaded`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 插件 ID |
| `reason` | string | 否 | 卸载原因 |

#### `error.plugin`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | string | 是 | 出错插件 ID |
| `error_code` | integer | 是 | 错误码 |
| `error_type` | string | 是 | 错误类型 |
| `message` | string | 是 | 错误描述 |
| `traceback` | string | 否 | 堆栈信息 |
| `timestamp` | string | 是 | 错误时间 |

#### `error.system`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `error_code` | integer | 是 | 错误码 |
| `error_type` | string | 是 | 错误类型 |
| `message` | string | 是 | 错误描述 |
| `severity` | string | 是 | 严重级别：critical / high / medium / low |
| `timestamp` | string | 是 | 错误时间 |

## 升级流程

suri_core 代码升级走**所有插件统一的自修改流程**：

```
1. 自分析（PluginSelfLearning 或 suri 角色分析）
        │
        ▼
2. 生成升级方案（原因、变更内容、回滚策略、风险评估）
        │
        ▼
3. suri 角色汇总，向用户呈现方案
        │
        ▼
4. 用户确认
        │
        ▼
5. 执行代码变更（IDE 模式：suri 角色生成变更文件，用户审阅后应用）
        │
        ▼
6. 【suri_core 特有】健康检查：验证变更后核心功能正常
        │
        ▼
7. 热更新或重启生效
```

**suri_core 升级的特殊约束**：
- 变更后必须能通过冒烟测试（EventBus 基本功能、PluginManager 加载流程）
- 建议非紧急变更在低谷期执行
- 关键升级需要重启（无法纯热更新）

## 配置项

```yaml
suri_core:
  event_bus:
    queue_maxsize: 10000
    worker_count: 4
    persist: true
  plugin_manager:
    scan_dirs: ["plugins/"]
    auto_load_core: true
    heartbeat_interval: 5
    heartbeat_timeout: 30
    ast_scan:
      enabled: true
      forbidden: ["socket", "subprocess", "eval", "exec", "os.system"]
```

## Manifest 示例

```json
{
  "name": "suri_core",
  "version": "1.0.0",
  "type": "core",
  "description": "内核插件，提供 EventBus 和 PluginManager",
  "permissions": ["system.*", "plugin.*"],
  "event_subscriptions": ["system.shutdown", "plugin.upgrade_proposed"],
  "runtime_mutable": false,
  "self_registration": true
}
```

## 依赖关系

- 无上游依赖（框架最底层）
- 下游：所有其他 19 个插件均依赖本插件
  - 基础服务层：config_service / log_service / security_service
  - 执行层：task_scheduler / task_planner / agent_registry / role_comm / interrupt_handler
  - 能力层：llm_gateway / memory_service / role_manager / role_learner / mcp_framework / upgrade_manager
  - 接入层：access
  - 扩展层：cron_service / hooks_service / test_framework / doc_sync
- 本插件不由 PluginManager 加载，由 main.py 实例化后自注册

## 数据模型

### SQLite 表
- `plugins` — 插件注册表（name/version/type/path/status/capabilities/last_heartbeat）
- `events` — 事件日志（event_id/event_type/source/target/payload/priority/timestamp/consumed）

## 生命周期

1. `__init__()` → 初始化内部状态（不创建 EventBus）
2. `bootstrap()` → 创建 EventBus、创建 PluginManager、自注册、加载其他插件
3. `register_events()` → 订阅 system.shutdown、plugin.upgrade_proposed
4. `start()` → 启动 EventBus worker、心跳循环
5. `pause()` → 暂停 EventBus 新事件入队
6. `resume()` → 恢复
7. `stop()` → 停止心跳、按依赖反向卸载其他插件（不卸载自己）
8. `cleanup()` → 关闭 EventBus、释放资源

## 安全边界

- 动态插件加载前必须经过 AST 安全扫描
- 危险操作直接拒绝加载
- 异常插件隔离，不影响核心和其他插件运行
- **核心原则**：suri_core 不解析业务事件内容，只做投递
- **升级安全**：suri_core 升级方案必须包含回滚策略，变更后必须通过健康检查
