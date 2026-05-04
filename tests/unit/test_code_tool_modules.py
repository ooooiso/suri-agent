#!/usr/bin/env python3
"""code_tool 模块单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.plugins.code_tool.reader import read_file
from agent_framework.plugins.code_tool.explorer import list_dir
from agent_framework.plugins.code_tool.search import grep
from agent_framework.plugins.code_tool.stats import stat_project


PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestReader(unittest.TestCase):
    """reader.py 测试。"""

    def test_read_file(self):
        result = read_file(PROJECT_ROOT, "agent_framework/shared/utils/event_types.py")
        self.assertIn("content", result)
        self.assertIn("class Priority", result["content"])
        self.assertGreater(result["total_lines"], 0)

    def test_read_file_with_offset(self):
        result = read_file(PROJECT_ROOT, "agent_framework/shared/utils/event_types.py", offset=0, limit=5)
        self.assertEqual(result["returned_lines"], 5)

    def test_read_file_not_found(self):
        result = read_file(PROJECT_ROOT, "nonexistent.py")
        self.assertIn("error_code", result)


class TestExplorer(unittest.TestCase):
    """explorer.py 测试。"""

    def test_list_dir(self):
        result = list_dir(PROJECT_ROOT, "agent_framework/shared")
        self.assertIn("items", result)
        names = [item["name"] for item in result["items"]]
        self.assertIn("interfaces", names)
        self.assertIn("utils", names)


class TestSearch(unittest.TestCase):
    """search.py 测试。"""

    def test_grep(self):
        result = grep(PROJECT_ROOT, "class Event", path="agent_framework/shared")
        self.assertIn("results", result)
        self.assertGreater(len(result["results"]), 0)


class TestStats(unittest.TestCase):
    """stats.py 测试。"""

    def test_stat_project(self):
        result = stat_project(PROJECT_ROOT, "agent_framework/shared")
        self.assertIn("total_files", result)
        self.assertGreater(result["total_files"], 0)


if __name__ == "__main__":
    unittest.main()