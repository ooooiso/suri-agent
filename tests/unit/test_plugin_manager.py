#!/usr/bin/env python3
"""PluginManager 单元测试。"""
import asyncio
import sys
import tempfile
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.event_bus.bus import EventBus
from agent_framework.plugin_manager.manager import PluginManager


class TestPluginManager(unittest.TestCase):
    """PluginManager 测试用例。"""

    def test_scan_plugins(self):
        """测试扫描插件目录。"""
        async def _test():
            bus = EventBus()
            await bus.start()

            project_root = Path(__file__).parent.parent.parent
            scan_dirs = [str(project_root / "agent_framework/plugins")]
            manager = PluginManager(bus, scan_dirs)
            manifests = manager._scan_plugins()

            # 验证扫描到核心插件
            self.assertIn("config_service", manifests)
            self.assertIn("log_service", manifests)
            self.assertIn("security_service", manifests)

            await bus.stop()

        asyncio.run(_test())

    def test_manifest_has_required_fields(self):
        """测试 manifest 包含必要字段。"""
        async def _test():
            bus = EventBus()
            await bus.start()

            project_root = Path(__file__).parent.parent.parent
            scan_dirs = [str(project_root / "agent_framework/plugins")]
            manager = PluginManager(bus, scan_dirs)
            manifests = manager._scan_plugins()

            for name, manifest in manifests.items():
                with self.subTest(plugin=name):
                    self.assertIn("name", manifest)
                    self.assertIn("version", manifest)
                    self.assertIn("type", manifest)

            await bus.stop()

        asyncio.run(_test())

    def test_topological_sort(self):
        """测试拓扑排序。"""
        async def _test():
            bus = EventBus()
            await bus.start()

            project_root = Path(__file__).parent.parent.parent
            scan_dirs = [str(project_root / "agent_framework/plugins")]
            manager = PluginManager(bus, scan_dirs)
            manifests = manager._scan_plugins()
            sorted_plugins = manager._topological_sort(manifests)

            # 验证所有插件都在排序结果中
            self.assertEqual(len(sorted_plugins), len(manifests))
            for name in manifests:
                self.assertIn(name, sorted_plugins)

            # 基础服务应该在接入层之前加载
            if all(p in sorted_plugins for p in ["config_service", "access"]):
                self.assertLess(
                    sorted_plugins.index("config_service"),
                    sorted_plugins.index("access"),
                    "config_service 应该在 access 之前加载",
                )

            await bus.stop()

        asyncio.run(_test())

    def test_ast_scan_safe(self):
        """测试 AST 扫描安全代码。"""
        async def _test():
            bus = EventBus()
            await bus.start()

            project_root = Path(__file__).parent.parent.parent
            scan_dirs = [str(project_root / "agent_framework/plugins")]
            manager = PluginManager(bus, scan_dirs)

            # 扫描所有插件的 plugin.py，验证安全
            for plugin_dir in (project_root / "agent_framework/plugins").iterdir():
                plugin_file = plugin_dir / "plugin.py"
                if plugin_file.exists():
                    result = manager._ast_scan(plugin_file)
                    self.assertTrue(
                        result,
                        f"AST scan failed for {plugin_file}",
                    )

            await bus.stop()

        asyncio.run(_test())

    def test_ast_scan_detects_forbidden_api(self):
        """测试 AST 扫描检测禁止 API。"""
        async def _test():
            bus = EventBus()
            await bus.start()

            project_root = Path(__file__).parent.parent.parent
            scan_dirs = [str(project_root / "agent_framework/plugins")]
            manager = PluginManager(bus, scan_dirs)

            # 创建包含危险代码的测试文件
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write("import os\nos.system('ls')\n")
                temp_path = Path(f.name)

            result = manager._ast_scan(temp_path)
            self.assertFalse(result, "AST scan should reject dangerous code")

            temp_path.unlink(missing_ok=True)
            await bus.stop()

        asyncio.run(_test())

    def test_ast_scan_safe_detects_eval(self):
        """测试 AST 扫描检测 eval。"""
        async def _test():
            bus = EventBus()
            await bus.start()

            project_root = Path(__file__).parent.parent.parent
            scan_dirs = [str(project_root / "agent_framework/plugins")]
            manager = PluginManager(bus, scan_dirs)

            # eval 检测
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write("eval('1+1')\n")
                temp_path = Path(f.name)

            result = manager._ast_scan(temp_path)
            self.assertFalse(result, "AST scan should reject eval")

            temp_path.unlink(missing_ok=True)
            await bus.stop()

        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()