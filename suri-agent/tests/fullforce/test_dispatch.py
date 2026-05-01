#!/usr/bin/env python3
"""
调度测试 — 模拟用户输入，测试四角色联动
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
from core.tool_executor import ToolService


class DispatchTest:
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
        self.user_id = "test_user"

    async def simulate_suri_process(self, text: str):
        """模拟 suri_process 流程"""
        print(f"\n{'='*60}")
        print(f"【用户输入】{text}")
        print(f"{'='*60}")
        
        # 1. 创建任务
        task_id = self.task.receive_task(self.user_id, text)
        print(f"[系统] 任务创建: {task_id}")
        
        # 2. 构建 suri 系统提示
        default_model = self.model_manager.get_default_model()
        suri_system_prompt = (
            "你是 Suri，central 部门的负责人，也是整个智能体平台的中枢。\n"
            "你的职责：\n"
            "1. 理解用户需求\n"
            "2. 判断需求归属哪个角色（根据下方角色能力边界判断）\n"
            "3. 如果需求可直接回答（闲聊、简单问题、关于你自身状态的问题），直接给出清晰回复，不要调度\n"
            "4. 如果需求需要其他角色的专业能力，直接回答处理结果（系统会自动将任务转发给对应角色执行）\n"
            "\n"
            "当前平台角色及能力边界：\n"
            "- suri（你自己）：中枢调度，负责任务分析、分派、协调、汇总。可直接回答闲聊、问候、平台状态查询。\n"
            "- suri-hr：人力资源与行政，负责角色创建/注销、组织架构调整、技能分配、部门设置。\n"
            "- suri-dev：程序维护，负责代码修复、性能优化、框架升级、技术架构设计、Bug 排查。\n"
            "- document-review：文档与变更审核，负责代码/文档审核、变更计划审计、质量把关。\n"
            "\n"
            "你当前使用的模型: {model_name} ({model_id})\n"
            "\n"
            "回复规则：\n"
            "- 用户问'你用的什么模型'、'你是谁'、'你能做什么'等关于你自身的问题 → 直接回答，不要调度\n"
            "- 闲聊、问候、简单事实问答 → 直接回答，不要调度\n"
            "- 需要写代码、修 Bug、优化性能、设计架构 → 由 suri-dev 处理\n"
            "- 需要创建角色、调整部门、分配技能 → 由 suri-hr 处理\n"
            "- 需要审核代码/文档、评估变更风险 → 由 document-review 处理\n"
            "- 请用简洁的中文回复，直接给出结果，不要重复说明'派发给谁'"
        ).format(model_name=default_model.name, model_id=default_model.model_id)
        
        messages = [
            {"role": "system", "content": suri_system_prompt},
            {"role": "user", "content": text},
        ]
        
        # 3. 调用模型
        try:
            reply = await self.model_manager.chat(messages)
            print(f"\n[suri] {reply}\n")
        except Exception as e:
            print(f"\n[suri] ❌ 模型调用失败: {e}\n")
            return
        
        # 4. 调度判断（双层匹配）
        dispatch_target = await self._detect_dispatch_target(text, reply)
        
        if dispatch_target:
            print(f"[系统] 匹配到角色: {dispatch_target}，触发调度...")
            role_result = await self._execute_dispatch(task_id, text, reply, dispatch_target)
            if role_result:
                summary = await self._summarize_result(task_id, text, dispatch_target, role_result)
                if summary:
                    print(f"\n[suri 汇总] {summary}\n")
        else:
            print(f"[系统] 未匹配到调度目标，suri 直接处理")
    
    async def _detect_dispatch_target(self, text, suri_reply):
        """检测调度目标（双层匹配）"""
        all_roles = [rid for rid in self.config.list_roles() if rid != 'suri']
        suri_reply_lower = suri_reply.lower()
        user_text_lower = text.lower()
        
        for rid in all_roles:
            if rid in suri_reply_lower:
                return rid
        
        for role_id in all_roles:
            keywords = self.config.get_role_keywords(role_id)
            for kw in keywords:
                if kw.lower() in user_text_lower:
                    return role_id
        return None
    
    async def _execute_dispatch(self, task_id, text, suri_reply, matched):
        """执行调度"""
        role_soul = self.config.get_role_soul(matched)
        if not role_soul:
            print(f"[系统] 角色 {matched} Soul 文件缺失")
            return None
        
        print(f"[系统] 调度至 {matched}...")
        
        default_model = self.model_manager.get_default_model()
        model_info = {
            'name': default_model.name,
            'model_id': default_model.model_id,
            'provider': default_model.provider,
        }
        
        role_prompt = self.context.build_context(matched, model_info=model_info)
        role_prompt += (
            f"\n\n---\n\n"
            f"当前任务来自用户，请直接给出专业的处理结果。\n"
            f"任务内容：{text}\n\n"
            f"要求：用简洁的中文回复，直接输出结果，不要提及调度或转发。"
        )
        
        messages = [
            {"role": "system", "content": role_prompt},
            {"role": "user", "content": text},
        ]
        
        try:
            result = await self.model_manager.chat(messages)
            print(f"\n[{matched}] {result}\n")
            return result
        except Exception as e:
            print(f"\n[{matched}] ❌ 执行失败: {e}\n")
            return None
    
    async def _summarize_result(self, task_id, text, role_id, role_result):
        """结果回流汇总"""
        summarize_prompt = (
            "你是 Suri，中枢调度总监。你刚刚将用户的任务交给了一个专业角色处理，"
            "现在该角色已完成工作并返回了结果。你的任务是：\n"
            "1. 审阅角色的处理结果\n"
            "2. 用简洁的中文向用户汇报最终结果\n"
            "3. 如果角色结果需要补充或澄清，简要说明\n"
            "4. 不要重复角色的详细技术内容，只提炼关键结论和行动项\n\n"
            f"原始用户需求：{text}\n"
            f"执行角色：{role_id}\n"
            f"角色返回结果：{role_result[:800]}\n\n"
            f"请向用户汇报最终结果（2-3 句话）："
        )
        
        messages = [
            {"role": "system", "content": "你是 Suri，用简洁中文汇报任务结果。"},
            {"role": "user", "content": summarize_prompt},
        ]
        
        try:
            summary = await self.model_manager.chat(messages)
            return summary
        except Exception:
            return f"{role_id} 已处理完成：{role_result[:200]}..." if len(role_result) > 200 else role_result
    
    async def run_tests(self):
        """运行调度测试用例"""
        print("\n" + "="*60)
        print("调度联动测试开始")
        print("="*60)
        
        # 测试 1: 闲聊问候（不应调度）
        await self.simulate_suri_process("你好，你是谁？")
        
        # 测试 2: 技术问题（应调度到 suri-dev）
        await self.simulate_suri_process("系统有个 Bug，帮我排查一下")
        
        # 测试 3: 创建角色（应调度到 suri-hr）
        await self.simulate_suri_process("帮我创建一个设计部门的设计师角色")
        
        # 测试 4: 文档审核（应调度到 document-review）
        await self.simulate_suri_process("帮我审核一下刚修改的代码文档")
        
        # 测试 5: 设计需求（应调度到 designer）
        await self.simulate_suri_process("帮我设计一个产品的登录页面")
        
        print("\n" + "="*60)
        print("调度联动测试完成")
        print("="*60 + "\n")


if __name__ == '__main__':
    test = DispatchTest()
    asyncio.run(test.run_tests())
