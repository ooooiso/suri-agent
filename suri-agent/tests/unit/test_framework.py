#!/usr/bin/env python3
"""
框架机制测试 — 不调用模型，纯本地验证

测试方向：
- D. 工具权限边界
- E. 规则摘要动态生成
- F. 上下文注入完整性
- G. 任务状态机
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'suri-agent'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from core.context import ContextService
from core.tool_executor import ToolService
from core.model_router import ModelService


class FrameworkTest:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.config = ConfigService(self.project_root)
        self.config.load_all()
        self.memory = MemoryService(self.project_root, self.config)
        self.context = ContextService(self.config, self.memory)
        self.model = ModelService(self.config)
        self.tool_service = ToolService(self.project_root, self.config)

    def test_d_tool_permissions(self):
        """场景D：工具权限边界"""
        print("\n" + "=" * 60)
        print("【场景D】工具权限边界测试")
        print("=" * 60)

        test_cases = [
            # (role_id, tool_id, expected, reason)
            ('suri', 'file_read', True, 'public 工具，所有角色可用'),
            ('suri-dev', 'file_write', True, 'maintainer 类型角色自动获得 maintainer 工具'),
            ('suri-hr', 'file_write', True, 'Soul 中 tools 字段显式授权'),
            ('document-review', 'file_write', False, '非 maintainer 类型，Soul 未显式授权'),
            ('suri', 'shell_exec', False, 'suri-dev 专属工具'),
            ('suri-dev', 'shell_exec', True, 'suri-dev 专属工具，permission == role_id'),
        ]

        for role_id, tool_id, expected, reason in test_cases:
            result = self.tool_service._can_use(role_id, tool_id)
            status = "✅" if result == expected else "❌"
            print(f"  {status} {role_id} + {tool_id}: {result} (期望 {expected}) — {reason}")

    def test_e_rule_summary(self):
        """场景E：规则摘要动态生成"""
        print("\n" + "=" * 60)
        print("【场景E】规则摘要动态生成测试")
        print("=" * 60)

        summary = self.context._get_rule_summary()
        lines = summary.strip().split('\n')
        print(f"  规则摘要行数: {len(lines)}")
        print(f"  前5行:\n    " + "\n    ".join(lines[:5]))

        # 验证是否包含已知规则的 docstring 内容
        has_doc_sync = '文档同步' in summary or 'doc_sync' in summary.lower()
        has_tool_sync = '工具同步' in summary or 'tool_sync' in summary.lower()

        print(f"  包含文档同步规则: {'✅' if has_doc_sync else '❌'}")
        print(f"  包含工具同步规则: {'✅' if has_tool_sync else '❌'}")

    def test_f_context_completeness(self):
        """场景F：上下文注入完整性"""
        print("\n" + "=" * 60)
        print("【场景F】上下文注入完整性测试")
        print("=" * 60)

        model_info = {'name': 'TestModel', 'model_id': 'test-001', 'provider': 'test'}
        ctx = self.context.build_context('suri-dev', current_task={'task_id': 't1', 'requirement': 'test'}, model_info=model_info)

        sections = {
            '身份': '## 你的身份' in ctx,
            '规则': '## 你必须遵守的规则' in ctx,
            '文件权限': '## 你的文件权限' in ctx,
            '经验': '## 你的经验总结' in ctx,
            '记忆': '## 相关记忆' in ctx,
            '工具': '## 你可用的工具' in ctx,
            '模型信息': 'TestModel' in ctx,
            '任务': '## 当前任务' in ctx,
        }

        for name, present in sections.items():
            print(f"  {'✅' if present else '❌'} 包含 [{name}] 部分")

        # 验证 suri 角色有额外的组织记忆
        suri_ctx = self.context.build_context('suri', model_info=model_info)
        has_org_memory = '## 组织共享记忆' in suri_ctx
        print(f"  {'✅' if has_org_memory else '❌'} suri 角色包含 [组织共享记忆]")

    def test_g_task_state_machine(self):
        """场景G：任务状态机"""
        print("\n" + "=" * 60)
        print("【场景G】任务状态机测试")
        print("=" * 60)

        from core.task_dispatcher import TaskService
        from infrastructure.logger import LoggerService
        logger = LoggerService(self.project_root)
        task_svc = TaskService(self.config, self.memory, self.context, self.model, None, logger)

        task_id = task_svc.receive_task('test_user', '测试状态流转')
        print(f"  任务创建: {task_id}")

        # 检查初始状态
        task = self.memory.get_task('suri', task_id)
        if task:
            print(f"  初始状态: {task.get('status', 'unknown')}")
        else:
            print(f"  ❌ 任务未找到")

        # 更新状态
        self.memory.update_task_status('suri', task_id, 'in_progress')
        task = self.memory.get_task('suri', task_id)
        print(f"  更新后状态: {task.get('status', 'unknown')}")

        self.memory.update_task_status('suri', task_id, 'completed')
        task = self.memory.get_task('suri', task_id)
        print(f"  完成状态: {task.get('status', 'unknown')}")

    def run_all(self):
        print("\n" + "=" * 60)
        print("框架机制测试开始（纯本地，无模型调用）")
        print("=" * 60)

        self.test_d_tool_permissions()
        self.test_e_rule_summary()
        self.test_f_context_completeness()
        self.test_g_task_state_machine()

        print("\n" + "=" * 60)
        print("框架机制测试完成")
        print("=" * 60 + "\n")


if __name__ == '__main__':
    test = FrameworkTest()
    test.run_all()
