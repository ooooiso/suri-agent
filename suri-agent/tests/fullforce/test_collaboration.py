#!/usr/bin/env python3
"""
协同场景测试 — 复杂需求涉及多个角色

测试当前架构对多角色协作的支持程度。
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


class CollaborationTest:
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
        self.user_id = "collab_test_user"

    def _detect_dispatch_target(self, text: str, suri_reply: str):
        """检测调度目标（双层匹配）"""
        all_roles = [rid for rid in self.config.list_roles() if rid != 'suri']
        suri_reply_lower = suri_reply.lower()
        user_text_lower = text.lower()

        matched = None
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

        # 收集所有匹配的角色（用于协同分析）
        all_matches = set()
        for role_id in all_roles:
            for kw in self.config.get_role_keywords(role_id):
                if kw.lower() in user_text_lower:
                    all_matches.add(role_id)

        return matched, all_matches

    async def _call_suri(self, text: str) -> str:
        """调用 suri 分析需求"""
        default_model = self.model_manager.get_default_model()
        all_roles = [rid for rid in self.config.list_roles() if rid != 'suri']
        role_list = "\n".join(f"- {rid}: {', '.join(self.config.get_role_keywords(rid)[:3])}" for rid in all_roles)

        suri_prompt = (
            "你是 Suri，中枢调度总监。当前平台有多个部门角色：\n\n"
            f"{role_list}\n\n"
            "你的职责是分析用户需求，判断需要哪些角色协作完成。\n"
            "如果需求涉及多个角色，请明确列出所有相关角色。\n"
            "回复规则：\n"
            "- 直接分析需求归属\n"
            "- 如涉及多个角色，列出角色名（用逗号分隔）\n"
            "- 如可直接回答，直接给出建议\n\n"
            f"用户请求：{text}"
        )

        messages = [
            {"role": "system", "content": suri_prompt},
            {"role": "user", "content": text},
        ]

        try:
            return await self.model_manager.chat(messages)
        except Exception as e:
            return f"[错误] {e}"

    async def _call_role(self, role_id: str, text: str, task_id: str) -> str:
        """调用指定角色"""
        default_model = self.model_manager.get_default_model()
        model_info = {
            'name': default_model.name,
            'model_id': default_model.model_id,
            'provider': default_model.provider,
        }

        current_task = {'task_id': task_id, 'requirement': text}
        role_prompt = self.context.build_context(role_id, current_task=current_task, model_info=model_info)
        role_prompt += f"\n\n---\n\n任务内容：{text}\n要求：直接输出结果。"

        messages = [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": text},
        ]

        try:
            return await self.model_manager.chat(messages)
        except Exception as e:
            return f"[错误] {e}"

    async def test_single_role_dispatch(self):
        """场景1：单一角色需求"""
        print("\n" + "=" * 60)
        print("【协同场景1】单一角色需求")
        print("=" * 60)

        text = "帮我设计一个数据分析平台的用户界面"
        print(f"  用户: {text}")

        suri_reply = await self._call_suri(text)
        print(f"  suri: {suri_reply[:200]}...")

        matched, all_matches = self._detect_dispatch_target(text, suri_reply)
        print(f"  首匹配角色: {matched}")
        print(f"  所有匹配角色: {all_matches}")

        if matched:
            result = await self._call_role(matched, text, "task_single")
            print(f"  [{matched}] {result[:200]}...")

    async def test_multi_role_collaboration(self):
        """场景2：多角色协作需求"""
        print("\n" + "=" * 60)
        print("【协同场景2】多角色协作需求")
        print("=" * 60)

        text = (
            "我需要开发一个电商数据分析平台，"
            "包括前端界面设计、后端API开发、"
            "销售数据清洗分析、用户操作文档、"
            "以及全面的质量测试。"
        )
        print(f"  用户: {text[:80]}...")

        suri_reply = await self._call_suri(text)
        print(f"  suri: {suri_reply[:300]}...")

        matched, all_matches = self._detect_dispatch_target(text, suri_reply)
        print(f"  首匹配角色: {matched}")
        print(f"  关键词匹配到的所有角色: {all_matches}")

        # 架构限制分析
        if len(all_matches) > 1:
            print(f"\n  ⚠️ 架构限制检测：需求涉及 {len(all_matches)} 个角色")
            print(f"     当前系统只调度到首匹配角色 [{matched}]")
            print(f"     理想行为：应依次调度到 {all_matches}")

            # 模拟理想行为：依次调用所有匹配角色
            print(f"\n  【模拟】依次调度到所有匹配角色：")
            for rid in all_matches:
                result = await self._call_role(rid, f"你是 '{rid}'，负责这个大型项目的一部分。项目需求：{text}", f"task_multi_{rid}")
                print(f"    [{rid}] {result[:150]}...")
        else:
            print(f"  ℹ️ 只匹配到单一角色")

    async def test_keyword_coverage(self):
        """场景3：关键词覆盖验证"""
        print("\n" + "=" * 60)
        print("【协同场景3】关键词覆盖验证")
        print("=" * 60)

        test_inputs = [
            ("帮我写测试用例", ["qa-tester"]),
            ("帮我分析销售数据", ["data-analyst"]),
            ("帮我写产品说明书", ["content-writer"]),
            ("帮我修Bug", ["suri-dev"]),
            ("帮我创建角色", ["suri-hr"]),
            ("帮我审核文档", ["document-review"]),
        ]

        for text, expected_roles in test_inputs:
            _, all_matches = self._detect_dispatch_target(text, "")
            is_match = any(r in all_matches for r in expected_roles)
            status = "✅" if is_match else "❌"
            print(f"  {status} '{text[:20]}...' → 匹配: {all_matches} (期望: {expected_roles})")

    async def run_all(self):
        print("\n" + "=" * 60)
        print("协同场景测试开始")
        print("=" * 60)

        await self.test_single_role_dispatch()
        await self.test_multi_role_collaboration()
        await self.test_keyword_coverage()

        print("\n" + "=" * 60)
        print("协同场景测试完成")
        print("=" * 60 + "\n")


if __name__ == '__main__':
    test = CollaborationTest()
    asyncio.run(test.run_all())
