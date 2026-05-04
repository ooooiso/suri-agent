# 插件开发指南

> 本文档指导开发者创建、测试、发布 suri-agent 插件。

---

## 一、插件目录结构

```
agent_framework/plugins/{type}/{name}/
├── __init__.py          # 导出 Plugin 类
├── manifest.json        # 插件元数据（必填）
├── plugin.py            # 主入口（继承 PluginInterface）
└── ...                  # 其他模块
```

**说明**：
- 所有新插件创建在 `agent_framework/plugins/{type}/{name}/` 下
- `{type}` 为插件类型：access / service / execution / capability / extension
- `plugins/`（顶层目录）已废弃，不创建新插件

---

## 二、manifest.json 规范

```json
{
  "name": "my_plugin",
  "version": "1.0.0",
  "type": "capability",
  "min_suri_version": "1.0.0",
  "api_version": "1.0",
  "requires_interfaces": {
    "config_service": ">=1.0.0",
    "log_service": ">=1.0.0"
  },
  "event_contract": {
    "publishes": ["my_plugin.event_name"],
    "subscribes": ["other_plugin.event_name"]
  },
  "exposes": {
    "events": ["my_plugin.event_name"],
    "tools": [],
    "commands": []
  },
  "hot_reload_level": "L1"
}
```

---

## 三、PluginInterface 实现

```python
"""agent_framework/plugins/{type}/{name}/plugin.py"""

from agent_framework.shared.interfaces.plugin import PluginInterface

class MyPlugin(PluginInterface):
    """示例插件"""
    
    API_VERSION = "1.0"
    
    async def init(self, event_bus, config):
        """初始化：接收依赖注入"""
        self.event_bus = event_bus
        self.config = config
        self.running = False
    
    def register_events(self):
        """注册事件订阅"""
        self.event_bus.subscribe("system.started", self._on_started)
        self.event_bus.subscribe("config.updated", self._on_config_updated)
    
    async def start(self):
        """启动插件"""
        self.running = True
    
    async def stop(self):
        """停止插件"""
        self.running = False
    
    async def cleanup(self):
        """清理资源"""
        pass
    
    async def _on_started(self, event):
        """处理 system.started 事件"""
        pass
    
    async def _on_config_updated(self, event):
        """配置热更新"""
        pass
```

---

## 四、事件通信

```python
# 发布事件
await self.event_bus.publish(Event(
    event_type="my_plugin.result",
    source="my_plugin",
    payload={"key": "value"},
    priority=Priority.NORMAL
))

# 订阅事件（在 register_events 中）
self.event_bus.subscribe("other_plugin.event", self._handler)
self.event_bus.subscribe("*.result", self._catch_all)  # 通配符
```

---

## 五、测试

```python
"""tests/plugin/test_my_plugin.py"""
from tests.framework.base import AsyncTestCase

class TestMyPlugin(AsyncTestCase):
    async def test_event_handling(self):
        await self.plugin.init(self.event_bus, {})
        self.plugin.register_events()
        await self.plugin.start()
        
        # 发布事件并验证
        events = await self.publish_and_collect(
            event_type="some.event",
            payload={},
            expected_count=1
        )
        self.assertEqual(len(events), 1)
```

---

## 六、命令注册

插件通过 manifest.json 的 `commands` 字段声明自己的 CLI 命令，终端自动发现，新增不需要改 CLI 代码。

### 6.1 manifest.json 新增 commands 字段

```json
{
  "name": "llm_gateway",
  "description": "5 家国产大模型路由与调度",
  "commands": [
    {
      "name": "switch",
      "usage": "/switch <厂商> [模型]",
      "desc": "切换 LLM 厂商",
      "args": [
        {"name": "厂商", "required": true, "desc": "厂商名如 deepseek/kimi"},
        {"name": "模型", "required": false, "desc": "模型名如 deepseek-chat"}
      ]
    },
    {
      "name": "setkey",
      "usage": "/setkey <厂商> [key]",
      "desc": "修改 API Key",
      "args": [
        {"name": "厂商", "required": true, "desc": "厂商名"},
        {"name": "key", "required": false, "desc": "API Key 值"}
      ]
    },
    {
      "name": "models",
      "usage": "/models",
      "desc": "列出所有可用模型",
      "args": []
    },
    {
      "name": "model",
      "usage": "/model",
      "desc": "查看当前使用的模型",
      "args": []
    }
  ]
}
```

### 6.2 命令注册流程

```
启动时 / 插件加载时
    │
    ▼
PluginManager 扫描所有 manifest.json
    │
    ▼
提取每个插件的 commands 字段
    │
    ▼
合并成全局命令表 COMMAND_REGISTRY
    │
    ▼
注入到 CLIChannelPlugin（Tab 补全 / /help 显示 / 路由分发）
```

### 6.3 命令存储方式

