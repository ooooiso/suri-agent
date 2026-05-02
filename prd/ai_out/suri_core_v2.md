# suri_core 插件 PRD（重构版）

## 定位

**内核插件**。概念上属于插件体系一员（有 manifest、生命周期、可被监控），但启动时由极简入口 `main.py` 实例化并自举注册，不由 PluginManager 加载。

职责仅限两件事：**事件总线** + **插件生命周期管理**。不执行业务逻辑，不处理任务调度，不直接调用模型。

## 变更说明（对比 v1）

| 变更项 | v1 | v2 |
|--------|-----|-----|
| EventRouter | 独立组件 | **合并入 EventBus**（内部分发逻辑） |
| 职责边界 | EventBus + PluginManager + EventRouter | **EventBus（含分发） + PluginManager** |
| 任务调度 | EventRouter 提及替代 Scheduler | **明确移除，由 task_scheduler 插件承担** |

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
bootstrap()：
  ├─ 创建 EventBus（含内部分发逻辑）
  ├─ 创建 PluginManager
  ├─ 自注册：suri_core 注册为第一个插件
  └─ 扫描并加载其他插件
    │
    ▼
系统就绪，等待事件
```

```python
# main.py
import asyncio
from suri_core import SuriCorePlugin

async def main():
    core = SuriCorePlugin()
    await core.bootstrap()
    await core.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## 功能需求

### 1. 事件总线（EventBus）

基于 asyncio.Queue 的异步发布/订阅模式。

**分发逻辑**（原 EventRouter 功能，现内置于 EventBus）：
- 根据 `event.event_type` 匹配订阅者
- 根据 `event.target`（如有）精确投递
- 支持通配符订阅：`system.*`、`role.*`、`error.*`
- 事件优先级：CRITICAL / HIGH / NORMAL / LOW
- 4 个工作协程并行分发
- SQLite 持久化高优先级事件，支持崩溃恢复

**标准事件类型**：
- `system.*` — 系统事件（启动、关闭、插件变更）
- `user.input` / `user.command` — 用户输入
- `role.*` — 角色事件
- `task.*` — 任务事件（由 task_scheduler 和角色发布）
- `llm.request` / `llm.response` — 大模型请求/响应
- `tool.call` / `tool.result` — 工具调用/结果
- `error.*` — 错误事件
- `plugin.*` — 插件事件（加载、卸载、升级）

**关键约束**：EventBus 只做消息路由和投递，不解析消息内容，不决定消息去向，不执行任何业务逻辑。

### 2. 插件管理器（PluginManager）

- 扫描路径：`plugins/` + `~/.suri/runtime/plugins/`
- 生命周期：扫描 → 加载 → 初始化 → 注册 → 运行 → 暂停 → 卸载 → 清理
- 依赖排序加载（拓扑排序）
- AST 静态安全扫描（禁止 socket/subprocess/eval/exec 等）
- 配置隔离：每个插件只接收自己的配置子树
- SQLite 注册表 + 内存字典双轨
- 心跳检测：核心插件 5s，普通插件 30s，超时自动标记 ERROR

## 接口定义

### 订阅事件
- `system.shutdown` → 优雅关闭所有子系统
- `system.heartbeat` → 响应心跳检测
- `plugin.upgrade_proposed` → 接收插件升级方案（包括 suri_core 自身）

### 发布事件
- `system.start` / `system.shutdown`
- `system.plugin_loaded` / `system.plugin_unloaded`
- `error.plugin` / `error.system`

**注意**：suri_core **不发布** task.* 事件。task 事件由 task_scheduler 和角色发布和订阅。

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
6. 【suri_core 特有】冒烟测试：验证 EventBus 分发 + PluginManager 加载流程正常
        │
        ▼
7. 热更新或重启生效
```

**suri_core 升级的特殊约束**：
- 变更后必须能通过冒烟测试
- 建议非紧急变更在低谷期执行
- 关键升级需要重启（无法纯热更新）

## 配置项

```yaml
suri_core:
  event_bus:
    queue_maxsize: 10000
    worker_count: 4
    persist: true
    enable_wildcard: true
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
- 所有其他插件均依赖本插件
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
- **升级安全**：suri_core 升级方案必须包含回滚策略，变更后必须通过冒烟测试
- **明确边界**：任务调度、规划、Agent 管理全部由独立插件承担，suri_core 不介入
