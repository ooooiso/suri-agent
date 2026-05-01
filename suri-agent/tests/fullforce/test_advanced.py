#!/usr/bin/env python3
"""
高级测试 — 多轮对话记忆、能力边界、学习经验

所有角色能力通过第三方大模型实现。
"""

import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'suri-agent'))

from infrastructure.config import ConfigService
from infrastructure.memory import MemoryService
from infrastructure.logger import LoggerService
from core.context import ContextService
from core.model_router import ModelService
from core.task_dispatcher import TaskService
from model.manager import ModelManager


class AdvancedTest:
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
        self.user_id = "test_user"

    # ─────────── 场景A：多轮对话记忆 ───────────

    async def test_multi_turn_memory(self):
        """测试角色是否能记住之前的对话上下文"""
        print("\n" + "=" * 60)
        print("【场景A】多轮对话记忆测试")
        print("=" * 60)

        task_id = self.task.receive_task(self.user_id, "系统启动时报 ModuleNotFoundError")
        print(f"[系统] 任务创建: {task_id}")

        # 第一轮：用户提出问题
        round1_input = "系统启动时报 ModuleNotFoundError: No module named 'importlib'"
        print(f"\n[用户 Round 1] {round1_input}")

        result1 = await self._run_role_turn(task_id, 'suri-dev', round1_input)
        print(f"[suri-dev Round 1] {result1[:300]}...")

        # 第二轮：用户追问（不重复问题，只追问细节）
        round2_input = "我刚才说的那个错误，是在 tool_executor.py 里出现的，具体怎么修？"
        print(f"\n[用户 Round 2] {round2_input}")

        # 关键测试点：第二轮上下文应包含第一轮的对话
        result2 = await self._run_role_turn(task_id, 'suri-dev', round2_input)
        print(f"[suri-dev Round 2] {result2[:300]}...")

        # 验证：第二轮回复中是否提到了第一轮的上下文
        mentions_first_round = 'importlib' in result2.lower() or 'module' in result2.lower()
        if mentions_first_round:
            print("\n  ✅ 第二轮回复引用了第一轮的上下文（记忆有效）")
        else:
            print("\n  ⚠️ 第二轮回复未明显引用第一轮上下文（可能记忆未生效或模型未使用）")

        # 第三轮：更进一步的追问
        round3_input = "按你说的加了 import 之后还有问题，是不是路径也不对？"
        print(f"\n[用户 Round 3] {round3_input}")
        result3 = await self._run_role_turn(task_id, 'suri-dev', round3_input)
        print(f"[suri-dev Round 3] {result3[:300]}...")

        print("\n  多轮对话记忆测试完成")

    async def _run_role_turn(self, task_id, role_id, text):
        """执行角色的一轮对话（保存消息 + 调用模型）"""
        # 保存用户消息
        self.memory.save_message(
            role_id,
            message_id=f"msg_{task_id[:8]}_user_{hash(text) % 10000}",
            task_id=task_id,
            sender='user',
            receiver=role_id,
            body={'type': 'task', 'content': text}
        )

        default_model = self.model_manager.get_default_model()
        model_info = {
            'name': default_model.name,
            'model_id': default_model.model_id,
            'provider': default_model.provider,
        }

        current_task = {'task_id': task_id, 'requirement': text}
        role_prompt = self.context.build_context(role_id, current_task=current_task, model_info=model_info)
        role_prompt += (
            f"\n\n---\n\n"
            f"当前任务来自用户，请直接给出专业的处理结果。\n"
            f"任务内容：{text}\n\n"
            f"要求：用简洁的中文回复，直接输出结果。"
        )

        messages = [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": text},
        ]

        try:
            result = await self.model_manager.chat(messages)
        except Exception as e:
            return f"[错误] 模型调用失败: {e}"

        # 保存角色回复
        self.memory.save_message(
            role_id,
            message_id=f"msg_{task_id[:8]}_{role_id}_{hash(result) % 10000}",
            task_id=task_id,
            sender=role_id,
            receiver='user',
            body={'type': 'response', 'content': result}
        )

        return result

    # ─────────── 场景B：角色能力边界（越权拒绝） ───────────

    async def test_role_boundary(self):
        """测试角色是否会拒绝越权请求"""
        print("\n" + "=" * 60)
        print("【场景B】角色能力边界测试（越权拒绝）")
        print("=" * 60)

        test_cases = [
            ('suri-dev', "帮我写一封情书给女朋友", "非技术请求"),
            ('suri-hr', "帮我排查一个内存泄漏的Bug，在 Python 多线程里", "技术请求"),
            ('document-review', "帮我写一个登录页面的 HTML 代码", "开发请求"),
        ]

        for role_id, request, category in test_cases:
            print(f"\n  测试: {role_id} 收到 {category}")
            print(f"  请求: {request}")

            result = await self._run_role_turn(f"boundary_{role_id}", role_id, request)
            print(f"  回复: {result[:200]}...")

            # 判断角色是否拒绝
            refusal_markers = ['不属于', '不在', '无法', '不能', '不负责', '交给', '建议', '请找']
            accepted_markers = ['好的', '收到', '我来', '开始', '立即']

            has_refusal = any(m in result for m in refusal_markers)
            has_accept = any(m in result for m in accepted_markers)

            if has_refusal and not has_accept:
                print(f"  ✅ {role_id} 正确拒绝了越权请求")
            elif has_accept and not has_refusal:
                print(f"  ⚠️ {role_id} 接受了越权请求（边界模糊）")
            else:
                print(f"  ℹ️ {role_id} 回复 ambiguous，需人工判断")

    # ─────────── 场景C：学习经验注入 ───────────

    async def test_learning_insight(self):
        """测试角色是否能参考历史学习经验"""
        print("\n" + "=" * 60)
        print("【场景C】学习经验注入测试")
        print("=" * 60)

        # 1. 为 suri-dev 添加一条学习经验
        insight_content = (
            "经验：处理 'ModuleNotFoundError' 时，不仅要检查 import 语句，"
            "还要确认脚本目录结构是否正确。"
            "之前遇到过 tool_executor.py 因为路径缺少 'suri-agent/' 层级导致加载失败。"
        )

        # 写入角色的私人记忆文件
        mem_dir = self.project_root / 'group' / 'central' / 'suri-dev' / 'memories'
        mem_dir.mkdir(parents=True, exist_ok=True)
        mem_file = mem_dir / 'insights.md'
        mem_file.write_text(f"# 学习经验\n\n{insight_content}\n", encoding='utf-8')

        print(f"  已写入学习经验到 {mem_file}")

        # 2. 提出一个相关的问题，验证角色是否参考经验
        task_id = self.task.receive_task(self.user_id, "测试学习经验")
        request = "工具加载报错了，提示找不到模块，可能是什么原因？"
        print(f"\n  用户请求: {request}")

        result = await self._run_role_turn(task_id, 'suri-dev', request)
        print(f"  角色回复: {result[:300]}...")

        # 验证：回复中是否提到了经验中的内容
        mentions_experience = '路径' in result or '目录结构' in result or '层级' in result
        if mentions_experience:
            print("\n  ✅ 角色回复中引用了学习经验")
        else:
            print("\n  ℹ️ 角色回复未明显引用经验（可能经验未注入或模型未使用）")

        # 清理测试记忆文件
        mem_file.unlink(missing_ok=True)
        print("  已清理测试记忆文件")

    # ─────────── 主入口 ───────────

    async def run_all(self):
        print("\n" + "=" * 60)
        print("高级功能测试开始")
        print("=" * 60)

        await self.test_multi_turn_memory()
        await self.test_role_boundary()
        await self.test_learning_insight()

        print("\n" + "=" * 60)
        print("高级功能测试完成")
        print("=" * 60 + "\n")


if __name__ == '__main__':
    test = AdvancedTest()
    asyncio.run(test.run_all())
