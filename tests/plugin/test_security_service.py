#!/usr/bin/env python3
"""security_service 单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.plugins.security_service.plugin import SecurityServicePlugin


class TestSecurityService(unittest.TestCase):
    """SecurityService 测试用例。"""

    def setUp(self):
        self.plugin = SecurityServicePlugin()
        self.plugin._project_root = Path(__file__).parent.parent.parent

    def test_can_read_allowed(self):
        self.assertTrue(self.plugin.can_read("agent_framework/shared/utils/event_types.py"))
        self.assertTrue(self.plugin.can_read("agent_framework/plugins/"))
        self.assertTrue(self.plugin.can_read("roles/"))

    def test_can_read_forbidden(self):
        self.assertFalse(self.plugin.can_read("/etc/passwd"))
        self.assertFalse(self.plugin.can_read("C:/Windows/system32"))

    def test_can_write_allowed(self):
        self.assertTrue(self.plugin.can_write("agent_framework/plugins/test.py"))
        self.assertTrue(self.plugin.can_write("tests/test.py"))
        self.assertTrue(self.plugin.can_write("roles/suri/Soul.md"))

    def test_can_write_forbidden(self):
        self.assertFalse(self.plugin.can_write("agent_framework/event_bus/bus.py"))
        self.assertFalse(self.plugin.can_write("shared/interfaces/plugin.py"))
        self.assertFalse(self.plugin.can_write("main.py"))
        self.assertFalse(self.plugin.can_write("/etc/hosts"))


if __name__ == "__main__":
    unittest.main()
