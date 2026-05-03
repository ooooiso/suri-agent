# test_framework 插件 PRD

## 定位

提供标准化的测试基础设施，所有插件测试使用统一基类和夹具。

**关键约束**：只提供测试工具，不参与业务逻辑。测试代码不部署到生产环境。

---

## 功能需求

### 1. EventBusFixture

内存事件总线 mock，用于插件测试。

```python
class EventBusFixture:
    """测试用 EventBus mock，记录所有发布的事件"""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._published: List[Event] = []
    
    async def publish(self, event: Event) -> None:
        """发布事件，记录到 _published 列表"""
        self._published.append(event)
        # 同步调用匹配的订阅者
        for pattern, handlers in self._subscribers.items():
            if self._match(pattern, event.event_type):
                for handler in handlers:
                    await handler(event)
    
    async def subscribe(self, pattern: str, handler: Callable) -> None:
        """注册订阅"""
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)
    
    def get_published_events(self, event_type: str = None) -> List[Event]:
        """获取已发布的事件列表，可按类型过滤"""
        if event_type:
            return [e for e in self._published if e.event_type == event_type]
        return self._published
    
    def clear(self) -> None:
        """清空所有记录"""
        self._published.clear()
        self._subscribers.clear()
    
    def _match(self, pattern: str, event_type: str) -> bool:
        """通配符匹配"""
        if pattern == event_type:
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return False
```

### 2. TestBase

所有测试的基类，提供隔离的运行环境。

```python
class TestBase(unittest.IsolatedAsyncioTestCase):
    """测试基类，提供 EventBusFixture 和临时目录"""
    
    async def asyncSetUp(self):
        self.bus = EventBusFixture()
        self.tmp_dir = tempfile.mkdtemp()
    
    async def asyncTearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def create_event(self, event_type: str, payload: dict, 
                     source: str = "test") -> Event:
        return Event(event_type=event_type, source=source, payload=payload)
```

### 3. PluginTestHarness

插件加载和生命周期测试工具。

```python
class PluginTestHarness:
    """插件测试工具，模拟插件加载和生命周期"""
    
    def __init__(self, bus: EventBusFixture):
        self.bus = bus
        self.plugin = None
    
    async def load_plugin(self, plugin_class: type, config: dict = None) -> PluginInterface:
        """加载插件实例"""
        self.plugin = plugin_class()
        await self.plugin.init(self.bus, config or {})
        self.plugin.register_events()
        await self.plugin.start()
        return self.plugin
    
    async def run_lifecycle(self) -> None:
        """运行完整生命周期测试"""
        await self.plugin.pause()
        await self.plugin.resume()
        await self.plugin.stop()
        await self.plugin.cleanup()
    
    def assert_event_published(self, event_type: str) -> None:
        """断言某类型事件已被发布"""
        events = self.bus.get_published_events(event_type)
        self.assertTrue(len(events) > 0, f"Event {event_type} not published")
    
    def assert_event_not_published(self, event_type: str) -> None:
        """断言某类型事件未被发布"""
        events = self.bus.get_published_events(event_type)
        self.assertEqual(len(events), 0, f"Event {event_type} was published")
```

### 4. RoleFixture

角色环境 mock，创建临时角色目录。

```python
class RoleFixture:
    """角色测试夹具，创建临时角色目录和 Soul 文件"""
    
    def __init__(self, role_id: str = "test_role"):
        self.role_id = role_id
        self.tmp_dir = tempfile.mkdtemp()
        self.role_dir = f"{self.tmp_dir}/roles/{role_id}"
        os.makedirs(f"{self.role_dir}/memories/insights", exist_ok=True)
        os.makedirs(f"{self.role_dir}/skills", exist_ok=True)
        self.soul_path = f"{self.role_dir}/soul.md"
    
    def write_soul(self, content: str) -> None:
        """写入 Soul 文件"""
        with open(self.soul_path, "w") as f:
            f.write(content)
    
    def get_insights_dir(self) -> str:
        return f"{self.role_dir}/memories/insights"
    
    def cleanup(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
```

---

## 接口定义

### 订阅事件

无（test_framework 不订阅业务事件）

### 发布事件

无（test_framework 不发布业务事件）

---

## 配置项

```yaml
test_framework:
  enabled: true
  tmp_dir_prefix: "suri_test_"
```

---

## 依赖关系

- 上游：无（独立工具）
- 下游：所有插件的测试代码

---

## 生命周期

1. `init()` → 无操作（工具类，无状态）
2. `start()` → 无操作
3. `stop()` → 无操作
4. `cleanup()` → 无操作

---

## 已知问题 & 优化项（迭代 2 发现）

### 1. `run_lifecycle` 是异步方法但被同步调用

**问题描述**：`PluginTestHarness.run_lifecycle()` 是 async 方法，但测试中调用时未加 `await`（如 `self.harness.run_lifecycle()`），导致生命周期测试实际上没有真正执行完整的生命周期流程。

**影响**：`test_lifecycle` 测试虽然通过，但未验证 pause → resume → stop → cleanup 的实际执行。

**建议修复**：
- 测试中改为 `await self.harness.run_lifecycle()`
- 或让 `run_lifecycle` 支持同步调用（内部使用 `asyncio.run` 或 `create_task`）

### 2. EventBusFixture 与真实 EventBus 行为不一致

**问题描述**：EventBusFixture 的 `subscribe` 是同步方法，但真实 EventBus 的 `subscribe` 是异步 coroutine。接口签名不同，导致测试环境与生产环境行为不一致。

**建议修复**：
- 统一接口签名，让 EventBusFixture 的 `subscribe` 也返回 coroutine
- 或让真实 EventBus 提供同步的 `subscribe_sync` 方法
- 或让 EventBusFixture 完全模拟真实 EventBus 的行为（包括异步分发、优先级排序等）
