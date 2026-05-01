#!/usr/bin/env python3
"""
压力测试 — 快速连续调度多个角色

验证系统在短时间内处理多个不同类型任务的能力。
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


class StressTest:
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
        self.user_id = "stress_test_user"

    async def _dispatch_once(self, text: str, expected_role: str) -> dict:
        """执行一次完整调度，返回结果和耗时"""
        import time
        start = time.time()

        task_id = self.task.receive_task(self.user_id, text)

        default_model = self.model_manager.get_default_model()
        model_info = {
            'name': default_model.name,
            'model_id': default_model.model_id,
            'provider': default_model.provider,
        }

        # suri 分析
        suri_prompt = (
            "你是 Suri，中枢调度总监。\n"
            "当前平台角色：suri-dev（程序维护）、suri-hr（人事）、document-review（审核）。\n"
            "请直接回复，如果需要某个角色处理，请明确说出角色名。\n"
            f"用户请求：{text}"
        )
        messages = [
            {"role": "system", "content": suri_prompt},
            {"role": "user", "content": text},
        ]

        try:
            suri_reply = await self.model_manager.chat(messages)
        except Exception as e:
            return {'success': False, 'error': f'suri 调用失败: {e}', 'elapsed': time.time() - start}

        # 调度判断
        all_roles = [rid for rid in self.config.list_roles() if rid != 'suri']
        matched = None
        suri_reply_lower = suri_reply.lower()
        user_text_lower = text.lower()

        for rid in all_roles:
            if rid in suri_reply_lower:
                matched = rid
                break
        if not matched:
            for role_id in all_roles:
                for kw in self.config.get_role_keywords(role_id):
                    if kw.lower() in user_text_lower:
                        matched = role_id
                        break
                if matched:
                    break

        if not matched:
            return {
                'success': True,
                'suri_reply': suri_reply,
                'role_result': None,
                'matched': None,
                'expected': expected_role,
                'elapsed': time.time() - start,
            }

        # 角色执行
        current_task = {'task_id': task_id, 'requirement': text}
        role_prompt = self.context.build_context(matched, current_task=current_task, model_info=model_info)
        role_prompt += f"\n\n---\n\n任务内容：{text}\n要求：直接输出结果。"

        role_messages = [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": text},
        ]

        try:
            role_result = await self.model_manager.chat(role_messages)
        except Exception as e:
            return {'success': False, 'error': f'{matched} 调用失败: {e}', 'elapsed': time.time() - start}

        elapsed = time.time() - start
        return {
            'success': True,
            'suri_reply': suri_reply,
            'role_result': role_result,
            'matched': matched,
            'expected': expected_role,
            'elapsed': elapsed,
        }

    async def run_stress(self):
        """快速连续调度测试"""
        print("\n" + "=" * 60)
        print("【压力测试】快速连续调度多个角色")
        print("=" * 60)

        cases = [
            ("帮我排查一个启动时的 Bug", "suri-dev"),
            ("帮我创建一个测试部门的新角色", "suri-hr"),
            ("帮我审核一下刚才修改的文档", "document-review"),
        ]

        results = []
        for text, expected in cases:
            print(f"\n  调度: {text[:40]}...")
            result = await self._dispatch_once(text, expected)
            results.append(result)

            if result['success']:
                matched = result['matched'] or 'suri'
                correct = matched == expected
                print(f"    匹配: {matched} (期望 {expected}) {'✅' if correct else '❌'}")
                print(f"    耗时: {result['elapsed']:.2f}s")
                if result['role_result']:
                    print(f"    角色回复: {result['role_result'][:80]}...")
            else:
                print(f"    ❌ 失败: {result['error']}")

        # 汇总
        total = len(results)
        success = sum(1 for r in results if r['success'])
        correct_match = sum(1 for r in results if r['success'] and r['matched'] == r['expected'])
        avg_time = sum(r['elapsed'] for r in results if r['success']) / max(success, 1)

        print(f"\n  汇总: {success}/{total} 成功, {correct_match}/{total} 匹配正确, 平均耗时 {avg_time:.2f}s")

    async def run_all(self):
        await self.run_stress()


if __name__ == '__main__':
    test = StressTest()
    asyncio.run(test.run_all())
