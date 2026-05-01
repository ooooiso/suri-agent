"""
角色自学习引擎

职责：
- 任务完成后，分析该角色的任务记录
- 提取经验、去重、写入角色记忆区
- 触发点：TaskService._trigger_learning()

设计原则：
- 异步执行，不阻塞主流程
- 错误处理完善，学习失败不影响系统运行

关联文档: suri-agent/learning/learning.md
"""

import asyncio
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from .base import BaseLearner
from .feedback_collector import FeedbackCollector, FeedbackRecord
from .experience_extractor import ExperienceExtractor, ExtractedInsight


class RoleLearner(BaseLearner):
    """角色自学习引擎"""
    
    learner_id = "role_learner"
    name = "角色自学习引擎"
    version = "1.0.0"
    
    def __init__(self, memory, model, logger=None):
        self.memory = memory
        self.model = model
        self.logger = logger
        self.collector = FeedbackCollector(memory, logger)
        self.extractor = ExperienceExtractor(model)
    
    async def learn(self, context: Dict[str, Any]) -> Optional[str]:
        """
        执行角色学习
        
        Args:
            context: {
                'task_id': str,
                'role_id': str,
                'success': bool
            }
        """
        return await self.learn_from_task(
            context['role_id'], 
            context['task_id']
        )
    
    async def learn_from_task(self, role_id: str, task_id: str) -> Optional[str]:
        """
        核心方法：从单个任务中学习
        
        步骤：
        1. 收集反馈
        2. 提取经验
        3. 去重检查
        4. 写入文件
        5. 记录日志
        """
        try:
            # 1. 收集反馈
            feedback = self.collector.collect_task_feedback(task_id, role_id)
            message_chain = self._get_message_chain(role_id, task_id)
            
            if self.logger:
                self.logger.log_learning(role_id, "开始复盘", f"任务 {task_id}")
            
            # 2. 提取经验
            insights = await self.extractor.extract(feedback, message_chain)
            
            if not insights:
                if self.logger:
                    self.logger.log_learning(role_id, "无经验可提取", f"任务 {task_id}")
                return None
            
            # 3. 逐条去重并写入
            saved_count = 0
            for insight in insights:
                if await self._is_duplicate(role_id, insight):
                    # 合并到已有经验
                    await self._merge_insight(role_id, insight)
                    if self.logger:
                        self.logger.log_learning(role_id, "经验合并", insight.title)
                else:
                    # 写入新经验
                    await self._save_insight(role_id, insight)
                    saved_count += 1
                    if self.logger:
                        self.logger.log_learning(role_id, "新经验保存", insight.title)
            
            # 4. 检查是否有技能更新建议
            skill_suggestions = self._check_skill_update(role_id, insights)
            
            if self.logger:
                self.logger.log_learning(
                    role_id, 
                    "复盘完成", 
                    f"任务 {task_id} | 提取 {len(insights)} 条 | 新增 {saved_count} 条 | 技能建议 {len(skill_suggestions)} 条"
                )
            
            return f"已保存 {saved_count} 条新经验"
            
        except Exception as e:
            if self.logger:
                self.logger.error("自学习", f"角色 {role_id} 任务 {task_id} 复盘失败: {e}")
            return None
    
    def _get_message_chain(self, role_id: str, task_id: str) -> list:
        """从 role.db 读取任务的完整消息链"""
        return self.memory.get_task_messages(role_id, task_id)
    
    async def _is_duplicate(self, role_id: str, insight: ExtractedInsight) -> bool:
        """
        去重检查：判断该经验是否已存在
        
        方案 A 实现（轻量）：
        - 读取该角色最近 50 条经验
        - 标题关键词杰卡德相似度 > 0.6 视为重复
        - 或 content 包含相同核心短语（5字以上短语匹配）
        
        Returns:
            True = 存在重复，需要合并
        """
        try:
            recent = self.memory.list_role_insights(role_id, limit=50)
            if not recent:
                return False
            
            new_title_words = set(insight.title.lower().split())
            new_key_point = insight.key_point.lower()
            
            for existing in recent:
                meta = existing.get('meta', {})
                existing_title = meta.get('title', '').lower()
                existing_content = existing.get('content', '').lower()
                
                # 杰卡德相似度
                existing_words = set(existing_title.split())
                if new_title_words and existing_words:
                    intersection = new_title_words & existing_words
                    union = new_title_words | existing_words
                    jaccard = len(intersection) / len(union) if union else 0
                    if jaccard > 0.6:
                        return True
                
                # 核心短语匹配（5字以上）
                # 提取新经验 key_point 中的 5-10 字短语
                new_phrases = self._extract_phrases(new_key_point, min_len=5, max_len=10)
                for phrase in new_phrases:
                    if phrase in existing_content:
                        return True
            
            return False
        except Exception:
            return False
    
    def _extract_phrases(self, text: str, min_len: int = 5, max_len: int = 10) -> List[str]:
        """从文本中提取指定长度的短语"""
        phrases = []
        for i in range(len(text) - min_len + 1):
            for length in range(min_len, min(max_len + 1, len(text) - i + 1)):
                phrase = text[i:i + length]
                # 过滤掉纯标点或空格的短语
                if any(c.isalnum() for c in phrase):
                    phrases.append(phrase)
        # 去重并限制数量
        seen = set()
        unique = []
        for p in phrases:
            if p not in seen:
                seen.add(p)
                unique.append(p)
                if len(unique) >= 50:  # 限制检查数量
                    break
        return unique
    
    async def _merge_insight(self, role_id: str, insight: ExtractedInsight) -> None:
        """
        合并经验：将新洞察合并到已有经验文件中
        
        操作：
        1. 找到匹配的旧经验文件
        2. 更新 trigger_count +1
        3. 更新 last_triggered 时间
        4. 如内容有补充，追加到"验证记录"段
        """
        try:
            recent = self.memory.list_role_insights(role_id, limit=50)
            
            for existing in recent:
                meta = existing.get('meta', {})
                existing_title = meta.get('title', '').lower()
                
                # 简单匹配：标题相似
                if insight.title.lower() in existing_title or existing_title in insight.title.lower():
                    # 更新文件
                    filepath = self.memory.project_root / existing['path']
                    if filepath.exists():
                        content = filepath.read_text(encoding='utf-8')
                        
                        # 更新 trigger_count
                        content = re.sub(
                            r'trigger_count:\s*\d+',
                            f"trigger_count: {meta.get('trigger_count', 1) + 1}",
                            content
                        )
                        
                        # 更新 last_triggered
                        now = datetime.now().isoformat()
                        content = re.sub(
                            r'last_triggered:\s*"[^"]*"',
                            f'last_triggered: "{now}"',
                            content
                        )
                        
                        # 追加验证记录
                        today = datetime.now().strftime('%Y-%m-%d')
                        content = content.rstrip() + f"\n- [{today}] 再次验证: {insight.situation[:50]}"
                        
                        filepath.write_text(content, encoding='utf-8')
                        break
        except Exception as e:
            if self.logger:
                self.logger.error("自学习", f"合并经验失败: {e}")
    
    async def _save_insight(self, role_id: str, insight: ExtractedInsight) -> str:
        """
        保存新经验到角色记忆区
        
        文件路径: group/<role>/memories/insights/YYYYMMDD_HHMMSS_{sanitized_title}.md
        """
        insight_data = {
            'title': insight.title,
            'category': insight.category,
            'situation': insight.situation,
            'key_point': insight.key_point,
            'avoid': insight.avoid,
            'tools_used': insight.tools_used,
            'skill_suggestion': insight.skill_suggestion,
            'confidence': insight.confidence,
        }
        return self.memory.save_role_insight(role_id, insight_data)
    
    def _check_skill_update(self, role_id: str, insights: List[ExtractedInsight]) -> List[Dict]:
        """
        检查是否有经验建议更新或创建技能
        
        当经验包含 tool_pattern 类别或 skill_suggestion 时，
        记录技能更新建议，供后续人工确认或自动处理。
        
        Returns:
            技能建议列表，每个元素包含 skill_id, tools, reason
        """
        suggestions = []
        for insight in insights:
            if insight.skill_suggestion or insight.category == 'tool_pattern':
                skill_id = insight.skill_suggestion or f"skill_{insight.title.lower().replace(' ', '_')[:30]}"
                suggestions.append({
                    'skill_id': skill_id,
                    'role_id': role_id,
                    'tools': insight.tools_used,
                    'reason': insight.key_point,
                    'title': insight.title,
                })
                if self.logger:
                    self.logger.log_learning(
                        role_id,
                        "技能更新建议",
                        f"建议创建/更新技能 {skill_id} | 工具: {insight.tools_used}"
                    )
        return suggestions
