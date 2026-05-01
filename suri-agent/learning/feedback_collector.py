"""
反馈收集器

职责：
- 在任务生命周期关键节点收集结构化反馈
- 为学习器提供标准化的输入数据

触发点：
1. 任务完成（成功/失败/取消）
2. 用户显式反馈（确认/修改/拒绝）
3. 异常重试耗尽

关联文档: suri-agent/learning/learning.md
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class TaskOutcome(str, Enum):
    SUCCESS = "success"      # 任务完成，用户满意
    PARTIAL = "partial"      # 完成但需修改
    FAILED = "failed"        # 执行失败
    CANCELLED = "cancelled"  # 用户取消
    TIMEOUT = "timeout"      # 超时


class UserFeedback(str, Enum):
    NONE = "none"            # 无显式反馈
    CONFIRM = "confirm"      # 用户确认通过
    MODIFY = "modify"        # 用户要求修改
    REJECT = "reject"        # 用户拒绝
    PRAISE = "praise"        # 用户表扬
    COMPLAIN = "complain"    # 用户抱怨


@dataclass
class FeedbackRecord:
    """标准化反馈记录"""
    task_id: str
    role_id: str
    session_id: str
    outcome: TaskOutcome
    user_feedback: UserFeedback = UserFeedback.NONE
    retry_count: int = 0
    execution_time_ms: int = 0
    user_comment: str = ""   # 用户自由文本反馈
    error_info: str = ""     # 失败时的错误信息


class FeedbackCollector:
    """反馈收集器"""
    
    def __init__(self, memory_service, logger=None):
        self.memory = memory_service
        self.logger = logger
    
    def collect_task_feedback(self, task_id: str, role_id: str) -> FeedbackRecord:
        """
        从 role.db 中提取任务的完整反馈信息
        
        读取内容：
        - task 记录（状态、重试次数）
        - 消息链（完整对话）
        - 审批记录（如有）
        
        Returns:
            FeedbackRecord 结构化对象
        """
        task = self.memory.get_task(role_id, task_id) or {}
        messages = self.memory.get_task_messages(role_id, task_id)
        
        # 推断 outcome
        status = task.get('status', 'pending')
        outcome_map = {
            'completed': TaskOutcome.SUCCESS,
            'failed': TaskOutcome.FAILED,
            'cancelled': TaskOutcome.CANCELLED,
            'timeout': TaskOutcome.TIMEOUT,
        }
        outcome = outcome_map.get(status, TaskOutcome.PARTIAL)
        
        # 检查是否有用户反馈消息
        user_feedback = UserFeedback.NONE
        user_comment = ""
        for msg in messages:
            body = msg.get('body', {})
            if body.get('type') == 'user_feedback':
                fb = body.get('feedback', 'none')
                try:
                    user_feedback = UserFeedback(fb)
                except ValueError:
                    user_feedback = UserFeedback.NONE
                user_comment = body.get('comment', '')
                break
        
        return FeedbackRecord(
            task_id=task_id,
            role_id=role_id,
            session_id=task.get('session_id', ''),
            outcome=outcome,
            user_feedback=user_feedback,
            retry_count=task.get('retry_count', 0),
            execution_time_ms=0,  # 暂时未统计
            user_comment=user_comment,
            error_info=task.get('error_info', '')
        )
    
    def record_user_feedback(self, task_id: str, feedback: UserFeedback, comment: str = "") -> None:
        """
        记录用户的显式反馈（由接入层调用）
        
        存储位置：在对应 role.db 的 messages 表中新增一条 type='user_feedback' 的消息
        """
        import uuid
        from datetime import datetime
        
        self.memory.save_message(
            role_id='suri',
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            task_id=task_id,
            sender='user',
            receiver='suri',
            body={
                'type': 'user_feedback',
                'feedback': feedback.value,
                'comment': comment,
                'timestamp': datetime.now().isoformat()
            }
        )
        
        if self.logger:
            self.logger.log_learning(
                'suri',
                '用户显式反馈',
                f"任务 {task_id} | {feedback.value} | {comment[:50]}"
            )
