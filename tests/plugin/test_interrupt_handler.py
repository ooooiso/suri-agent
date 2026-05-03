"""interrupt_handler 插件测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import unittest
from plugins.interrupt_handler.plugin import InterruptHandlerPlugin
from plugins.test_framework.plugin import EventBusFixture, TestBase, PluginTestHarness


class TestInterruptHandlerPlugin(TestBase):
    """interrupt_handler 插件测试"""
    
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.harness = PluginTestHarness(self.bus)
        self.plugin = await self.harness.load_plugin(InterruptHandlerPlugin)
    
    def test_classify_missing_tool(self):
        """测试分类：缺少工具"""
        reason_type = self.plugin._classify_reason("缺少工具，无法执行操作")
        self.assertEqual(reason_type, "missing_tool")
        
        reason_type = self.plugin._classify_reason("need tool not available")
        self.assertEqual(reason_type, "missing_tool")
    
    def test_classify_knowledge_gap(self):
        """测试分类：知识不足"""
        reason_type = self.plugin._classify_reason("我不会这个，不了解相关知识")
        self.assertEqual(reason_type, "knowledge_gap")
        
        reason_type = self.plugin._classify_reason("I don't know how to do this")
        self.assertEqual(reason_type, "knowledge_gap")
    
    def test_classify_permission_denied(self):
        """测试分类：权限不足"""
        reason_type = self.plugin._classify_reason("权限不足，拒绝访问")
        self.assertEqual(reason_type, "permission_denied")
        
        reason_type = self.plugin._classify_reason("403 forbidden")
        self.assertEqual(reason_type, "permission_denied")
    
    def test_classify_dependency_failed(self):
        """测试分类：依赖失败"""
        reason_type = self.plugin._classify_reason("依赖服务调用失败")
        self.assertEqual(reason_type, "dependency_failed")
        
        reason_type = self.plugin._classify_reason("connection refused")
        self.assertEqual(reason_type, "dependency_failed")
    
    def test_classify_timeout(self):
        """测试分类：超时"""
        reason_type = self.plugin._classify_reason("操作超时，无响应")
        self.assertEqual(reason_type, "timeout")
        
        reason_type = self.plugin._classify_reason("request timeout")
        self.assertEqual(reason_type, "timeout")
    
    def test_classify_resource_exhausted(self):
        """测试分类：资源耗尽"""
        reason_type = self.plugin._classify_reason("内存不足，OOM")
        self.assertEqual(reason_type, "resource_exhausted")
        
        reason_type = self.plugin._classify_reason("rate limit exceeded 429")
        self.assertEqual(reason_type, "resource_exhausted")
    
    def test_classify_unknown(self):
        """测试分类：未知"""
        reason_type = self.plugin._classify_reason("一些完全无关的错误信息")
        self.assertEqual(reason_type, "unknown")
    
    async def test_handle_missing_tool(self):
        """测试处理缺少工具"""
        result = await self.plugin._handle_missing_tool("agent_001", "缺少工具")
        self.assertEqual(result.action, "escalate")
        self.assertEqual(result.reason, "missing_tool")
        self.assertEqual(result.escalation_target, "suri")
    
    async def test_handle_knowledge_gap(self):
        """测试处理知识不足"""
        result = await self.plugin._handle_knowledge_gap("agent_001", "不会")
        self.assertEqual(result.action, "escalate")
        self.assertEqual(result.reason, "knowledge_gap")
    
    async def test_handle_permission_denied(self):
        """测试处理权限不足"""
        result = await self.plugin._handle_permission_denied("agent_001", "权限不足")
        self.assertEqual(result.action, "escalate")
        self.assertEqual(result.reason, "permission_denied")
    
    async def test_handle_dependency_failed_auto_retry(self):
        """测试处理依赖失败（自动重试）"""
        self.plugin.config["enable_auto_retry"] = True
        self.plugin.config["auto_retry_types"] = ["dependency_failed"]
        self.plugin.config["max_auto_retries"] = 2
        
        result = await self.plugin._handle_dependency_failed("agent_001", "依赖失败")
        self.assertEqual(result.action, "retry")
        self.assertEqual(self.plugin._retry_counts.get("agent_001"), 1)
    
    async def test_handle_dependency_failed_wait(self):
        """测试处理依赖失败（等待用户决策）"""
        self.plugin.config["enable_auto_retry"] = True
        self.plugin.config["auto_retry_types"] = ["dependency_failed"]
        self.plugin.config["max_auto_retries"] = 0  # 不允许重试
        
        result = await self.plugin._handle_dependency_failed("agent_002", "依赖失败")
        self.assertEqual(result.action, "wait")
    
    async def test_handle_timeout_auto_retry(self):
        """测试处理超时（自动重试）"""
        self.plugin.config["enable_auto_retry"] = True
        self.plugin.config["auto_retry_types"] = ["timeout"]
        self.plugin.config["max_auto_retries"] = 2
        
        result = await self.plugin._handle_timeout("agent_003", "超时")
        self.assertEqual(result.action, "retry")
    
    async def test_handle_timeout_wait(self):
        """测试处理超时（等待用户决策）"""
        self.plugin.config["enable_auto_retry"] = True
        self.plugin.config["auto_retry_types"] = ["timeout"]
        self.plugin.config["max_auto_retries"] = 0
        
        result = await self.plugin._handle_timeout("agent_004", "超时")
        self.assertEqual(result.action, "wait")
    
    async def test_handle_resource_exhausted(self):
        """测试处理资源耗尽"""
        result = await self.plugin._handle_resource_exhausted("agent_001", "内存不足")
        self.assertEqual(result.action, "wait")
    
    async def test_handle_unknown(self):
        """测试处理未知类型"""
        result = await self.plugin._handle_unknown("agent_001", "未知错误")
        self.assertEqual(result.action, "escalate")
        self.assertEqual(result.escalation_target, "suri")
    
    async def test_handle(self):
        """测试完整处理流程"""
        result = await self.plugin.handle("agent_001", "权限不足，拒绝访问")
        self.assertEqual(result.handled, True)
        self.assertEqual(result.reason, "permission_denied")
    
    def test_should_auto_retry_enabled(self):
        """测试自动重试判断（启用）"""
        self.plugin.config["enable_auto_retry"] = True
        self.plugin.config["auto_retry_types"] = ["timeout", "dependency_failed"]
        self.plugin.config["max_auto_retries"] = 2
        
        self.assertTrue(self.plugin._should_auto_retry("timeout", 0))
        self.assertTrue(self.plugin._should_auto_retry("dependency_failed", 1))
        self.assertFalse(self.plugin._should_auto_retry("timeout", 3))  # 超过最大重试次数
        self.assertFalse(self.plugin._should_auto_retry("missing_tool", 0))  # 不在自动重试类型中
    
    def test_should_auto_retry_disabled(self):
        """测试自动重试判断（禁用）"""
        self.plugin.config["enable_auto_retry"] = False
        self.assertFalse(self.plugin._should_auto_retry("timeout", 0))
    
    async def test_on_agent_blocked(self):
        """测试 Agent 受阻事件处理"""
        from shared.utils.event_types import Event
        
        event = Event(
            event_type="agent.blocked",
            source="test",
            payload={
                "agent_id": "agent_001",
                "reason": "权限不足",
                "block_type": "permission",
            }
        )
        
        await self.plugin._on_agent_blocked(event)
        
        # 应该发布 interrupt.handled 事件
        handled_events = self.bus.get_published_events("interrupt.handled")
        self.assertEqual(len(handled_events), 1)
        self.assertEqual(handled_events[0].payload["action"], "escalate")
    
    async def test_on_task_failed_auto_retry(self):
        """测试任务失败事件处理（自动重试）"""
        from shared.utils.event_types import Event
        
        self.plugin.config["enable_auto_retry"] = True
        self.plugin.config["auto_retry_types"] = ["timeout"]
        self.plugin.config["max_auto_retries"] = 2
        
        event = Event(
            event_type="task.failed",
            source="test",
            payload={
                "task_id": "task_001",
                "error_message": "操作超时",
                "retry_count": 0,
                "agent_id": "agent_001",
            }
        )
        
        await self.plugin._on_task_failed(event)
        
        # 应该发布 retry_requested 事件
        retry_events = self.bus.get_published_events("interrupt.retry_requested")
        self.assertEqual(len(retry_events), 1)
    
    async def test_on_task_failed_user_decision(self):
        """测试任务失败事件处理（需要用户决策）"""
        from shared.utils.event_types import Event
        
        self.plugin.config["enable_auto_retry"] = True
        self.plugin.config["auto_retry_types"] = ["timeout"]
        self.plugin.config["max_auto_retries"] = 0  # 不允许重试
        
        event = Event(
            event_type="task.failed",
            source="test",
            payload={
                "task_id": "task_001",
                "error_message": "操作超时",
                "retry_count": 0,
                "agent_id": "agent_001",
            }
        )
        
        await self.plugin._on_task_failed(event)
        
        # 应该发布 user_decision_needed 事件
        decision_events = self.bus.get_published_events("interrupt.user_decision_needed")
        self.assertEqual(len(decision_events), 1)
    
    async def test_on_user_decision_continue(self):
        """测试用户决策：继续"""
        from shared.utils.event_types import Event
        
        # 先创建一个待处理决策
        self.plugin._pending_decisions["decision_001"] = {
            "agent_id": "agent_001",
            "task_id": "task_001",
            "reason": "超时",
        }
        
        event = Event(
            event_type="user.decision",
            source="test",
            payload={
                "decision_id": "decision_001",
                "choice": "continue",
            }
        )
        
        await self.plugin._on_user_decision(event)
        
        # 应该发布 retry_requested 事件
        retry_events = self.bus.get_published_events("interrupt.retry_requested")
        self.assertEqual(len(retry_events), 1)
        # 决策记录应该被清理
        self.assertNotIn("decision_001", self.plugin._pending_decisions)
    
    async def test_on_user_decision_cancel(self):
        """测试用户决策：取消"""
        from shared.utils.event_types import Event
        
        self.plugin._pending_decisions["decision_002"] = {
            "agent_id": "agent_001",
            "task_id": "task_001",
            "reason": "超时",
        }
        
        event = Event(
            event_type="user.decision",
            source="test",
            payload={
                "decision_id": "decision_002",
                "choice": "cancel",
            }
        )
        
        await self.plugin._on_user_decision(event)
        
        # 应该发布 cancelled 事件
        cancel_events = self.bus.get_published_events("interrupt.cancelled")
        self.assertEqual(len(cancel_events), 1)
    
    async def test_lifecycle(self):
        """测试生命周期"""
        await self.harness.run_lifecycle()
    
    # --- 热更新测试 ---
    
    async def test_reload_keywords_keeps_builtin(self):
        """测试重新加载关键词时内置关键词保留"""
        # 修改关键词
        self.plugin._keywords["missing_tool"] = ["自定义关键词"]
        
        # 重新加载
        self.plugin._reload_keywords()
        
        # 内置关键词恢复
        self.assertIn("缺少工具", self.plugin._keywords["missing_tool"])
        self.assertIn("need tool", self.plugin._keywords["missing_tool"])
    
    async def test_reload_keywords_external_overrides_builtin(self):
        """测试外部关键词覆盖内置关键词"""
        # 模拟外部加载返回自定义关键词
        original_load = self.plugin._load_external_keywords
        
        def mock_load():
            return {"missing_tool": ["外部关键词"]}
        
        self.plugin._load_external_keywords = mock_load
        self.plugin._reload_keywords()
        
        # 外部关键词覆盖了内置
        self.assertEqual(self.plugin._keywords["missing_tool"], ["外部关键词"])
        
        # 恢复
        self.plugin._load_external_keywords = original_load
        self.plugin._reload_keywords()
    
    async def test_detect_keyword_conflicts(self):
        """测试关键词冲突检测"""
        # 模拟两个类型有相同关键词
        self.plugin._keywords = {
            "type_a": ["冲突词"],
            "type_b": ["冲突词"],
        }
        
        # 应该打印告警但不抛出异常
        self.plugin._detect_keyword_conflicts()
        # 没有异常即通过
    
    async def test_detect_keyword_conflicts_no_conflict(self):
        """测试无冲突时不告警"""
        self.plugin._keywords = {
            "type_a": ["关键词A"],
            "type_b": ["关键词B"],
        }
        
        self.plugin._detect_keyword_conflicts()
        # 没有异常即通过
    
    async def test_on_config_updated_ignores_other_plugin(self):
        """测试 config.updated 事件只响应自身插件"""
        from shared.utils.event_types import Event
        
        # 先修改关键词
        self.plugin._keywords["missing_tool"] = ["被修改"]
        
        # 其他插件的配置变更
        event = Event(
            event_type="config.updated",
            source="other_plugin",
            payload={"plugin_id": "other_plugin"},
        )
        await self.plugin._on_config_updated(event)
        
        # 关键词不应被恢复（因为被忽略了）
        self.assertEqual(self.plugin._keywords["missing_tool"], ["被修改"])
    
    async def test_on_config_updated_self(self):
        """测试 config.updated 事件响应自身插件"""
        from shared.utils.event_types import Event
        
        # 先修改关键词
        self.plugin._keywords["missing_tool"] = ["被修改"]
        
        # 自身配置变更
        event = Event(
            event_type="config.updated",
            source="interrupt_handler",
            payload={"plugin_id": "interrupt_handler"},
        )
        await self.plugin._on_config_updated(event)
        
        # 关键词被恢复
        self.assertIn("缺少工具", self.plugin._keywords["missing_tool"])
    
    async def test_on_keywords_updated(self):
        """测试 keywords_updated 事件触发重新加载"""
        from shared.utils.event_types import Event
        
        # 先修改关键词
        self.plugin._keywords["missing_tool"] = ["被修改"]
        
        event = Event(
            event_type="interrupt_handler.keywords_updated",
            source="upgrade_manager",
            payload={},
        )
        await self.plugin._on_keywords_updated(event)
        
        # 关键词被恢复
        self.assertIn("缺少工具", self.plugin._keywords["missing_tool"])
    
    async def test_external_keywords_path_exists(self):
        """测试外部关键词路径常量存在"""
        self.assertTrue(
            self.plugin.EXTERNAL_KEYWORDS_PATH.endswith("interrupt_keywords.yaml")
        )
    
    async def test_load_external_keywords_file_not_found(self):
        """测试外部关键词文件不存在时返回空字典"""
        keywords = self.plugin._load_external_keywords()
        self.assertEqual(keywords, {})


if __name__ == "__main__":
    unittest.main()