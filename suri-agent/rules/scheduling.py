"""
调度规则

职责：
- 任务入口唯一性校验
- 需求匹配部门
- 任务下发与升级
- 跨部门协作协调
"""

from typing import Dict, List, Optional, Any
from rules.base import BaseRule


class SchedulingRule(BaseRule):
    """任务调度规则执行器"""
    
    rule_id = "scheduling"
    name = "调度规则"
    owner = "suri"
    
    # 重试间隔（秒）
    RETRY_INTERVALS = [0, 30, 120]
    MAX_RETRIES = 3
    DIRECTOR_OFFLINE_THRESHOLD = 300  # 5分钟
    
    def validate(self, context: Dict) -> bool:
        """校验调度请求是否合法"""
        role_id = context.get("role_id")
        if not role_id:
            return False
        # 只有 suri 能作为任务入口
        return role_id == "suri"
    
    def execute(self, context: Dict) -> Dict:
        """执行调度决策"""
        text = context.get("text", "")
        departments = context.get("departments", [])
        
        matched = self.match_department(text, departments)
        return {
            "matched_department": matched,
            "is_cross_department": len(matched) > 1 if isinstance(matched, list) else False,
            "requires_clarification": matched is None,
        }
    
    def match_department(self, text: str, departments: List[Dict]) -> Optional[Any]:
        """
        根据需求内容匹配责任部门。
        返回单个部门、多个部门（跨部门）或 None（无法匹配）。
        """
        matches = []
        for dept in departments:
            dept_function = dept.get("function", "")
            # 简单关键词匹配（后续可替换为语义匹配）
            keywords = dept_function.replace("、", " ").replace("，", " ").split()
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                matches.append((score, dept))
        
        if not matches:
            return None
        
        matches.sort(key=lambda x: x[0], reverse=True)
        
        # 如果最高分明显领先，返回单个部门
        if len(matches) == 1 or matches[0][0] > matches[1][0] * 1.5:
            return matches[0][1]
        
        # 多个部门得分接近，返回跨部门需求
        return [m[1] for m in matches[:3]]
    
    def get_retry_interval(self, retry_count: int) -> int:
        """获取第 N 次重试的等待间隔（秒）"""
        if retry_count < len(self.RETRY_INTERVALS):
            return self.RETRY_INTERVALS[retry_count]
        return self.RETRY_INTERVALS[-1]
    
    def should_escalate(self, director_last_seen: float, current_time: float) -> bool:
        """总监离线超过阈值，应升级"""
        return (current_time - director_last_seen) > self.DIRECTOR_OFFLINE_THRESHOLD
    
    def build_task_message(self, task_id: str, task_type: str, 
                          requirement: str, deadline: str) -> Dict:
        """构建标准化任务消息"""
        return {
            "message_id": f"msg_{task_id}",
            "task_type": task_type,
            "requirement": requirement,
            "deadline": deadline,
            "status": "pending",
        }
