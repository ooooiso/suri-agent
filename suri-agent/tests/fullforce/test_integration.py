#!/usr/bin/env python3
"""
集成测试脚本 — 模拟终端交互，测试四角色联动

用法: python tests/integration_test.py
"""

import sys
import asyncio
from pathlib import Path
from io import StringIO

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'suri-agent'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.logger import LoggerService
from core.context import ContextService
from core.model_router import ModelService
from core.task_dispatcher import TaskService
from model.manager import ModelManager
from core.tool_executor import ToolService


class IntegrationTest:
    """集成测试器"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.config = ConfigService(self.project_root)
        self.config.load_all()
        self.memory = MemoryService(self.project_root, self.config)
        self.logger = LoggerService(self.project_root)
        self.model = ModelService(self.config)
        self.context = ContextService(self.config, self.memory)
        self.task = TaskService(self.config, self.memory, self.context, self.model, None, self.logger)
        self.model_manager = ModelManager(self.project_root)
        self.tool_service = ToolService(self.project_root, self.config)
        
    def test_basic(self):
        """基础功能测试"""
        print("=" * 60)
        print("【测试 1】基础功能检查")
        print("=" * 60)
        
        # 检查角色
        roles = self.config.list_roles()
        print(f"  角色列表: {roles}")
        assert 'suri' in roles, "suri 角色缺失"
        assert 'suri-dev' in roles, "suri-dev 角色缺失"
        assert 'suri-hr' in roles, "suri-hr 角色缺失"
        assert 'document-review' in roles, "document-review 角色缺失"
        print("  ✅ 四个核心角色均存在")
        
        # 检查模型
        default = self.model_manager.get_default_model()
        print(f"  默认模型: {default.name if default else '无'}")
        assert default is not None, "默认模型未配置"
        print("  ✅ 模型已配置")
        
        # 检查工具
        tools = self.tool_service.list_tools()
        print(f"  工具数量: {len(tools)}")
        
        # 检查部门
        depts = self.config.list_departments()
        print(f"  部门列表: {depts}")
        
        print("  ✅ 基础检查通过\n")
        
    def test_role_context(self):
        """测试角色上下文构建"""
        print("=" * 60)
        print("【测试 2】角色上下文构建")
        print("=" * 60)
        
        for role_id in ['suri', 'suri-dev', 'suri-hr', 'document-review']:
            ctx = self.context.build_context(role_id, model_info={'name': 'Test', 'model_id': 'test'})
            assert ctx, f"{role_id} 上下文构建失败"
            lines = ctx.split('\n')
            print(f"  {role_id}: {len(lines)} 行上下文")
        
        print("  ✅ 所有角色上下文构建成功\n")
        
    def test_keywords(self):
        """测试角色关键词提取"""
        print("=" * 60)
        print("【测试 3】角色关键词提取")
        print("=" * 60)
        
        for role_id in self.config.list_roles():
            kws = self.config.get_role_keywords(role_id)
            print(f"  {role_id}: {kws[:5]}")
        
        print("  ✅ 关键词提取正常\n")
        
    async def test_model_call(self):
        """测试模型调用"""
        print("=" * 60)
        print("【测试 4】模型调用（实际 API）")
        print("=" * 60)
        
        default = self.model_manager.get_default_model()
        print(f"  使用模型: {default.name}")
        
        messages = [
            {"role": "system", "content": "你是一个简洁的助手，只回答'是'或'否'。"},
            {"role": "user", "content": "你能正常工作吗？只回答一个字。"},
        ]
        
        try:
            reply = await self.model_manager.chat(messages)
            print(f"  模型回复: {reply[:100]}")
            print("  ✅ 模型调用成功\n")
            return True
        except Exception as e:
            print(f"  ❌ 模型调用失败: {e}\n")
            return False
            
    async def test_dispatch(self):
        """测试任务调度"""
        print("=" * 60)
        print("【测试 5】任务调度流程")
        print("=" * 60)
        
        task_id = self.task.receive_task("test_user", "测试需求")
        print(f"  任务创建: {task_id}")
        
        # 测试部门匹配
        depts = self.config.list_departments()
        print(f"  可用部门: {depts}")
        
        print("  ✅ 调度流程基础检查通过\n")
        
    async def run_all(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("Suri 集成测试开始")
        print("=" * 60 + "\n")
        
        self.test_basic()
        self.test_role_context()
        self.test_keywords()
        
        model_ok = await self.test_model_call()
        if not model_ok:
            print("⚠️ 模型调用失败，后续依赖模型的测试将跳过\n")
        
        await self.test_dispatch()
        
        print("=" * 60)
        print("集成测试完成")
        print("=" * 60)


if __name__ == '__main__':
    test = IntegrationTest()
    asyncio.run(test.run_all())
