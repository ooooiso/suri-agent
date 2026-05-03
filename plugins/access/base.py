"""通道基类 — 所有接入通道的抽象基类。

所有通道（CLI / Telegram / Web / 飞书）继承此类，共享：
- 事件发布接口
- 消息格式化
- 会话管理
- 错误去重
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseChannel(ABC):
    """接入通道基类。

    子类必须实现：
    - send_message() — 发送文本消息
    - send_decision() — 发送决策菜单
    - send_status() — 发送状态信息
    """

    def __init__(self, event_bus, session_id: str):
        self._event_bus = event_bus
        self._session_id = session_id

    @abstractmethod
    async def send_message(self, content: str, msg_type: str = "text") -> None:
        """发送消息到通道。"""
        ...

    @abstractmethod
    async def send_decision(self, decision_id: str, question: str,
                            options: List[str]) -> None:
        """发送决策菜单到通道。"""
        ...

    @abstractmethod
    async def send_status(self, status: Dict[str, Any]) -> None:
        """发送状态信息到通道。"""
        ...

    async def stop(self) -> None:
        """停止通道。"""
        pass
