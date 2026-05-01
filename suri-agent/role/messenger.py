"""
角色通信管理器

职责：
- 角色间消息路由
- 消息格式校验
- 跨部门通信权限检查
- 消息留存管理
"""

from pathlib import Path
from typing import Dict, Any, Optional


class RoleMessenger:
    """角色通信管理器"""
    
    REQUIRED_FIELDS = ["message_id", "sender_role", "receiver_role", 
                       "timestamp", "priority", "task_ref", "body"]
    
    VALID_PRIORITIES = ["high", "normal", "low"]
    VALID_TYPES = ["task", "approval", "notify", "escalation"]
    
    # 消息留存期限（天）
    RETENTION_DAYS = {
        "approval": 90,
        "task": 30,
        "notify": 30,
        "escalation": 90,
    }
    
    def __init__(self, project_root: Path, projection_service=None, config=None):
        self.project_root = project_root
        self.projection = projection_service  # 投影服务
        self.config = config  # ConfigService，用于动态读取角色 department
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息，执行格式校验和权限检查
        
        Args:
            message: 消息体
            
        Returns:
            发送结果
        """
        # 1. 格式校验
        valid, error = self._validate_format(message)
        if not valid:
            return {"success": False, "error": error}
        
        sender = message.get("sender_role")
        receiver = message.get("receiver_role")
        
        # 2. 跨部门通信权限检查
        if not self._can_communicate(sender, receiver):
            return {
                "success": False,
                "error": f"跨部门通信被拒绝: {sender} 无权直接联系 {receiver}",
            }
        
        # 3. 路由消息
        result = {
            "success": True,
            "message_id": message.get("message_id"),
            "routed": True,
            "sender": sender,
            "receiver": receiver,
            "channel": self._get_channel(sender, receiver),
            "retention_days": self._get_retention_days(message),
        }
        
        # 4. 投影到 Telegram（新增）
        if self.projection:
            import asyncio
            # 确定投影目标
            project_to = self._get_project_targets(sender, receiver)
            if project_to:
                asyncio.create_task(
                    self.projection.project_message(project_to, sender, receiver, message)
                )
        
        return result
    
    def _get_project_targets(self, sender: str, receiver: str) -> list:
        """获取投影目标 Telegram 群组"""
        dept_map = self._get_department_map()
        sender_dept = dept_map.get(sender, 'unknown')
        receiver_dept = dept_map.get(receiver, 'unknown')
        
        targets = []
        
        # 同部门通信 → 投影到该部门群
        if sender_dept == receiver_dept and sender_dept != 'unknown':
            targets.append(f"tg:{sender_dept}")
        
        # 跨部门通信 → 投影到双方部门群 + 中枢群
        elif sender_dept != receiver_dept:
            if sender_dept != 'unknown':
                targets.append(f"tg:{sender_dept}")
            if receiver_dept != 'unknown':
                targets.append(f"tg:{receiver_dept}")
            targets.append("tg:central")
        
        return targets
    
    def _validate_format(self, message: Dict[str, Any]) -> tuple[bool, str]:
        """校验消息格式"""
        for field in self.REQUIRED_FIELDS:
            if field not in message:
                return False, f"缺少必填字段: {field}"
        
        body = message.get("body", {})
        if "type" not in body or "content" not in body:
            return False, "body 缺少 type 或 content"
        
        if body.get("type") not in self.VALID_TYPES:
            return False, f"无效的 body.type: {body.get('type')}"
        
        if message.get("priority") not in self.VALID_PRIORITIES:
            return False, f"无效的 priority: {message.get('priority')}"
        
        return True, ""
    
    def _can_communicate(self, sender: str, receiver: str) -> bool:
        """检查跨部门通信是否允许"""
        if sender == receiver:
            return True
        
        if sender == "suri" or receiver == "suri":
            return True
        
        # 同部门允许
        dept_map = self._get_department_map()
        sender_dept = dept_map.get(sender)
        receiver_dept = dept_map.get(receiver)
        
        if sender_dept and receiver_dept and sender_dept == receiver_dept:
            return True
        
        # 跨部门只允许总监级（简化判断：含 _admin / _lead / _director）
        director_keywords = ["_admin", "_lead", "_director"]
        sender_is_director = any(kw in sender for kw in director_keywords)
        receiver_is_director = any(kw in receiver for kw in director_keywords)
        
        return sender_is_director and receiver_is_director
    
    def _get_channel(self, sender: str, receiver: str) -> str:
        """确定通信通道"""
        if sender == receiver:
            return "self"
        
        dept_map = self._get_department_map()
        if dept_map.get(sender) == dept_map.get(receiver):
            return "department_group"
        
        return "director_private_with_cc"
    
    def _get_retention_days(self, message: Dict[str, Any]) -> int:
        """获取消息留存天数"""
        msg_type = message.get("body", {}).get("type", "task")
        return self.RETENTION_DAYS.get(msg_type, 30)
    
    def _get_department_map(self) -> Dict[str, str]:
        """获取角色到部门的映射（从 Soul 文件动态读取）"""
        if self.config:
            return {
                role_id: self.config.get_role_soul(role_id).meta.get('department', 'central')
                for role_id in self.config.list_roles()
                if self.config.get_role_soul(role_id)
            }
        # 硬编码回退（仅用于无 config 的测试场景）
        return {"suri": "central"}
