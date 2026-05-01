"""
通信服务

职责：
- 连接 Telegram Bot（未来可扩展飞书）
- 将外部消息标准化为内部格式
- 将内部消息发送到对应角色/群组

原则：通信适配器是主程序的一部分，但通信规则由外部配置驱动。

关联文档: suri-agent/access/telegram/telegram.md, suri-agent/access/telegram/groups.yaml, development-plan/2.TELEGRAM_INTEGRATION_SPEC.md
"""

import os
import asyncio
from typing import Dict, Any, Optional, Callable
from infrastructure.config import ConfigService
from access.base import StandardMessage


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
        self._message_handler: Optional[Callable[[StandardMessage], None]] = None
        self._connected = False
        self._application = None  # python-telegram-bot Application 实例
    
    async def connect(self) -> bool:
        """连接 Telegram Bot"""
        if not self.bot_token:
            print("[CommService] 错误: 未设置 TELEGRAM_BOT_TOKEN")
            return False
        
        try:
            from telegram.ext import Application
            
            print(f"[CommService] 正在连接 Telegram Bot {self.username}...")
            self._application = Application.builder().token(self.bot_token).build()
            
            # 注册消息处理器
            from telegram.ext import MessageHandler, filters
            self._application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_telegram_message)
            )
            self._application.add_handler(
                MessageHandler(filters.COMMAND, self._on_telegram_command)
            )
            
            # 启动 bot（不阻塞）
            await self._application.initialize()
            await self._application.start_polling()
            await self._application.updater.start_polling()
            
            self._connected = True
            print(f"[CommService] Telegram Bot 已上线: @{self.username}")
            return True
            
        except ImportError:
            print("[CommService] 警告: python-telegram-bot 未安装，将以离线模式运行")
            print("          安装: pip install 'python-telegram-bot>=20.0'")
            self._connected = False
            return False
        except Exception as e:
            print(f"[CommService] Telegram 连接失败: {e}")
            self._connected = False
            return False
    
    async def disconnect(self) -> None:
        """断开 Telegram 连接"""
        if self._application:
            try:
                await self._application.stop()
                await self._application.shutdown()
            except Exception as e:
                print(f"[CommService] 断开连接时出错: {e}")
        self._connected = False
    
    def on_message(self, handler: Callable[[StandardMessage], None]) -> None:
        """注册消息处理器"""
        self._message_handler = handler
    
    async def send_to_role(self, role_id: str, message: StandardMessage) -> bool:
        """
        发送消息给指定角色
        
        解析 roles_mapping.md 获取 Telegram 账号，私聊发送。
        """
        chat_id = self.resolve_role_chat_id(role_id)
        if not chat_id:
            print(f"[CommService] 无法解析 {role_id} 的聊天 ID")
            return False
        
        return await self._send_message(chat_id, message)
    
    async def send_to_group(self, group_id: str, message: StandardMessage) -> bool:
        """发送消息到群组"""
        return await self._send_message(group_id, message)
    
    async def broadcast(self, message: StandardMessage) -> bool:
        """广播到中台调度群"""
        return await self.send_to_group(self.central_group, message)
    
    async def _send_message(self, chat_id: str, message: StandardMessage) -> bool:
        """底层发送消息到 Telegram"""
        if not self._connected or not self._application:
            print(f"[CommService] 未连接，无法发送消息到 {chat_id}")
            return False
        
        try:
            from telegram import Bot
            bot = Bot(token=self.bot_token)
            
            content = message.body.get('content', '')
            # Markdown 格式支持
            await bot.send_message(
                chat_id=chat_id,
                text=content[:4096],  # Telegram 单条消息限制
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return True
        except Exception as e:
            print(f"[CommService] 发送消息失败: {e}")
            return False
    
    async def _on_telegram_message(self, update, context) -> None:
        """处理收到的 Telegram 普通消息"""
        if not update.message or not update.message.text:
            return
        
        # 忽略群聊中非 @bot 的消息
        if update.message.chat.type in ['group', 'supergroup']:
            if not update.message.text.startswith(f'@{self.username}'):
                # 检查是否 @bot
                if f'@{self.username}' not in update.message.text:
                    return
        
        raw_msg = {
            'message_id': str(update.message.message_id),
            'from_user': str(update.message.from_user.id),
            'chat_id': str(update.message.chat_id),
            'text': update.message.text.replace(f'@{self.username}', '').strip(),
            'date': str(update.message.date),
            'is_group': update.message.chat.type in ['group', 'supergroup'],
        }
        
        msg = self.parse_incoming(raw_msg)
        if msg and self._message_handler:
            # 在后台处理，不阻塞 bot
            asyncio.create_task(self._async_handle(msg))
    
    async def _on_telegram_command(self, update, context) -> None:
        """处理收到的 Telegram 命令"""
        if not update.message or not update.message.text:
            return
        
        # 命令处理由外部 CommandHandler 完成
        # 这里只做基础解析，将命令作为消息传递给主程序
        raw_msg = {
            'message_id': str(update.message.message_id),
            'from_user': str(update.message.from_user.id),
            'chat_id': str(update.message.chat_id),
            'text': update.message.text,
            'date': str(update.message.date),
            'is_group': update.message.chat.type in ['group', 'supergroup'],
            'is_command': True,
        }
        
        msg = self.parse_incoming(raw_msg)
        if msg and self._message_handler:
            asyncio.create_task(self._async_handle(msg))
    
    async def _async_handle(self, msg: StandardMessage) -> None:
        """异步调用消息处理器"""
        try:
            if asyncio.iscoroutinefunction(self._message_handler):
                await self._message_handler(msg)
            else:
                self._message_handler(msg)
        except Exception as e:
            print(f"[CommService] 消息处理出错: {e}")
    
    def parse_incoming(self, raw_msg: Dict[str, Any]) -> Optional[StandardMessage]:
        """
        将 Telegram 消息解析为标准格式
        
        Args:
            raw_msg: Telegram 原始消息对象
            
        Returns:
            StandardMessage 或 None
        """
        text = raw_msg.get('text', '')
        user_id = raw_msg.get('from_user', 'user')
        
        # 私聊 → 直接发给 suri
        # 群组 → 同样发给 suri（suri 负责调度）
        return StandardMessage(
            message_id=raw_msg.get('message_id', 'unknown'),
            sender_role=user_id,
            receiver_role='suri',
            timestamp=raw_msg.get('date', ''),
            priority='normal',
            task_ref='',
            body={
                'type': 'message',
                'content': text,
                'source': 'telegram',
                'chat_id': raw_msg.get('chat_id', ''),
                'is_group': raw_msg.get('is_group', False),
                'is_command': raw_msg.get('is_command', False),
            }
        )
    
    def resolve_role_chat_id(self, role_id: str) -> Optional[str]:
        """
        从 roles_mapping.md 解析角色的 Telegram 聊天 ID
        
        TODO: 实现从 group/<role>/reference/roles_mapping.md 读取
        """
        # 临时方案：从环境变量查找
        env_key = f"TG_CHAT_{role_id.upper().replace('-', '_')}"
        chat_id = os.getenv(env_key, '')
        if chat_id:
            return chat_id
        return None
    
    @property
    def is_connected(self) -> bool:
        return self._connected
