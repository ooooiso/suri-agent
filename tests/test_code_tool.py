#!/usr/bin/env python3
"""code_tool 单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

from plugins.code_tool.plugin import CodeToolPlugin


class TestCodeTool(unittest.TestCase):
    """CodeTool 测试用例。"""

    def setUp(self):
        self.plugin = CodeToolPlugin()
        # 手动设置项目根目录（模拟 init 的效果）
        self.plugin._project_root = Path(__file__).parent.parent

    def test_list_dir(self):
        """测试列出目录。"""
        result = self.plugin.list_dir("shared")
        self.assertIn("items", result)
        self.assertIsInstance(result["items"], list)
        # shared 目录下应该有 interfaces 和 utils
        names = [item["name"] for item in result["items"]]
        self.assertIn("interfaces", names)
        self.assertIn("utils", names)

    def test_read_file(self):
        """测试读取文件。"""
        result = self.plugin.read_file("shared/utils/event_types.py")
        self.assertIn("content", result)
        self.assertIn("class Priority", result["content"])
        self.assertIn("total_lines", result)
        self.assertGreater(result["total_lines"], 0)

    def test_read_file_with_offset(self):
        """测试带偏移读取文件。"""
        result = self.plugin.read_file("shared/utils/event_types.py", offset=0, limit=5)
        self.assertEqual(result["returned_lines"], 5)
        self.assertEqual(result["offset"], 0)

    def test_read_file_not_found(self):
        """测试读取不存在的文件。"""
        result = self.plugin.read_file("nonexistent.py")
        self.assertIn("error_code", result)

    def test_grep(self):
        """测试文本搜索。"""
        result = self.plugin.grep("class Event", path="shared")
        self.assertIn("results", result)
        self.assertGreater(len(result["results"]), 0)
        # 应该找到 event_types.py 中的 class Event
        files = [r["file"] for r in result["results"]]
        self.assertTrue(any("event_types.py" in f for f in files))

    def test_stat_project(self):
        """测试项目统计。"""
        result = self.plugin.stat_project("shared")
        self.assertIn("total_files", result)
        self.assertIn("total_lines", result)
        self.assertIn("by_extension", result)
        self.assertGreater(result["total_files"], 0)


if __name__ == "__main__":
    unittest.main()
