#!/usr/bin/env python3
"""security_service 单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

from plugins.security_service.plugin import SecurityServicePlugin


class TestSecurityService(unittest.TestCase):
    """SecurityService 测试用例。"""

    def setUp(self):
        self.plugin = SecurityServicePlugin()
        # 手动设置项目根目录
        self.plugin._project_root = Path(__file__).parent.parent

    def test_can_read_allowed(self):
        """测试允许读取的路径。"""
        self.assertTrue(self.plugin.can_read("shared/utils/event_types.py"))
        self.assertTrue(self.plugin.can_read("plugins/"))
        self.assertTrue(self.plugin.can_read("roles/"))

    def test_can_read_forbidden(self):
        """测试禁止读取的路径。"""
        self.assertFalse(self.plugin.can_read("/etc/passwd"))
        self.assertFalse(self.plugin.can_read("C:/Windows/system32"))

    def test_can_write_allowed(self):
        """测试允许写入的路径。"""
        self.assertTrue(self.plugin.can_write("plugins/test.py"))
        self.assertTrue(self.plugin.can_write("tests/test.py"))
        self.assertTrue(self.plugin.can_write("roles/suri/Soul.md"))

    def test_can_write_forbidden(self):
        """测试禁止写入的路径。"""
        # 核心框架不可写
        self.assertFalse(self.plugin.can_write("agent_framework/event_bus/bus.py"))
        self.assertFalse(self.plugin.can_write("shared/interfaces/plugin.py"))
        self.assertFalse(self.plugin.can_write("main.py"))
        # 系统目录不可写
        self.assertFalse(self.plugin.can_write("/etc/hosts"))


if __name__ == "__main__":
    unittest.main()
