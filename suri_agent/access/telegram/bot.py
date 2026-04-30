"""
通信服务

职责：
- 连接 Telegram Bot（未来可扩展飞书）
- 将外部消息标准化为内部格式
- 将内部消息发送到对应角色/群组

原则：通信适配器是主程序的一部分，但通信规则由外部配置驱动。
"""

import os
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from suri_agent.infrastructure.config import ConfigService


@dataclass
class StandardMessage:
    message_id: str
    sender_role: str
    receiver_role: str
    timestamp: str
    priority: str
    task_ref: str
    body: Dict[str, Any]


class CommService:
    """
    通信适配器
    
    当前实现 Telegram，预留飞书切换接口。
    所有收发消息均转换为 StandardMessage 内部格式。
    """
    
    def __init__(self, config: ConfigService):
        self.config = config
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.username = os.getenv('TELEGRAM_BOT_USERNAME', '')
        self.central_group = os.getenv('TELEGRAM_CENTRAL_GROUP_ID', '')
        self._message_handler: Optional[Callable] = None
        self._connected = False
    
    async def connect(self) -> bool:
        """连接 Telegram Bot"""
        if not self.bot_token:
            print("[CommService] 错误: 未设置 TELEGRAM_BOT_TOKEN")
            return False
        
        # TODO: 使用 python-telegram-bot 或 aiogram 连接
        print(f"[CommService] 正在连接 Telegram Bot {self.username}...")
        self._connected = True
        return True
    
    def on_message(self, handler: Callable[[StandardMessage], None]) -> None:
        """注册消息处理器"""
        self._message_handler = handler
    
    async def send_to_role(self, role_id: str, message: StandardMessage) -> bool:
        """
        发送消息给指定角色
        
        解析 roles_mapping.md 获取 Telegram 账号，私聊发送。
        """
        # TODO: 实现 Telegram 私聊发送
        print(f"[CommService] 发送给 {role_id}: {message.body.get('content', '')[:100]}")
        return True
    
    async def send_to_group(self, group_id: str, message: StandardMessage) -> bool:
        """发送消息到群组"""
        # TODO: 实现 Telegram 群组发送
        print(f"[CommService] 发送到群组 {group_id}: {message.body.get('content', '')[:100]}")
        return True
    
    async def broadcast(self, message: StandardMessage) -> bool:
        """广播到中台调度群"""
        return await self.send_to_group(self.central_group, message)
    
    def parse_incoming(self, raw_msg: Dict[str, Any]) -> Optional[StandardMessage]:
        """
        将 Telegram 消息解析为标准格式
        
        Args:
            raw_msg: Telegram 原始消息对象
            
        Returns:
            StandardMessage 或 None
        """
        # TODO: 实现 Telegram 消息解析
        # 当前为占位实现
        return StandardMessage(
            message_id=raw_msg.get('message_id', 'unknown'),
            sender_role=raw_msg.get('from_user', 'user'),
            receiver_role='suri',
            timestamp=raw_msg.get('date', ''),
            priority='normal',
            task_ref='',
            body={'type': 'message', 'content': raw_msg.get('text', '')}
        )
    
    def resolve_role_chat_id(self, role_id: str) -> Optional[str]:
        """
        从 roles_mapping.md 解析角色的 Telegram 聊天 ID
        """
        # TODO: 实现角色到 Telegram ID 的映射
        return None
    
    def get_group_id(self, department_id: str) -> Optional[str]:
        """
        从 function_index.md 获取部门群组 ID
        """
        entry = self.config.get_function_index()
        if entry and 'departments' in entry.meta:
            for dept in entry.meta['departments']:
                if dept.get('id') == department_id:
                    return dept.get('group_chat')
        return None
