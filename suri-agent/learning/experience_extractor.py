"""
经验提取器

职责：
- 定义经验提取的 Prompt 模板
- 调用 LLM 分析任务记录，生成结构化经验
- 解析 LLM 输出为内部格式

原则：Prompt 工程集中在此处，便于统一调优。

关联文档: suri-agent/learning/learning.md
"""

from typing import Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExtractedInsight:
    """提取后的经验条目"""
    title: str              # 经验标题（一句话概括）
    category: str           # 类别: success_pattern / improvement / pitfall / preference / tool_pattern
    situation: str          # 适用情境
    key_point: str          # 核心要点
    avoid: str              # 避免什么
    tools_used: str = ""    # 使用的工具及调用方式（JSON 格式或描述）
    skill_suggestion: str = ""  # 是否建议固化为技能，技能 ID 建议
    confidence: float = 0.5  # 置信度 0-1
    created_at: str = ""     # ISO 时间


class ExperienceExtractor:
    """经验提取器"""
    
    def __init__(self, model_service):
        self.model = model_service
    
    async def extract(self, feedback: 'FeedbackRecord', message_chain: List[Dict]) -> List[ExtractedInsight]:
        """
        从任务反馈中提取经验
        
        Args:
            feedback: 结构化反馈记录
            message_chain: 完整消息链（角色对话记录）
            
        Returns:
            0-3 条 ExtractedInsight，空列表表示无可学习的内容
        """
        prompt = self._build_prompt(feedback, message_chain)
        
        # 调用模型（使用 chat 类型，轻量级模型即可）
        model_result = await self.model.call_model(prompt, model_type='chat')
        
        if not model_result or not model_result.get('success'):
            return []
        
        response = model_result.get('content', '')
        return self._parse_response(response)
    
    def _build_prompt(self, feedback, message_chain) -> str:
        """构建经验提取 Prompt"""
        
        # 格式化消息链
        chain_text = ""
        for msg in message_chain[-20:]:  # 最近 20 条
            body = msg.get('body', {})
            content = body.get('content', '')
            chain_text += f"[{msg.get('sender_role')} → {msg.get('receiver_role')}] {content[:300]}\n"
        
        return EXPERIENCE_EXTRACTION_PROMPT_TEMPLATE.format(
            role_id=feedback.role_id,
            task_id=feedback.task_id,
            outcome=feedback.outcome.value,
            user_feedback=feedback.user_feedback.value,
            retry_count=feedback.retry_count,
            execution_time_ms=feedback.execution_time_ms,
            user_comment=feedback.user_comment,
            error_info=feedback.error_info,
            message_chain=chain_text
        )
    
    def _parse_response(self, response: str) -> List[ExtractedInsight]:
        """解析 LLM 返回的文本为结构化经验"""
        response = response.strip()
        
        # 如果没有值得记录的经验
        if response == '无' or len(response) < 10:
            return []
        
        insights = []
        # 按 "---" 分割文本
        parts = response.split('---')
        
        for part in parts:
            part = part.strip()
            if not part or '类别:' not in part:
                continue
            
            # 提取各字段
            category = self._extract_field(part, '类别')
            title = self._extract_field(part, '标题')
            situation = self._extract_field(part, '情境')
            key_point = self._extract_field(part, '要点')
            avoid = self._extract_field(part, '避免')
            tools_used = self._extract_field(part, '工具调用')
            skill_suggestion = self._extract_field(part, '技能建议')
            
            # 跳过标题为空的段落
            if not title:
                continue
            
            # confidence 初始值
            confidence_map = {
                'success_pattern': 0.7,
                'improvement': 0.6,
                'pitfall': 0.8,
                'preference': 0.5,
                'tool_pattern': 0.75,
            }
            confidence = confidence_map.get(category, 0.5)
            
            insights.append(ExtractedInsight(
                title=title,
                category=category,
                situation=situation,
                key_point=key_point,
                avoid=avoid,
                tools_used=tools_used,
                skill_suggestion=skill_suggestion,
                confidence=confidence,
                created_at=datetime.now().isoformat()
            ))
        
        return insights[:3]  # 最多 3 条
    
    def _extract_field(self, text: str, field_name: str) -> str:
        """从文本中提取指定字段的值"""
        import re
        pattern = rf'{field_name}[：:]\s*(.*?)(?=\n|$)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""


# ═══════════════════════════════════════════════════════
# Prompt 模板
# ═══════════════════════════════════════════════════════

EXPERIENCE_EXTRACTION_PROMPT_TEMPLATE = """你是一位经验丰富的 AI 助手复盘专家。请分析以下任务执行记录，提取 0-3 条可复用的经验。

【任务信息】
角色: {role_id}
任务ID: {task_id}
状态: {outcome}
用户反馈: {user_feedback}
重试次数: {retry_count}
执行耗时: {execution_time_ms}ms
用户评论: {user_comment}
错误信息: {error_info}

【完整对话记录】
{message_chain}

【指令】
请判断这次任务是否有值得记录的经验：
- 如果任务成功且顺利，提取"成功模式"
- 如果用户反复修改或反馈负面，提取"改进建议"和"常见陷阱"
- 如果任务失败，分析决策链中哪一步出了问题
- 如果任务中使用了工具（如文件操作、模型切换、shell 命令等），提取"工具使用模式"
- 如果只是普通任务、无明显特征，返回"无"

【特别关注】
- 如果角色在任务中调用了工具，请分析：调用了哪些工具、调用顺序、参数模式、是否形成了可复用的工具组合
- 如果某个工具调用模式重复出现（2次以上），建议将其固化为"技能"，给出技能 ID 建议

【输出格式】（严格按此格式，不要多余内容）
---
经验1
类别: [success_pattern / improvement / pitfall / preference / tool_pattern]
标题: [一句话概括，20字以内]
情境: [什么情况下适用]
要点: [具体做法，100字以内]
避免: [如果做错了会怎样，50字以内]
工具调用: [如果涉及工具，描述调用的工具及参数模式；否则留空]
技能建议: [如果建议固化为技能，给出技能 ID 建议，如 "skill_model_switch"；否则留空]
---
经验2
类别: ...
...
---

如果没有值得记录的经验，只输出一个字：无"""
