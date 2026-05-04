#!/usr/bin/env python3
"""code_tool 插件集成测试。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.event_bus.bus import EventBus
from agent_framework.plugins.code_tool.plugin import CodeToolPlugin
from agent_framework.shared.utils.event_types import Event, Priority


class TestCodeToolPlugin(unittest.TestCase):
    """CodeToolPlugin 事件处理测试。"""

    def setUp(self):
        self.plugin = CodeToolPlugin()

    def test_plugin_init(self):
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})
            self.assertIsNotNone(self.plugin._project_root)
            await bus.stop()
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
