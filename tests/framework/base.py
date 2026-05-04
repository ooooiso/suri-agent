"""测试框架基类 — 所有测试的共享基础设施。

提供：
- AsyncTestCase: 自动创建/销毁 EventBus 的异步测试基类
- 测试夹具加载
- 通用断言方法
"""

import asyncio
import unittest
from typing import Any, Dict, Optional

from agent_framework.event_bus.bus import EventBus
from agent_framework.shared.utils.event_types import Event, Priority


class AsyncTestCase(unittest.TestCase):
    """异步测试基类。

    自动创建 EventBus，提供 run_async() 辅助方法。
    子类只需定义 async def _test() 方法。
    """

    def setUp(self):
        self.bus = EventBus()
        self._events: list = []

    def run_async(self, coro):
        """运行异步协程。"""
        return asyncio.run(coro)

    async def start_bus(self):
        """启动 EventBus。"""
        await self.bus.start()

    async def stop_bus(self):
        """停止 EventBus。"""
        await self.bus.stop()

    def collect_events(self, event_type: str, timeout: float = 0.3) -> list:
        """收集指定类型的事件。

        注册一个临时 handler，发布事件后等待 timeout 秒收集。
        """
        collected = []

        async def handler(event):
            collected.append(event)

        self.bus.subscribe(event_type, handler)
        return collected

    def assertEventReceived(self, events: list, expected_type: str,
                            msg: Optional[str] = None):
        """断言事件列表包含指定类型的事件。"""
        types = [e.event_type for e in events]
        self.assertIn(expected_type, types, msg or f"Event {expected_type} not received")

    def assertEventPayload(self, event: Event, key: str, expected_value: Any,
                           msg: Optional[str] = None):
        """断言事件 payload 包含指定键值。"""
        actual = event.payload.get(key)
        self.assertEqual(
            actual, expected_value,
            msg or f"Payload[{key}] expected {expected_value!r}, got {actual!r}"
        )


class EventCollector:
    """事件收集器 — 在测试中收集特定事件。"""

    def __init__(self, bus: EventBus, event_type: str):
        self.bus = bus
        self.event_type = event_type
        self.events: list = []

    async def __aenter__(self):
        self.bus.subscribe(self.event_type, self._handler)
        return self

    async def __aexit__(self, *args):
        pass

    async def _handler(self, event: Event):
        self.events.append(event)

    def wait_for(self, count: int = 1, timeout: float = 0.5) -> bool:
        """等待收集到指定数量的事件。"""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.events) >= count:
                return True
            time.sleep(0.05)
        return len(self.events) >= count
