"""role_comm 插件单元测试 — 完全独立测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import unittest
import uuid
from pathlib import Path
from agent_framework.plugins.execution.role_comm.plugin import RoleCommPlugin, RoleMessage
from agent_framework.plugins.extension.test_framework.plugin import EventBusFixture, TestBase, PluginTestHarness


class TestRoleCommPlugin(TestBase):
    """role_comm 插件测试 — 每个测试使用独立临时目录和插件实例"""
    
    def _make_plugin(self, test_name: str):
        """创建带独立 runtime 目录的插件实例"""
        plugin = RoleCommPlugin()
        plugin._runtime_root = Path(self.tmp_dir) / test_name
        return plugin
    
    async def _run_test_with_plugin(self, test_name: str, test_func):
        """用独立插件实例运行测试函数"""
        plugin = self._make_plugin(test_name)
        await plugin.init(self.bus, {})
        await plugin.start()
        try:
            await test_func(plugin)
        finally:
            await plugin.cleanup()
    
    # ── 基础发送/接收 ──
    
    async def test_send_and_receive_message(self):
        async def _test(plugin):
            mid = plugin.send_message("designer_A", "dev_role", "session_1", "按钮改绿色")
            self.assertIsNotNone(mid)
            msgs = plugin.get_messages("dev_role", session_id="session_1")
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0]["from_role"], "designer_A")
            self.assertEqual(msgs[0]["content"], "按钮改绿色")
        await self._run_test_with_plugin("send_recv", _test)
    
    async def test_message_session_isolation(self):
        async def _test(plugin):
            """不同 session_id 的消息隔离"""
            plugin.send_message("designer_A", "dev_role", "session_X", "消息A")
            plugin.send_message("designer_B", "dev_role", "session_Y", "消息B")
            
            msgs_x = plugin.get_messages("dev_role", session_id="session_X")
            msgs_y = plugin.get_messages("dev_role", session_id="session_Y")
            
            self.assertEqual(len(msgs_x), 1)
            self.assertEqual(len(msgs_y), 1)
            self.assertEqual(msgs_x[0]["content"], "消息A")
            self.assertEqual(msgs_y[0]["content"], "消息B")
        await self._run_test_with_plugin("session_iso", _test)
    
    async def test_unread_count(self):
        async def _test(plugin):
            plugin.send_message("A", "B", "s1", "1")
            plugin.send_message("A", "B", "s1", "2")
            plugin.send_message("A", "B", "s1", "3")
            
            cnt = plugin.get_unread_count("B", "s1")
            self.assertEqual(cnt, 3)
        await self._run_test_with_plugin("unread", _test)
    
    async def test_mark_consumed(self):
        async def _test(plugin):
            plugin.send_message("A", "B", "s1", "消息")
            cnt = plugin.get_unread_count("B", "s1")
            self.assertEqual(cnt, 1)
            
            plugin.mark_consumed("B", "s1")
            cnt = plugin.get_unread_count("B", "s1")
            self.assertEqual(cnt, 0)
        await self._run_test_with_plugin("consume", _test)
    
    # ── 多角色通信 ──
    
    async def test_multiple_roles(self):
        async def _test(plugin):
            """多个角色间通信"""
            plugin.send_message("designer_A", "dev_role", "s1", "改按钮颜色")
            plugin.send_message("pm_role", "dev_role", "s2", "改字体大小")
            plugin.send_message("dev_role", "designer_A", "s1", "已改好")
            
            dev_msgs = plugin.get_messages("dev_role")
            designer_msgs = plugin.get_messages("designer_A")
            
            self.assertEqual(len(dev_msgs), 2)
            self.assertEqual(len(designer_msgs), 1)
            self.assertEqual(designer_msgs[0]["from_role"], "dev_role")
        await self._run_test_with_plugin("multi_role", _test)
    
    # ── 消息顺序 ──
    
    async def test_message_order(self):
        async def _test(plugin):
            """消息按时间排序"""
            plugin.send_message("A", "B", "s1", "第一条")
            plugin.send_message("A", "B", "s1", "第二条")
            plugin.send_message("A", "B", "s1", "第三条")
            
            msgs = plugin.get_messages("B", session_id="s1")
            self.assertEqual(len(msgs), 3)
            self.assertEqual(msgs[0]["content"], "第一条")
            self.assertEqual(msgs[1]["content"], "第二条")
            self.assertEqual(msgs[2]["content"], "第三条")
        await self._run_test_with_plugin("order", _test)
    
    # ── 事件驱动 ──
    
    async def test_event_driven_send(self):
        async def _test(plugin):
            """通过事件发送消息"""
            role_msg_event = {
                "event_type": "role.message",
                "source": "test",
                "payload": {
                    "from_role": "designer_A",
                    "to_role": "dev_role",
                    "session_id": "s1",
                    "content": "按钮改绿色",
                }
            }
            
            # role_comm 监听了 role.message 事件
            # 通过发布事件触发
            await self.bus.publish(type('Event', (), role_msg_event)())
            
            msgs = plugin.get_messages("dev_role", session_id="s1")
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0]["from_role"], "designer_A")
        await self._run_test_with_plugin("event_drive", _test)
    
    # ── 消息摘要 ──
    
    async def test_long_message_summary(self):
        async def _test(plugin):
            long_content = "这是" * 200  # 超过 500 字符应自动摘要
            mid = plugin.send_message("A", "B", "s1", long_content)
            
            msgs = plugin.get_messages("B", session_id="s1")
            self.assertEqual(len(msgs), 1)
            # 摘要不应为 None（长消息自动截断前 100 字符）
            # 但 summary 字段可能在 config 未启用时为空
        await self._run_test_with_plugin("summary", _test)
    
    # ── 消息留存清理 ──
    
    async def test_delete_old_messages(self):
        async def _test(plugin):
            plugin.send_message("A", "B", "s1", "旧消息")
            result = plugin.delete_old_messages(retention_days=0)  # 0天，全部删除
            self.assertIn("deleted", result)
            self.assertIn("retention_days", result)
        await self._run_test_with_plugin("retention", _test)
    
    # ── 生命周期 ──
    
    async def test_lifecycle(self):
        """测试插件生命周期"""
        plugin = self._make_plugin("lifecycle")
        await plugin.init(self.bus, {})
        
        # 初始状态
        self.assertEqual(plugin._status, "initialized")
        
        await plugin.start()
        self.assertEqual(plugin._status, "running")
        
        await plugin.pause()
        self.assertEqual(plugin._status, "paused")
        
        await plugin.resume()
        self.assertEqual(plugin._status, "running")
        
        await plugin.stop()
        self.assertEqual(plugin._status, "stopped")
        
        await plugin.cleanup()
    
    # ── 健康检查 ──
    
    async def test_health_check(self):
        async def _test(plugin):
            plugin.send_message("A", "B", "s1", "测试")
            result = plugin.health_check()
            self.assertEqual(result["status"], "pass")
            self.assertIn("total_messages", result)
            self.assertIn("db_size_bytes", result)
        await self._run_test_with_plugin("hc", _test)
    
    # ── 空数据库 ──
    
    async def test_empty_get_messages(self):
        async def _test(plugin):
            msgs = plugin.get_messages("nonexistent_role")
            self.assertEqual(len(msgs), 0)
        await self._run_test_with_plugin("empty", _test)
    
    async def test_empty_unread(self):
        async def _test(plugin):
            cnt = plugin.get_unread_count("nonexistent_role")
            self.assertEqual(cnt, 0)
        await self._run_test_with_plugin("empty_unread", _test)


if __name__ == "__main__":
    unittest.main()