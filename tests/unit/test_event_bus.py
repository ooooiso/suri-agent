#!/usr/bin/env python3
"""EventBus 单元测试。"""
import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.event_bus.bus import EventBus
from shared.utils.event_types import Event, Priority


class TestEventBus(unittest.TestCase):
    """EventBus 测试用例。"""

    def test_publish_subscribe(self):
        """测试发布-订阅基本流程。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            
            received = []
            async def handler(event):
                received.append(event)
            
            bus.subscribe("test.event", handler)
            event = Event(event_type="test.event", source="test", payload={"msg": "hello"})
            await bus.publish(event)
            await asyncio.sleep(0.2)
            
            self.assertEqual(len(received), 1)
            self.assertEqual(received[0].payload["msg"], "hello")
            
            await bus.stop()
        
        asyncio.run(_test())

    def test_wildcard_subscription(self):
        """测试通配符订阅。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            
            received = []
            async def handler(event):
                received.append(event.event_type)
            
            bus.subscribe("system.*", handler)
            await bus.publish(Event(event_type="system.start", source="test", priority=Priority.HIGH))
            await bus.publish(Event(event_type="system.ready", source="test", priority=Priority.HIGH))
            await asyncio.sleep(0.2)
            
            self.assertEqual(len(received), 2)
            self.assertIn("system.start", received)
            self.assertIn("system.ready", received)
            
            await bus.stop()
        
        asyncio.run(_test())

    def test_priority_ordering(self):
        """测试优先级排序。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            
            received = []
            async def handler(event):
                received.append(event.payload["order"])
            
            bus.subscribe("test.priority", handler)
            
            # 先发布 NORMAL，再 HIGH
            await bus.publish(Event(
                event_type="test.priority", source="test",
                payload={"order": 1}, priority=Priority.NORMAL
            ))
            await bus.publish(Event(
                event_type="test.priority", source="test",
                payload={"order": 2}, priority=Priority.HIGH
            ))
            
            await asyncio.sleep(0.3)
            
            # HIGH 应该先被处理
            self.assertEqual(received[0], 2)
            
            await bus.stop()
        
        asyncio.run(_test())

    def test_event_persistence(self):
        """测试事件持久化到 SQLite。"""
        async def _test():
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
                db_path = f.name
            
            # 初始化数据库表
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT,
                    source TEXT,
                    target TEXT,
                    payload TEXT,
                    priority TEXT,
                    timestamp TEXT,
                    consumed INTEGER
                )
            """)
            conn.commit()
            conn.close()
            
            bus = EventBus(db_path=db_path)
            await bus.start()
            
            event = Event(
                event_type="test.persist", source="test",
                payload={"data": "test"}, priority=Priority.CRITICAL
            )
            await bus.publish(event)
            await asyncio.sleep(0.2)
            
            # 验证数据库中有记录
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM events WHERE event_type = 'test.persist'")
            count = cursor.fetchone()[0]
            conn.close()
            
            self.assertGreaterEqual(count, 1)
            
            await bus.stop()
            Path(db_path).unlink(missing_ok=True)
        
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
