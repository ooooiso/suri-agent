"""agent_registry 插件测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import unittest
from plugins.agent_registry.plugin import AgentRegistryPlugin
from plugins.test_framework.plugin import EventBusFixture, TestBase, PluginTestHarness
from shared.interfaces.plugin import TaskStep


class TestAgentRegistryPlugin(TestBase):
    """agent_registry 插件测试"""
    
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.harness = PluginTestHarness(self.bus)
        self.plugin = await self.harness.load_plugin(AgentRegistryPlugin)
    
    def test_create_agent(self):
        """测试创建 Agent"""
        agent = self.plugin.create_agent(
            task_id="task_001",
            task_name="测试任务",
            role_id="suri",
            user_id="test_user",
        )
        
        self.assertIsNotNone(agent)
        self.assertEqual(agent.task_name, "测试任务")
        self.assertEqual(agent.role_id, "suri")
        self.assertEqual(agent.status, "planning")
        self.assertTrue(agent.agent_id.startswith("suri_"))
    
    def test_create_agent_with_steps(self):
        """测试创建带步骤的 Agent"""
        steps = [
            TaskStep(step_id="step_1", description="步骤1", assignee="suri"),
            TaskStep(step_id="step_2", description="步骤2", assignee="suri", depends_on=["step_1"]),
        ]
        
        agent = self.plugin.create_agent(
            task_id="task_002",
            task_name="多步骤任务",
            role_id="suri",
            user_id="test_user",
            steps=steps,
        )
        
        self.assertEqual(len(agent.steps), 2)
        self.assertEqual(agent.progress, "0/2")
    
    def test_get_agent(self):
        """测试获取 Agent"""
        agent = self.plugin.create_agent(
            task_id="task_003",
            task_name="获取测试",
            role_id="suri",
            user_id="test_user",
        )
        
        found = self.plugin.get_agent(agent.agent_id)
        self.assertIsNotNone(found)
        self.assertEqual(found.agent_id, agent.agent_id)
    
    def test_get_agent_not_found(self):
        """测试获取不存在的 Agent"""
        found = self.plugin.get_agent("nonexistent")
        self.assertIsNone(found)
    
    def test_list_agents(self):
        """测试列出 Agent"""
        self.plugin.create_agent(task_id="t1", task_name="任务1", role_id="suri", user_id="user1")
        self.plugin.create_agent(task_id="t2", task_name="任务2", role_id="suri", user_id="user1")
        self.plugin.create_agent(task_id="t3", task_name="任务3", role_id="suri", user_id="user2")
        
        agents = self.plugin.list_agents()
        self.assertEqual(len(agents), 3)
        
        user1_agents = self.plugin.list_agents(user_id="user1")
        self.assertEqual(len(user1_agents), 2)
    
    def test_list_agents_by_status(self):
        """测试按状态列出 Agent"""
        agent = self.plugin.create_agent(
            task_id="t1", task_name="任务1", role_id="suri", user_id="user1"
        )
        self.plugin.update_agent_status(agent.agent_id, "completed")
        
        completed = self.plugin.list_agents(status="completed")
        self.assertEqual(len(completed), 1)
        
        planning = self.plugin.list_agents(status="planning")
        self.assertEqual(len(planning), 0)
    
    def test_update_agent_status(self):
        """测试更新 Agent 状态"""
        agent = self.plugin.create_agent(
            task_id="t1", task_name="任务1", role_id="suri", user_id="user1"
        )
        
        result = self.plugin.update_agent_status(agent.agent_id, "running")
        self.assertTrue(result)
        self.assertEqual(self.plugin.get_agent(agent.agent_id).status, "running")
    
    def test_update_agent_status_not_found(self):
        """测试更新不存在的 Agent 状态"""
        result = self.plugin.update_agent_status("nonexistent", "running")
        self.assertFalse(result)
    
    def test_update_step_status(self):
        """测试更新步骤状态"""
        steps = [TaskStep(step_id="step_1", description="步骤1", assignee="suri")]
        agent = self.plugin.create_agent(
            task_id="t1", task_name="任务1", role_id="suri", user_id="user1",
            steps=steps,
        )
        
        result = self.plugin.update_step_status(agent.agent_id, "step_1", "completed", "成功")
        self.assertTrue(result)
        
        updated = self.plugin.get_agent(agent.agent_id)
        self.assertEqual(updated.steps[0].status, "completed")
        self.assertEqual(updated.steps[0].result, "成功")
        self.assertEqual(updated.progress, "1/1")
    
    def test_update_step_status_not_found(self):
        """测试更新不存在的步骤状态"""
        agent = self.plugin.create_agent(
            task_id="t1", task_name="任务1", role_id="suri", user_id="user1",
        )
        result = self.plugin.update_step_status(agent.agent_id, "nonexistent", "completed")
        self.assertFalse(result)
    
    def test_get_agent_progress(self):
        """测试获取 Agent 进度"""
        steps = [
            TaskStep(step_id="step_1", description="步骤1", assignee="suri"),
            TaskStep(step_id="step_2", description="步骤2", assignee="suri"),
        ]
        agent = self.plugin.create_agent(
            task_id="t1", task_name="任务1", role_id="suri", user_id="user1",
            steps=steps,
        )
        
        self.assertEqual(self.plugin.get_agent_progress(agent.agent_id), "0/2")
        
        self.plugin.update_step_status(agent.agent_id, "step_1", "completed")
        self.assertEqual(self.plugin.get_agent_progress(agent.agent_id), "1/2")
    
    def test_build_chat_messages(self):
        """测试构建聊天消息"""
        steps = [TaskStep(step_id="step_1", description="分析需求", assignee="suri")]
        agent = self.plugin.create_agent(
            task_id="t1", task_name="实现登录功能", role_id="suri", user_id="user1",
            steps=steps,
        )
        
        messages = self.plugin.build_chat_messages(agent.agent_id, "请开始")
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("实现登录功能", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "请开始")
    
    def test_build_chat_messages_not_found(self):
        """测试构建不存在的 Agent 消息"""
        messages = self.plugin.build_chat_messages("nonexistent", "请开始")
        self.assertEqual(messages, [])
    
    def test_agent_id_format(self):
        """测试 Agent ID 格式"""
        agent = self.plugin.create_agent(
            task_id="t1", task_name="任务1", role_id="suri", user_id="user1",
        )
        
        parts = agent.agent_id.split("_")
        self.assertEqual(parts[0], "suri")
        self.assertEqual(len(parts), 3)  # role_timestamp_random
    
    async def test_lifecycle(self):
        """测试生命周期"""
        await self.harness.run_lifecycle()


if __name__ == "__main__":
    unittest.main()
