"""
通信协议规则

职责：
- 验证消息格式
- 确定通信通道
- 跨部门通信权限校验
- 消息留存期限
"""

from typing import Dict, List, Optional
from rules.base import BaseRule


class CommunicationRule(BaseRule):
    """角色通信协议执行器"""
    
    rule_id = "communication_protocol"
    name = "角色通信协议"
    owner = "suri"
    
    # 消息留存期限（天）
    RETENTION_DAYS = {
        "approval": 90,
        "task": 30,
        "notify": 30,
        "escalation": 90,
    }
    
    # 通信通道映射
    CHANNELS = {
        "internal": "department_group",
        "director_to_suri": "private",
        "cross_department": "director_private_with_cc",
        "broadcast": "central_group",
        "approval_flow": "security_to_suri_to_user",
    }
    
    REQUIRED_FIELDS = [
        "message_id", "sender_role", "receiver_role",
        "timestamp", "priority", "task_ref",
        "body.type", "body.content",
    ]
    
    def validate(self, context: Dict) -> bool:
        msg = context.get("message")
        if not msg:
            return False
        return self.validate_message_format(msg)
    
    def execute(self, context: Dict) -> Dict:
        sender = context.get("sender_role")
        receiver = context.get("receiver_role")
        scenario = context.get("scenario", "internal")
        
        channel = self.get_channel(sender, receiver, scenario)
        allowed = self.is_cross_department_allowed(sender, receiver)
        
        return {
            "channel": channel,
            "allowed": allowed,
            "retention_days": self.get_retention_days(context.get("msg_type", "task")),
        }
    
    def validate_message_format(self, msg: Dict) -> bool:
        """验证消息是否包含必填字段"""
        for field in self.REQUIRED_FIELDS:
            if "." in field:
                parts = field.split(".")
                target = msg
                for part in parts:
                    if not isinstance(target, dict) or part not in target:
                        return False
                    target = target[part]
            else:
                if field not in msg:
                    return False
        return True
    
    def get_channel(self, sender_role: str, receiver_role: str,
                   scenario: str) -> str:
        """确定通信通道"""
        return self.CHANNELS.get(scenario, "private")
    
    def is_cross_department_allowed(self, sender_role: str,
                                    receiver_role: str) -> bool:
        """
        检查跨部门通信是否允许。
        普通成员禁止跨部门直连，总监级可以。
        """
        # 简化实现：所有角色 ID 中包含 _admin 或 _lead 或 _director 的视为总监级
        director_keywords = ["_admin", "_lead", "_director"]
        sender_is_director = any(kw in sender_role for kw in director_keywords)
        receiver_is_director = any(kw in receiver_role for kw in director_keywords)
        
        if sender_role == "suri" or receiver_role == "suri":
            return True
        
        # 双方都是总监级，允许跨部门
        return sender_is_director and receiver_is_director
    
    def get_retention_days(self, msg_type: str) -> int:
        """获取消息类型对应的留存天数"""
        return self.RETENTION_DAYS.get(msg_type, 30)
