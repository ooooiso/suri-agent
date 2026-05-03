"""test_framework 插件 — 测试基础设施"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Callable, Dict, List, Optional

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event


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
    
    def subscribe(self, pattern: str, handler: Callable) -> None:
        """注册订阅（同步接口，与真实 EventBus 一致）"""
        if pattern not in self._subscribers:
            self._subscribers[pattern] = []
        self._subscribers[pattern].append(handler)
    
    def subscribe_sync(self, pattern: str, handler: Callable) -> None:
        """同步订阅（别名，与真实 EventBus 一致）"""
        self.subscribe(pattern, handler)
    
    def unsubscribe(self, pattern: str, handler: Callable) -> None:
        """取消订阅（与真实 EventBus 一致）"""
        if pattern in self._subscribers:
            if handler in self._subscribers[pattern]:
                self._subscribers[pattern].remove(handler)
    
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


class PluginTestHarness:
    """插件测试工具，模拟插件加载和生命周期"""
    
    def __init__(self, bus: EventBusFixture):
        self.bus = bus
        self.plugin = None
    
    async def load_plugin(self, plugin_class: type,
                          config: dict = None) -> PluginInterface:
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


class TestFrameworkPlugin(PluginInterface):
    """测试框架插件。
    
    提供标准化的测试基础设施，所有插件测试使用统一基类和夹具。
    只提供测试工具，不参与业务逻辑。
    """
    
    def __init__(self):
        self.name = "test_framework"
        self.event_bus = None
        self.config = {}
    
    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化插件"""
        self.event_bus = event_bus
        self.config = config.get("test_framework", {})
    
    async def start(self) -> None:
        """启动插件"""
        pass
    
    async def pause(self) -> None:
        """暂停插件"""
        pass
    
    async def resume(self) -> None:
        """恢复插件"""
        pass
    
    async def stop(self) -> None:
        """停止插件"""
        pass
    
    async def cleanup(self) -> None:
        """清理资源"""
        pass
