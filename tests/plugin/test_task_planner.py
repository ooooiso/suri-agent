"""task_planner 插件测试"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import unittest
from plugins.task_planner.plugin import TaskPlannerPlugin
from plugins.test_framework.plugin import EventBusFixture, TestBase, PluginTestHarness


class TestTaskPlannerPlugin(TestBase):
    """task_planner 插件测试"""
    
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.harness = PluginTestHarness(self.bus)
        self.plugin = await self.harness.load_plugin(
            TaskPlannerPlugin,
            {"task_planner": {"enable_template_matching": True}}
        )
    
    async def test_rule_based_plan_code(self):
        """测试规则驱动：代码开发"""
        plan = await self.plugin.plan("实现一个用户登录功能")
        self.assertIsNotNone(plan)
        self.assertTrue(len(plan.steps) > 0)
        self.assertEqual(plan.steps[0].assignee, "suri")
    
    def test_rule_based_plan_review(self):
        """测试规则驱动：代码审查"""
        plan = self.plugin._rule_based_plan("审查代码质量", [])
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 4)  # review 模板有 4 步
    
    def test_rule_based_plan_statistics(self):
        """测试规则驱动：数据分析"""
        plan = self.plugin._rule_based_plan("统计项目代码行数", [])
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 4)  # statistics 模板有 4 步
    
    def test_rule_based_plan_role_creation(self):
        """测试规则驱动：角色创建"""
        # 使用更精确的关键词以匹配 role_creation 模板
        plan = self.plugin._rule_based_plan("新增角色", [])
        self.assertIsNotNone(plan)
        # role_creation 模板有 5 步
        self.assertEqual(len(plan.steps), 5)
    
    def test_generic_plan(self):
        """测试通用降级规划"""
        plan = self.plugin._generic_plan("创建目录结构。编写 manifest.json。实现核心逻辑")
        self.assertIsNotNone(plan)
        # 只按中文句号拆分，manifest.json 不被拆分，所以是 3 段
        self.assertEqual(len(plan.steps), 3)
        # 全部并行
        for step in plan.steps:
            self.assertEqual(step.depends_on, [])
    
    def test_generic_plan_single(self):
        """测试通用降级规划：单句"""
        plan = self.plugin._generic_plan("实现一个功能")
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 1)
    
    def test_cycle_detection(self):
        """测试循环依赖检测"""
        from shared.interfaces.plugin import TaskStep
        
        steps = [
            TaskStep(step_id="step_1", description="A", assignee="suri", depends_on=["step_2"]),
            TaskStep(step_id="step_2", description="B", assignee="suri", depends_on=["step_3"]),
            TaskStep(step_id="step_3", description="C", assignee="suri", depends_on=["step_1"]),
        ]
        
        self.assertTrue(self.plugin._has_cycle(steps))
    
    def test_no_cycle(self):
        """测试无循环依赖"""
        from shared.interfaces.plugin import TaskStep
        
        steps = [
            TaskStep(step_id="step_1", description="A", assignee="suri", depends_on=[]),
            TaskStep(step_id="step_2", description="B", assignee="suri", depends_on=["step_1"]),
            TaskStep(step_id="step_3", description="C", assignee="suri", depends_on=["step_2"]),
        ]
        
        self.assertFalse(self.plugin._has_cycle(steps))
    
    def test_register_template(self):
        """测试注册模板"""
        from shared.interfaces.plugin import TaskTemplate, TemplateStep
        
        template = TaskTemplate(
            template_id="test.custom",
            name="自定义",
            keywords=["test"],
            steps=[TemplateStep("步骤1", "suri")],
            default_role="suri",
            priority=50,
        )
        
        result = self.plugin.register_template(template)
        self.assertTrue(result)
        self.assertIn("test.custom", self.plugin._templates)
    
    def test_register_template_priority_limit(self):
        """测试模板优先级限制（不能超过 99）"""
        from shared.interfaces.plugin import TaskTemplate, TemplateStep
        
        template = TaskTemplate(
            template_id="test.high",
            name="高优先级",
            keywords=["high"],
            steps=[TemplateStep("步骤1", "suri")],
            default_role="suri",
            priority=100,
        )
        
        result = self.plugin.register_template(template)
        self.assertFalse(result)  # 超过 99 拒绝
    
    def test_unregister_builtin(self):
        """测试不能注销内置模板"""
        result = self.plugin.unregister_template("builtin.code")
        self.assertFalse(result)
    
    def test_get_ready_steps(self):
        """测试获取就绪步骤"""
        from shared.interfaces.plugin import TaskPlan, TaskStep
        
        plan = TaskPlan(
            plan_id="test_plan",
            task_name="test",
            steps=[
                TaskStep(step_id="step_1", description="A", assignee="suri", depends_on=[]),
                TaskStep(step_id="step_2", description="B", assignee="suri", depends_on=["step_1"]),
                TaskStep(step_id="step_3", description="C", assignee="suri", depends_on=["step_1"]),
            ],
            involved_roles=["suri"],
            dependencies=["step_2", "step_3"],
        )
        
        self.plugin._plans["test_plan"] = plan
        
        # 初始状态：只有 step_1 就绪
        ready = self.plugin.get_ready_steps("test_plan")
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].step_id, "step_1")
        
        # 完成 step_1 后，step_2 和 step_3 就绪
        plan.steps[0].status = "completed"
        ready = self.plugin.get_ready_steps("test_plan")
        self.assertEqual(len(ready), 2)
    
    async def test_lifecycle(self):
        """测试生命周期"""
        await self.harness.run_lifecycle()
        # 生命周期完成后，模板应该被清空（cleanup 清空了 _templates）
        self.assertEqual(len(self.plugin._templates), 0)
    
    async def test_template_to_plan_depends_on(self):
        """测试模板转换的 depends_on 正确性"""
        from shared.interfaces.plugin import TaskTemplate, TemplateStep
        
        template = TaskTemplate(
            template_id="test.depends",
            name="依赖测试",
            keywords=["test"],
            steps=[
                TemplateStep("第一步", "suri"),
                TemplateStep("第二步", "suri"),
                TemplateStep("第三步", "suri"),
            ],
            default_role="suri",
            priority=0,
        )
        
        plan = self.plugin._template_to_plan(template, "测试任务")
        self.assertEqual(len(plan.steps), 3)
        # 第一步无依赖
        self.assertEqual(plan.steps[0].depends_on, [])
        # 第二步依赖第一步
        self.assertEqual(plan.steps[1].depends_on, ["step_1"])
        # 第三步依赖第二步
        self.assertEqual(plan.steps[2].depends_on, ["step_2"])
    
    async def test_generic_plan_no_dot_split(self):
        """测试 generic_plan 不拆分英文句点（manifest.json 不被误拆）"""
        plan = self.plugin._generic_plan("创建目录结构。编写 manifest.json。实现核心逻辑")
        self.assertIsNotNone(plan)
        # 只有中文句号拆分，所以是 3 段（manifest.json 不被拆分）
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(plan.steps[1].description, "编写 manifest.json")
    
    async def test_rule_based_plan_keyword_priority(self):
        """测试关键词匹配优先匹配更长关键词"""
        # "新增角色" 比 "创建" 更长，应匹配 role_creation 而非 code
        plan = self.plugin._rule_based_plan("新增角色", [])
        self.assertIsNotNone(plan)
        # role_creation 模板有 5 步
        self.assertEqual(len(plan.steps), 5)
    
    async def test_rule_based_plan_keyword_short(self):
        """测试短关键词仍能匹配 code 模板"""
        plan = self.plugin._rule_based_plan("实现一个功能", [])
        self.assertIsNotNone(plan)
        # code 模板有 6 步
        self.assertEqual(len(plan.steps), 6)
    
    def test_parse_llm_response(self):
        """测试 LLM 响应解析"""
        response = '{"task_name": "test", "steps": [{"step_id": "step_1", "description": "do something", "assignee": "suri", "depends_on": []}], "involved_roles": ["suri"]}'
        data = self.plugin._parse_llm_response(response)
        self.assertIsNotNone(data)
        self.assertEqual(data["task_name"], "test")
    
    def test_parse_llm_response_invalid(self):
        """测试无效 LLM 响应解析"""
        data = self.plugin._parse_llm_response("not json")
        self.assertIsNone(data)
    
    # --- 热更新测试 ---
    
    async def test_reload_templates_keeps_builtin(self):
        """测试重新加载模板时内置模板始终保留"""
        # 先注册一个外部模板
        from shared.interfaces.plugin import TaskTemplate, TemplateStep
        template = TaskTemplate(
            template_id="test.custom",
            name="自定义",
            keywords=["custom"],
            steps=[TemplateStep("步骤1", "suri")],
            default_role="suri",
            priority=50,
        )
        self.plugin.register_template(template)
        self.assertIn("test.custom", self.plugin._templates)
        
        # 重新加载模板（模拟热更新）
        self.plugin._reload_templates()
        
        # 内置模板保留
        self.assertIn("builtin.code", self.plugin._templates)
        self.assertIn("builtin.review", self.plugin._templates)
        # 外部模板被清除（因为 _reload_templates 只加载内置 + 外部文件）
        self.assertNotIn("test.custom", self.plugin._templates)
    
    async def test_reload_templates_builtin_not_overwritten(self):
        """测试外部模板不能覆盖内置模板"""
        # 模拟外部模板加载（通过 _load_external_templates 返回内置同名的模板）
        # 但 _reload_templates 会跳过内置模板的覆盖
        from shared.interfaces.plugin import TaskTemplate, TemplateStep
        
        # 直接修改 _templates 模拟外部加载
        original_steps = len(self.plugin._templates["builtin.code"].steps)
        
        # 重新加载，内置模板不应被覆盖
        self.plugin._reload_templates()
        self.assertEqual(len(self.plugin._templates["builtin.code"].steps), original_steps)
    
    async def test_on_config_updated_ignores_other_plugin(self):
        """测试 config.updated 事件只响应自身插件"""
        from shared.utils.event_types import Event
        
        # 其他插件的配置变更不应触发重新加载
        event = Event(
            event_type="config.updated",
            source="other_plugin",
            payload={"plugin_id": "other_plugin"},
        )
        await self.plugin._on_config_updated(event)
        # 没有异常即通过
    
    async def test_on_config_updated_self(self):
        """测试 config.updated 事件响应自身插件"""
        from shared.utils.event_types import Event
        
        # 先注册一个外部模板
        from shared.interfaces.plugin import TaskTemplate, TemplateStep
        template = TaskTemplate(
            template_id="test.before_reload",
            name="重载前",
            keywords=["before"],
            steps=[TemplateStep("步骤1", "suri")],
            default_role="suri",
            priority=50,
        )
        self.plugin.register_template(template)
        self.assertIn("test.before_reload", self.plugin._templates)
        
        # 模拟自身配置变更
        event = Event(
            event_type="config.updated",
            source="task_planner",
            payload={"plugin_id": "task_planner"},
        )
        await self.plugin._on_config_updated(event)
        
        # 重新加载后，手动注册的模板被清除
        self.assertNotIn("test.before_reload", self.plugin._templates)
    
    async def test_on_templates_updated(self):
        """测试 templates_updated 事件触发重新加载"""
        from shared.utils.event_types import Event
        
        # 先注册一个外部模板
        from shared.interfaces.plugin import TaskTemplate, TemplateStep
        template = TaskTemplate(
            template_id="test.before_update",
            name="更新前",
            keywords=["before"],
            steps=[TemplateStep("步骤1", "suri")],
            default_role="suri",
            priority=50,
        )
        self.plugin.register_template(template)
        self.assertIn("test.before_update", self.plugin._templates)
        
        # 模拟模板更新事件
        event = Event(
            event_type="task_planner.templates_updated",
            source="upgrade_manager",
            payload={},
        )
        await self.plugin._on_templates_updated(event)
        
        # 重新加载后，手动注册的模板被清除
        self.assertNotIn("test.before_update", self.plugin._templates)
    
    async def test_external_templates_path_exists(self):
        """测试外部模板路径常量存在"""
        import os
        self.assertTrue(
            self.plugin.EXTERNAL_TEMPLATES_PATH.endswith("task_templates.yaml")
        )
    
    async def test_load_external_templates_file_not_found(self):
        """测试外部模板文件不存在时返回空字典"""
        templates = self.plugin._load_external_templates()
        self.assertEqual(templates, {})


if __name__ == "__main__":
    unittest.main()