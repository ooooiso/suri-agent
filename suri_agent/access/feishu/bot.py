"""
飞书通信适配器（预留）

职责：
- 未来实现飞书机器人的连接与消息收发
- 继承 BaseCommAdapter，保持接口一致

原则：与 Telegram 适配器同级，可无缝切换。
"""

from typing import Dict, Any, Optional
from .base_comm import BaseCommAdapter, StandardMessage


class FeishuAdapter(BaseCommAdapter):
    """
    飞书适配器
    
    当前为预留实现，配置见 manifest/communication/feishu.md
    """
    
    async def connect(self) -> bool:
        """连接飞书"""
        # TODO: 实现飞书 Bot 连接
        print("[FeishuAdapter] 飞书适配器尚未实现")
        return False
    
    async def disconnect(self) -> None:
        """断开飞书连接"""
        pass
    
    async def send_to_user(self, user_id: str, message: StandardMessage) -> bool:
        """发送给用户"""
        return False
    
    async def send_to_role(self, role_id: str, message: StandardMessage) -> bool:
        """发送给角色"""
        return False
    
    async def send_to_group(self, group_id: str, message: StandardMessage) -> bool:
        """发送到群组"""
        return False
    
    def parse_incoming(self, raw_msg: Dict[str, Any]) -> Optional[StandardMessage]:
        """解析飞书消息"""
        return None
