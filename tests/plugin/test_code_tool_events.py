"""code_tool 插件事件处理测试。"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.event_bus.bus import EventBus
from agent_framework.plugins.execution.code_tool.plugin import CodeToolPlugin
from agent_framework.plugins.execution.code_tool.writer import write_file, append_file, create_file
from agent_framework.shared.utils.event_types import Event, Priority


class TestCodeToolEvents(unittest.TestCase):
    """CodeToolPlugin 事件处理测试。"""

    def setUp(self):
        self.plugin = CodeToolPlugin()

    def test_tool_call_read_file(self):
        """测试 tool.call read_file 事件。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})

            results = []
            async def handler(event):
                results.append(event)

            bus.subscribe("tool.result", handler)

            event = Event(
                event_type="tool.call",
                source="test",
                payload={
                    "tool_name": "code_tool.read_file",
                    "params": {"path": "agent_framework/shared/utils/event_types.py"},
                },
                priority=Priority.NORMAL,
            )
            await self.plugin._on_tool_call(event)
            await asyncio.sleep(0.1)

            self.assertEqual(len(results), 1)
            result = results[0].payload["result"]
            self.assertIn("content", result)
            self.assertIn("class Priority", result["content"])

            await bus.stop()

        asyncio.run(_test())

    def test_tool_call_list_dir(self):
        """测试 tool.call list_dir 事件。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})

            results = []
            async def handler(event):
                results.append(event)

            bus.subscribe("tool.result", handler)

            event = Event(
                event_type="tool.call",
                source="test",
                payload={
                    "tool_name": "code_tool.list_dir",
                    "params": {"path": "agent_framework/shared"},
                },
                priority=Priority.NORMAL,
            )
            await self.plugin._on_tool_call(event)
            await asyncio.sleep(0.1)

            self.assertEqual(len(results), 1)
            result = results[0].payload["result"]
            self.assertIn("items", result)

            await bus.stop()

        asyncio.run(_test())

    def test_tool_call_unknown(self):
        """测试未知 tool_name 不产生结果。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            await self.plugin.init(bus, {})

            results = []
            async def handler(event):
                results.append(event)

            bus.subscribe("tool.result", handler)

            event = Event(
                event_type="tool.call",
                source="test",
                payload={
                    "tool_name": "code_tool.unknown",
                    "params": {},
                },
                priority=Priority.NORMAL,
            )
            await self.plugin._on_tool_call(event)
            await asyncio.sleep(0.1)

            self.assertEqual(len(results), 0)

            await bus.stop()

        asyncio.run(_test())


class TestCodeToolWriter(unittest.TestCase):
    """code_tool writer 模块测试。"""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_file(self):
        """测试写入文件。"""
        result = write_file(self.temp_dir, "test.txt", "hello world")
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("action"), "write")

        # 验证文件内容
        content = (self.temp_dir / "test.txt").read_text(encoding="utf-8")
        self.assertEqual(content, "hello world")

    def test_append_file(self):
        """测试追加文件。"""
        write_file(self.temp_dir, "test.txt", "line1\n")
        result = append_file(self.temp_dir, "test.txt", "line2\n")
        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("action"), "append")

        content = (self.temp_dir / "test.txt").read_text(encoding="utf-8")
        self.assertEqual(content, "line1\nline2\n")

    def test_create_file_new(self):
        """测试创建新文件。"""
        result = create_file(self.temp_dir, "new.txt", "new content")
        self.assertTrue(result.get("success"))

    def test_create_file_exists(self):
        """测试创建已存在的文件返回错误。"""
        write_file(self.temp_dir, "exists.txt", "content")
        result = create_file(self.temp_dir, "exists.txt", "new content")
        self.assertIn("error_code", result)
        self.assertEqual(result["error_code"], 4005)

    def test_write_outside_project(self):
        """测试写入项目外路径返回错误。"""
        result = write_file(self.temp_dir, "../outside.txt", "content")
        self.assertIn("error_code", result)
        self.assertEqual(result["error_code"], 4001)

    def test_write_forbidden_dir(self):
        """测试写入禁止目录返回错误。"""
        result = write_file(self.temp_dir, "agent_framework/core/plugin.py", "content")
        self.assertIn("error_code", result)
        self.assertEqual(result["error_code"], 4002)

    def test_write_needs_approval(self):
        """测试写入需要审批的目录标记。"""
        result = write_file(self.temp_dir, "agent_framework/plugins/test.py", "content")
        self.assertTrue(result.get("needs_approval"))


if __name__ == "__main__":
    unittest.main()