"""
通信适配器抽象基类

职责：
- 定义通信服务的统一接口
- Telegram、飞书等具体适配器继承此类

原则：主程序通过基类与通信层交互，不依赖具体实现。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass


@dataclass
class StandardMessage:
    """内部标准消息格式"""
    message_id: str
    sender_role: str
    receiver_role: str
    timestamp: str
    priority: str
    task_ref: str
    body: Dict[str, Any]


class BaseCommAdapter(ABC):
    """
    通信适配器基类
    
    所有通信渠道（Telegram、飞书、Webhook 等）必须实现此接口。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._connected = False
        self._message_handler: Optional[Callable[[StandardMessage], None]] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """连接通信渠道"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        pass
    
    @abstractmethod
    async def send_to_user(self, user_id: str, message: StandardMessage) -> bool:
        """发送消息给用户"""
        pass
    
    @abstractmethod
    async def send_to_role(self, role_id: str, message: StandardMessage) -> bool:
        """发送消息给角色"""
        pass
    
    @abstractmethod
    async def send_to_group(self, group_id: str, message: StandardMessage) -> bool:
        """发送消息到群组"""
        pass
    
    @abstractmethod
    def parse_incoming(self, raw_msg: Dict[str, Any]) -> Optional[StandardMessage]:
        """将外部消息解析为标准格式"""
        pass
    
    def on_message(self, handler: Callable[[StandardMessage], None]) -> None:
        """注册消息处理器"""
        self._message_handler = handler
    
    @property
    def is_connected(self) -> bool:
        return self._connected