| 来源 | 优先级 | 说明 |
|------|--------|------|
| **manifest.json 声明** | 低 | 每个插件的 `commands` 字段，启动时批量加载 |
| **动态注册 API** | 高 | `register_command(cmd_info)` 运行时动态添加 |
| **内置命令** | 最高 | `help`, `quit` 等 CLI 通道自身提供 |

同名的以后注册者为准（防止恶意覆盖需结合权限系统）。

---

## 七、插件状态规范

### 7.1 状态枚举

所有插件实例必须维护 `_status` 和 `_running` 属性，CLI 通道从这两个属性读取并映射为终端图标。

| 状态 | 枚举值 | 图标 | 条件 |
|------|--------|------|------|
| 运行中 | running | ✅ | `_running == True` 且心跳 ≤ 10s |
| 响应延迟 | delayed | ⚠️ | `_running == True` 但心跳 10-30s |
| 无响应 | timeout | ❌ | `_running == True` 但心跳 > 30s |
| 等待中 | pending | ⏳ | `_running == False` 且刚初始化 |
| 加载失败 | load_failed | ❌ | init() 或 start() 抛出异常 |
| 已暂停 | stopped | ⏸ | `_running == False` 且用户手动 stop |
| 升级中 | upgrading | ❕ | upgrade() 执行中 |
| 已卸载 | removed | 🗑️ | remove() 完成后从列表移除 |

### 7.2 插件生命周期实现规范

插件实现类必须遵守以下属性约定：

```python
class PluginInterface:
    _status: str = "pending"       # 当前状态枚举值
    _running: bool = False          # 运行标志
    _heartbeat: float = 0.0        # 最后一次心跳时间戳 (time.time())
    
    async def start(self):
        """状态变化: pending/stopped → running"""
        self._running = True
        self._status = "running"
        self._heartbeat = time.time()
    
    async def stop(self):
        """状态变化: running → stopped"""
        self._running = False
        self._status = "stopped"
    
    async def restart(self):
        """状态变化: running → stopped → running"""
        await self.stop()
        await self.start()
    
    async def upgrade(self, target_version: str):
        """状态变化: running → upgrading → running"""
        self._status = "upgrading"
        # ... 执行升级逻辑 ...
        self._manifest["version"] = new_version
        self._status = "running"
    
    async def remove(self):
        """状态变化: running → removed (然后从列表移除)"""
        await self.stop()
        self._status = "removed"
    
    async def heartbeat(self):
        """心跳上报"""
        self._heartbeat = time.time()
        await self.event_bus.publish(Event(
            event_type="system.heartbeat",
            source=self._manifest["name"],
            payload={
                "plugin_id": self._manifest["name"],
                "timestamp": datetime.now().isoformat(),
                "status": self._status,
            }
        ))
```

### 7.3 状态转换矩阵

| 当前状态 | 触发操作 | 目标状态 | 说明 |
|---------|---------|---------|------|
| pending | init() 成功 | initialized | 初始化完成 |
| initialized | start() | running | 正常启动 |
| initialized | start() 异常 | load_failed | 启动失败 |
| running | stop() | stopped | 手动暂停 |
| running | 心跳超时 10s | delayed | 响应延迟警告 |
| running | 心跳超时 30s | timeout | 无响应 |
| running | upgrade() | upgrading | 升级中 |
| running | remove() | removed | 删除后移除 |
| stopped | start() | running | 恢复运行 |
| load_failed | start() | running | 重试启动 |
| upgrading | 升级完成 + start() | running | 升级成功 |
| timeout | restart() | running | 重启恢复 |
| delayed | 心跳恢复 ≤ 10s | running | 自动恢复 |

### 7.4 CLI 图标映射函数

```python
def _get_status_icon(self, plugin) -> str:
    """根据插件实时状态返回终端图标。"""
    status = getattr(plugin, "_status", "pending")
    running = getattr(plugin, "_running", False)
    heartbeat = getattr(plugin, "_heartbeat", 0)
    
    # 特殊状态优先
    if status == "upgrading":
        return "❕"
    if status == "load_failed":
        return "❌"
    if status == "stopped":
        return "⏸"
    if status == "removed":
        return "🗑️"
    
    # 运行中的插件检查心跳
    if running:
        elapsed = time.time() - heartbeat
        if elapsed <= 10:
            return "✅"
        elif elapsed <= 30:
            return "⚠️"
        else:
            return "❌"  # 超时
    
    # 未启动
    return "⏳"
```

---

## 八、检查清单

- [ ] manifest.json 包含 name / version / type / api_version
- [ ] requires_interfaces 声明所有依赖
- [ ] event_contract 声明所有 publish/subscribe 事件
- [ ] hot_reload_level 正确设置
- [ ] 实现 PluginInterface 所有方法
- [ ] 单元测试覆盖
- [ ] 不直接 import 其他插件的类
- [ ] 不共享可变状态（全局变量）
- [ ] 不硬编码配置/模板数据