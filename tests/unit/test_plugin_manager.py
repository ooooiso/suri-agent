#!/usr/bin/env python3
"""PluginManager 单元测试。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import unittest

from agent_framework.event_bus.bus import EventBus
from agent_framework.plugin_manager.manager import PluginManager
from shared.utils.event_types import Event, Priority


class TestPluginManager(unittest.TestCase):
    """PluginManager 测试用例。"""

    def test_scan_plugins(self):
        """测试插件扫描。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            
            project_root = Path(__file__).parent.parent.parent
            scan_dirs = [str(project_root / "plugins")]
            manager = PluginManager(bus, scan_dirs)
            
            manifests = manager._scan_plugins()
            
            # 验证扫描到了插件（suri_core 在 agent_framework/ 中，不由 PluginManager 扫描）
            self.assertIn("config_service", manifests)
            self.assertIn("llm_gateway", manifests)
            self.assertIn("code_tool", manifests)
            
            await bus.stop()
        
        asyncio.run(_test())

    def test_topological_sort(self):
        """测试依赖拓扑排序。"""
        async def _test():
            bus = EventBus()
            await bus.start()
            
            manager = PluginManager(bus, [])
            
            manifests = {
                "plugin_a": {"dependencies": ["plugin_c"]},
                "plugin_b": {"dependencies": []},
                "plugin_c": {"dependencies": ["plugin_b"]},
            }
            
            sorted_names = manager._topological_sort(manifests)
            
            # plugin_b 必须在 plugin_c 之前，plugin_c 必须在 plugin_a 之前
            b_idx = sorted_names.index("plugin_b")
            c_idx = sorted_names.index("plugin_c")
            a_idx = sorted_names.index("plugin_a")
            
            self.assertLess(b_idx, c_idx)
            self.assertLess(c_idx, a_idx)
            
            await bus.stop()
        
        asyncio.run(_test())

    def test_ast_scan_safe(self):
        """测试 AST 扫描通过安全代码。"""
        async def _test():
            manager = PluginManager(None, [])
            
            # 测试一个安全的文件
            safe_file = Path(__file__).parent.parent.parent / "shared" / "interfaces" / "plugin.py"
            result = manager._ast_scan(safe_file)
            self.assertTrue(result)
        
        asyncio.run(_test())

    def test_ast_scan_forbidden(self):
        """测试 AST 扫描检测危险代码。"""
        async def _test():
            manager = PluginManager(None, [])
            
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write("eval('1 + 1')\n")
                temp_file = f.name
            
            result = manager._ast_scan(Path(temp_file))
            self.assertFalse(result)
            
            Path(temp_file).unlink(missing_ok=True)
        
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
