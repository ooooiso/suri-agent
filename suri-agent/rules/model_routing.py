"""
模型路由规则

职责：
- 根据任务类型选择模型类别
- 主模型故障时自动降级
- 连续降级告警
"""

from typing import Dict, List, Optional
from rules.base import BaseRule


class ModelRoutingRule(BaseRule):
    """模型路由与降级策略"""
    
    rule_id = "model_routing"
    name = "模型路由规则"
    owner = "config_admin"
    
    # 超时阈值（秒）
    TIMEOUT_THRESHOLD = 30
    # 连续降级告警阈值
    MAX_CONSECUTIVE_FALLBACKS = 3
    
    # 任务类型 → 模型类别映射
    TASK_TO_CATEGORY = {
        "chat": "chat",
        "text_generation": "chat",
        "code": "expert",
        "analysis": "expert",
        "image_generation": "text2image",
        "image_edit": "image2image",
        "video_generation": "text2video",
    }
    
    def __init__(self):
        self._consecutive_fallbacks = 0
        self._last_model = None
    
    def validate(self, context: Dict) -> bool:
        task_type = context.get("task_type")
        model_pool = context.get("model_pool", [])
        return task_type is not None and len(model_pool) > 0
    
    def execute(self, context: Dict) -> Dict:
        task_type = context.get("task_type")
        model_pool = context.get("model_pool", [])
        preferred_model = context.get("preferred_model")
        
        selected = self.select_model(task_type, model_pool, preferred_model)
        return {
            "selected_model": selected,
            "category": self.TASK_TO_CATEGORY.get(task_type, "chat"),
            "fallback_count": self._consecutive_fallbacks,
        }
    
    def select_model(self, task_type: str, model_pool: List[Dict],
                    preferred_model: Optional[str] = None) -> Optional[Dict]:
        """根据任务类型选择模型"""
        category = self.TASK_TO_CATEGORY.get(task_type, "chat")
        
        # 过滤同类别的模型
        candidates = [
            m for m in model_pool
            if m.get("category") == category and m.get("status") == "active"
        ]
        
        if not candidates:
            return None
        
        # 按优先级排序
        candidates.sort(key=lambda m: m.get("priority", 0), reverse=True)
        
        # 若有偏好模型且可用，优先使用
        if preferred_model:
            for m in candidates:
                if m.get("model_id") == preferred_model:
                    return m
        
        # 返回优先级最高的可用模型
        return candidates[0] if candidates else None
    
    def should_fallback(self, last_error: Optional[str],
                       response_time: float) -> bool:
        """判断是否应触发降级"""
        if last_error and last_error != "":
            return True
        if response_time > self.TIMEOUT_THRESHOLD:
            return True
        return False
    
    def get_fallback_model(self, current_model: Dict,
                          model_pool: List[Dict]) -> Optional[Dict]:
        """获取降级后的备用模型"""
        category = current_model.get("category", "chat")
        current_id = current_model.get("model_id")
        
        candidates = [
            m for m in model_pool
            if m.get("category") == category
            and m.get("status") == "active"
            and m.get("model_id") != current_id
        ]
        
        candidates.sort(key=lambda m: m.get("priority", 0), reverse=True)
        
        if candidates:
            self._consecutive_fallbacks += 1
            self._last_model = candidates[0]
            return candidates[0]
        
        return None
    
    def record_success(self):
        """模型调用成功，重置降级计数"""
        self._consecutive_fallbacks = 0
    
    def should_alert(self) -> bool:
        """是否需要发送连续降级告警"""
        return self._consecutive_fallbacks >= self.MAX_CONSECUTIVE_FALLBACKS
