"""memory_service 插件测试 — 完全独立测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import unittest
from pathlib import Path
from agent_framework.plugins.capability.memory_service.plugin import MemoryServicePlugin
from agent_framework.plugins.extension.test_framework.plugin import EventBusFixture, TestBase, PluginTestHarness


class TestMemoryServicePlugin(TestBase):
    """memory_service 插件测试 — 每个测试使用独立临时目录和插件实例"""
    
    def _make_plugin(self, test_name: str):
        """创建带独立 runtime 目录的插件实例"""
        plugin = MemoryServicePlugin()
        plugin._runtime_root = Path(self.tmp_dir) / test_name
        return plugin
    
    
    
    async def _run_test_with_plugin(self, test_name: str, test_func):
        """用独立插件实例运行测试函数"""
        self._plugin = self._make_plugin(test_name)
        try:
            await test_func(self._plugin)
        finally:
            await self._plugin.cleanup()
            self._plugin = None
    
    # --- 事实记忆 ---
    
    async def test_set_and_get_fact(self):
        async def _test(plugin):
            plugin.set_fact("role1", "fmt", "Markdown", confidence=0.9)
            self.assertEqual(plugin.get_fact("role1", "fmt"), "Markdown")
        await self._run_test_with_plugin("set_get", _test)
    
    async def test_get_fact_not_found(self):
        async def _test(plugin):
            self.assertIsNone(plugin.get_fact("role2", "nonexistent"))
        await self._run_test_with_plugin("get_nf", _test)
    
    async def test_delete_fact(self):
        async def _test(plugin):
            plugin.set_fact("role3", "k", "v")
            self.assertTrue(plugin.delete_fact("role3", "k"))
            self.assertIsNone(plugin.get_fact("role3", "k"))
        await self._run_test_with_plugin("del", _test)
    
    async def test_delete_fact_not_found(self):
        async def _test(plugin):
            self.assertFalse(plugin.delete_fact("role4", "nonexistent"))
        await self._run_test_with_plugin("del_nf", _test)
    
    async def test_list_facts(self):
        async def _test(plugin):
            for i in range(3):
                plugin.set_fact("role5", f"k{i}", f"v{i}")
            self.assertEqual(len(plugin.list_facts("role5")), 3)
        await self._run_test_with_plugin("list", _test)
    
    async def test_set_fact_upsert(self):
        async def _test(plugin):
            plugin.set_fact("role6", "key", "old")
            plugin.set_fact("role6", "key", "new")
            self.assertEqual(plugin.get_fact("role6", "key"), "new")
        await self._run_test_with_plugin("upsert", _test)
    
    async def test_store_complex_value(self):
        async def _test(plugin):
            cv = {"name": "cfg", "items": [1, 2], "nested": {"k": "v"}}
            plugin.set_fact("role7", "cfg", cv)
            self.assertEqual(plugin.get_fact("role7", "cfg"), cv)
        await self._run_test_with_plugin("complex", _test)
    
    # --- 经验 ---
    
    async def test_store_and_get_experience(self):
        async def _test(plugin):
            eid = plugin.store_experience("role8", "review", "ctx", [{"t": "v"}], "ok", 0.8)
            self.assertIsNotNone(eid)
            exps = plugin.get_experiences("role8", "review")
            self.assertEqual(len(exps), 1)
            self.assertEqual(exps[0]["task_type"], "review")
        await self._run_test_with_plugin("exp", _test)
    
    # --- 模式 ---
    
    async def test_store_and_get_pattern(self):
        async def _test(plugin):
            pid = plugin.store_pattern("role9", "pattern1", confidence=0.7, source="src")
            self.assertIsNotNone(pid)
            pats = plugin.get_patterns("role9", min_confidence=0.5)
            self.assertEqual(len(pats), 1)
            self.assertEqual(pats[0]["pattern"], "pattern1")
        await self._run_test_with_plugin("pat", _test)
    
    async def test_pattern_dedup(self):
        async def _test(plugin):
            pid1 = plugin.store_pattern("role10", "相同模式")
            pid2 = plugin.store_pattern("role10", "相同模式")
            self.assertEqual(pid1, pid2)
            pats = plugin.get_patterns("role10")
            self.assertEqual(len(pats), 1)
            self.assertEqual(pats[0]["evidence_count"], 2)
        await self._run_test_with_plugin("dedup", _test)
    
    # --- 消息 ---
    
    async def test_store_and_get_messages(self):
        async def _test(plugin):
            mid = plugin.store_message("role11", "t1", "u", "a", "body")
            self.assertIsNotNone(mid)
            msgs = plugin.get_messages("role11", task_id="t1")
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0]["sender"], "u")
            self.assertEqual(msgs[0]["body"], "body")
        await self._run_test_with_plugin("msg", _test)
    
    # --- 洞察 ---
    
    async def test_add_and_get_insights(self):
        async def _test(plugin):
            fp = plugin.add_insight("role12", "Title", "Body text", ["tag1"])
            self.assertTrue(fp.endswith(".md"))
            insights = plugin.get_insights("role12", days=30)
            self.assertEqual(len(insights), 1)
            self.assertEqual(insights[0]["title"], "Title")
        await self._run_test_with_plugin("insight", _test)
    
    # --- 遗忘 ---
    
    async def test_forget_old_memories(self):
        async def _test(plugin):
            plugin.set_fact("role13", "old", "v", confidence=0.2)
            stats = plugin.forget_old_memories("role13", threshold_days=0, confidence_threshold=0.3)
            self.assertIn("facts_deleted", stats)
        await self._run_test_with_plugin("forget", _test)
    
    # --- 健康检查 ---
    
    async def test_health_check(self):
        async def _test(plugin):
            plugin.set_fact("role14", "k", "v")
            result = plugin.health_check("role14")
            self.assertEqual(result["status"], "pass")
            self.assertIn("tables", result)
            self.assertIn("db_size_bytes", result)
        await self._run_test_with_plugin("hc", _test)
    
    async def test_health_check_invalid_role(self):
        async def _test(plugin):
            with self.assertRaises(ValueError):
                plugin._get_role_db_path("../etc/passwd")
        await self._run_test_with_plugin("hc_inv", _test)
    
    # --- 跨角色隔离 ---
    
    async def test_cross_role_isolation(self):
        async def _test(plugin):
            plugin.set_fact("role_a", "k", "va")
            plugin.set_fact("role_b", "k", "vb")
            self.assertEqual(plugin.get_fact("role_a", "k"), "va")
            self.assertEqual(plugin.get_fact("role_b", "k"), "vb")
        await self._run_test_with_plugin("iso", _test)
    
    # --- 生命周期 ---
    
    async def test_lifecycle(self):
        async def _test(plugin):
            await plugin.pause()
            await plugin.resume()
            await plugin.stop()
            await plugin.cleanup()
        plugin = self._make_plugin("lifecycle")
        await plugin.init(EventBusFixture(), {})
        await _test(plugin)


if __name__ == "__main__":
    unittest.main()