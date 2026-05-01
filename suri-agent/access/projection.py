"""
投影服务

职责：
- 将角色内部通信选择性同步到 Telegram 群组展示
- 同部门通信 → 投影到该部门群
- 跨部门通信 → 投影到双方部门群 + 中枢群
- 投影是单向展示，不是通信本身

原则：
- Telegram 不参与角色间通信路由，只接收投影
- 消息脱敏（隐藏 API Key 等敏感信息）

关联文档: suri-agent/access/telegram/telegram.md, development-plan/2.TELEGRAM_INTEGRATION_SPEC.md
"""

import re
from typing import Dict, Any, Optional
from access.base import StandardMessage


class ProjectionService:
    """通信投影服务"""
    
    def __init__(self, comm_service, config_service):
        self.comm = comm_service
        self.config = config_service
        self._group_map: Dict[str, str] = {}  # department_id -> telegram_group_id
        self._load_groups()
    
    def _load_groups(self) -> None:
        """从配置加载群组映射"""
        import yaml
        groups_path = self.config.project_root / 'suri-agent' / 'access' / 'telegram' / 'groups.yaml'
        if groups_path.exists():
            try:
                data = yaml.safe_load(groups_path.read_text(encoding='utf-8'))
                if data and 'groups' in data:
                    self._group_map = data['groups']
            except Exception:
                pass
    
    async def project_message(self, project_refs: list, sender: str, receiver: str, 
                               message: Dict[str, Any]) -> bool:
        """
        将消息投影到指定的 Telegram 群组
        
        Args:
            project_refs: 投影目标列表，如 ["tg:design", "tg:central"]
            sender: 发送者角色 ID
            receiver: 接收者角色 ID
            message: 消息体
        
        Returns:
            是否至少成功发送一条
        """
        if not self.comm or not self.comm.is_connected:
            return False
        
        body = message.get('body', {})
        content = body.get('content', '')
        msg_type = body.get('type', 'message')
        
        # 脱敏处理
        safe_content = self._sanitize(content)
        
        # 格式化投影消息
        projection_text = self._format_projection(sender, receiver, msg_type, safe_content)
        
        success_any = False
        for ref in project_refs:
            if not ref.startswith('tg:'):
                continue
            
            dept_id = ref.replace('tg:', '')
            group_id = self._group_map.get(dept_id)
            
            if not group_id:
                continue
            
            # 组装 StandardMessage
            proj_msg = StandardMessage(
                message_id=f"proj_{message.get('message_id', 'unknown')}",
                sender_role='suri-projection',
                receiver_role=group_id,
                timestamp=message.get('timestamp', ''),
                priority='normal',
                task_ref=message.get('task_ref', ''),
                body={'type': 'projection', 'content': projection_text}
            )
            
            try:
                result = await self.comm.send_to_group(group_id, proj_msg)
                if result:
                    success_any = True
            except Exception as e:
                print(f"[Projection] 投影到 {dept_id} 失败: {e}")
        
        return success_any
    
    def _format_projection(self, sender: str, receiver: str, msg_type: str, 
                           content: str) -> str:
        """格式化投影消息文本"""
        type_emoji = {
            'task': '📋',
            'approval': '✅',
            'notify': '🔔',
            'escalation': '⚠️',
        }
        emoji = type_emoji.get(msg_type, '💬')
        
        # 截断过长内容
        if len(content) > 800:
            content = content[:800] + "...（内容已截断）"
        
        lines = [
            f"{emoji} **{sender}** → **{receiver}**",
            f"",
            f"{content}",
        ]
        return "\n".join(lines)
    
    def _sanitize(self, text: str) -> str:
        """脱敏：隐藏敏感信息"""
        if not text:
            return text
        
        # 隐藏 API Key
        text = re.sub(r'sk-[a-zA-Z0-9]{20,}', '[API_KEY_HIDDEN]', text)
        # 隐藏密码
        text = re.sub(r'password[:=]\s*\S+', 'password=[HIDDEN]', text, flags=re.IGNORECASE)
        # 隐藏 token
        text = re.sub(r'token[:=]\s*\S+', 'token=[HIDDEN]', text, flags=re.IGNORECASE)
        # 隐藏私钥
        text = re.sub(r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----.*?-----END (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
                      '[PRIVATE_KEY_HIDDEN]', text, flags=re.DOTALL)
        
        return text
    
    def bind_group(self, dept_id: str, group_id: str) -> None:
        """绑定部门到 Telegram 群组"""
        self._group_map[dept_id] = group_id
        # TODO: 持久化到 suri-agent/access/telegram/groups.yaml
    
    def get_bound_groups(self) -> Dict[str, str]:
        """获取所有已绑定的群组"""
        return self._group_map.copy()
