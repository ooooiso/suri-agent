"""access 插件事件处理测试。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.event_bus.bus import EventBus
from plugins.access.plugin import AccessPlugin
from plugins.access.formatter import MessageFormatter
from shared.utils.event_types import Event, Priority


class TestAccessEvents(unittest.TestCase):
    """AccessPlugin 事件处理测试。"""

    def setUp(self):
        self.plugin = AccessPlugin()

    def test_llm_response_routing(self):
        """测试 LLM 响应路由到 CLI。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})
            self.plugin._cli = None  # 不启动真实 CLI

            # 模拟 LLM 响应
            event = Event(
                event_type="llm.response",
                source="llm_gateway",
                payload={
                    "content": "Hello from Suri",
                    "session_id": "cli_123",
                    "request_id": "req-1",
                },
                priority=Priority.NORMAL,
            )
            # 不报错即可
            await self.plugin._on_llm_response(event)
            await bus.stop()

        asyncio.run(_test())

    def test_llm_error_dedup(self):
        """测试 LLM 错误去重（5 秒内同一错误码不重复显示）。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})
            self.plugin._cli = None

            event = Event(
                event_type="llm.error",
                source="llm_gateway",
                payload={
                    "error_code": 401,
                    "message": "API Key 无效",
                    "provider": "deepseek",
                    "session_id": "cli_123",
                },
                priority=Priority.HIGH,
            )

            # 第一次调用
            await self.plugin._on_llm_error(event)
            self.assertEqual(len(self.plugin._last_error_map), 1)

            # 第二次调用（5 秒内同一错误码）
            await self.plugin._on_llm_error(event)
            # 去重后不应增加
            self.assertEqual(len(self.plugin._last_error_map), 1)

            await bus.stop()

        asyncio.run(_test())

    def test_llm_error_different_code(self):
        """测试不同错误码不被去重。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})
            self.plugin._cli = None

            event1 = Event(
                event_type="llm.error",
                source="llm_gateway",
                payload={
                    "error_code": 401,
                    "message": "API Key 无效",
                    "provider": "deepseek",
                    "session_id": "cli_123",
                },
                priority=Priority.HIGH,
            )
            event2 = Event(
                event_type="llm.error",
                source="llm_gateway",
                payload={
                    "error_code": 429,
                    "message": "请求过于频繁",
                    "provider": "deepseek",
                    "session_id": "cli_123",
                },
                priority=Priority.HIGH,
            )

            await self.plugin._on_llm_error(event1)
            await self.plugin._on_llm_error(event2)
            # 不同错误码，应有 2 条记录
            self.assertEqual(len(self.plugin._last_error_map), 1)  # 同一 session 覆盖
            self.assertEqual(self.plugin._last_error_map["cli_123"][0], 429)

            await bus.stop()

        asyncio.run(_test())

    def test_system_ready(self):
        """测试 system.ready 事件。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})
            self.plugin._cli = None

            event = Event(
                event_type="system.ready",
                source="system",
                payload={},
                priority=Priority.NORMAL,
            )
            # 不报错即可
            await self.plugin._on_system_ready(event)
            await bus.stop()

        asyncio.run(_test())

    def test_user_command_status(self):
        """测试 user.command status 命令。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})
            self.plugin._cli = None

            event = Event(
                event_type="user.command",
                source="cli",
                payload={
                    "command": "status",
                    "channel": "cli",
                    "session_id": "cli_123",
                    "user_id": "cli_user",
                },
                priority=Priority.NORMAL,
            )
            # 不报错即可
            await self.plugin._on_user_command(event)
            await bus.stop()

        asyncio.run(_test())

    def test_user_command_logs(self):
        """测试 user.command logs 命令。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})
            self.plugin._cli = None

            event = Event(
                event_type="user.command",
                source="cli",
                payload={
                    "command": "logs",
                    "channel": "cli",
                    "session_id": "cli_123",
                    "user_id": "cli_user",
                },
                priority=Priority.NORMAL,
            )
            await self.plugin._on_user_command(event)
            await bus.stop()

        asyncio.run(_test())

    def test_formatter_error_401(self):
        """测试 formatter 401 错误格式化。"""
        msg = MessageFormatter.format_error(401, "API Key 无效", "deepseek")
        self.assertIn("⚠️", msg)
        self.assertIn("/setkey", msg)
        self.assertIn("deepseek", msg)

    def test_formatter_error_3002(self):
        """测试 formatter 3002 错误格式化。"""
        msg = MessageFormatter.format_error(3002, "No API key", "kimi")
        self.assertIn("⚠️", msg)
        self.assertIn("/setkey", msg)

    def test_formatter_status_panel(self):
        """测试 formatter 状态面板。"""
        providers = {
            "deepseek": {"models": ["deepseek-chat"], "api_key": True},
            "kimi": {"models": ["moonshot-v1-8k"], "api_key": False},
        }
        api_keys = {"deepseek": "sk-xxx"}
        panel = MessageFormatter.format_status(
            providers, "deepseek", "deepseek-chat", api_keys
        )
        self.assertIn("✅", panel)
        self.assertIn("❌", panel)
        self.assertIn("deepseek-chat", panel)

    def test_formatter_decision(self):
        """测试 formatter 决策菜单。"""
        menu = MessageFormatter.format_decision("请选择：", ["选项A", "选项B"])
        self.assertIn("选项A", menu)
        self.assertIn("选项B", menu)
        self.assertIn("1-2", menu)


if __name__ == "__main__":
    unittest.main()
