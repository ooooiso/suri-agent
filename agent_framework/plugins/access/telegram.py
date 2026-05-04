"""Telegram 通道 — Bot 轮询模式。"""

import asyncio
from typing import Any, Dict, Optional

from agent_framework.shared.utils.event_types import Event, Priority

from .telegram_bot import TelegramBotAPI


class TelegramChannel:
    """Telegram Bot 通道。"""

    def __init__(self, event_bus, token: str):
        self._event_bus = event_bus
        try:
            token.encode("ascii")
        except UnicodeEncodeError:
            print("[Telegram] Token 包含非 ASCII 字符，跳过启动。")
            self._bot = None
            return
        self._bot = TelegramBotAPI(token)
        self._running = False
        self._offset = 0
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> bool:
        """启动 Telegram 轮询。"""
        if not self._bot:
            return False
        me = self._bot.get_me()
        if not me:
            print("[Telegram] Bot Token 无效，无法启动 Telegram 通道。")
            return False
        
        # 注册命令列表，用户输入 / 时客户端自动提示
        ok = self._bot.set_my_commands([
            {"command": "start", "description": "开始对话"},
            {"command": "status", "description": "查看系统状态"},
            {"command": "model", "description": "查看当前模型"},
            {"command": "reload", "description": "刷新配置"},
            {"command": "reconfig", "description": "配置管理"},
            {"command": "help", "description": "显示帮助"},
        ])
        if ok:
            print("[Telegram] 命令菜单已注册，输入 / 可查看命令列表。")
        else:
            print("[Telegram] 命令菜单注册失败，但 Bot 仍可正常使用。")
        
        print(f"[Telegram] Bot @{me.get('username')} 已连接。")
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        return True

    def stop(self) -> None:
        """停止轮询。"""
        self._running = False
        if self._task:
            self._task.cancel()

    async def _poll_loop(self) -> None:
        """轮询循环。"""
        while self._running:
            try:
                updates = self._bot.get_updates(offset=self._offset, limit=10)
                for update in updates:
                    self._offset = max(self._offset, update.get("update_id", 0) + 1)
                    await self._handle_update(update)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Telegram] Poll error: {e}")
                await asyncio.sleep(5)

    async def _handle_update(self, update: Dict[str, Any]) -> None:
        """处理单个更新。"""
        message = update.get("message")
        if not message:
            return
        
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "").strip()
        user = message.get("from", {})
        user_id = str(user.get("id", "unknown"))
        
        if not text:
            return
        
        # 命令处理
        if text.startswith("/"):
            await self._handle_command(chat_id, text, user_id)
            return
        
        # 普通消息 → user.input 事件
        await self._event_bus.publish(Event(
            event_type="user.input",
            source="access",
            payload={
                "user_id": user_id,
                "content": text,
                "channel": "telegram",
                "session_id": f"tg_{chat_id}",
            },
            priority=Priority.NORMAL,
        ))

    async def _handle_command(self, chat_id: int, text: str, user_id: str) -> None:
        """处理命令。"""
        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:]
        
        # 单独输入 "/" 给出命令列表
        if cmd == "/":
            self._bot.send_message(
                chat_id,
                "*可用命令*\n"
                "/start — 开始对话\n"
                "/status — 查看系统状态\n"
                "/model — 查看当前模型\n"
                "/reload — 刷新配置\n"
                "/reconfig — 配置管理\n"
                "/help — 显示帮助\n\n"
                "💡 直接发送消息即可与 Suri 对话\n"
                "切换模型：`llm.switch <厂商> [模型]`"
            )
            return

        if cmd == "/start":
            self._bot.send_message(
                chat_id,
                "👋 你好！我是 Suri，你的 AI 助手。\n\n"
                "直接发送消息即可对话。\n"
                "输入 / 查看所有命令。"
            )
        elif cmd == "/help":
            self._bot.send_message(
                chat_id,
                "*可用命令*\n"
                "/start — 开始对话\n"
                "/status — 查看系统状态\n"
                "/model — 查看当前模型\n"
                "/reload — 刷新配置\n"
                "/reconfig — 配置管理\n"
                "/help — 显示帮助\n\n"
                "切换模型：发送 `llm.switch <厂商> [模型]`\n"
                "例如：`llm.switch kimi` 或 `llm.switch deepseek deepseek-v4-flash`"
            )
        elif cmd == "/status":
            self._bot.send_message(chat_id, "✅ Suri 系统运行中。")
        elif cmd == "/model":
            await self._event_bus.publish(Event(
                event_type="user.command",
                source="access",
                payload={
                    "command": "llm.list",
                    "args": [],
                    "user_id": user_id,
                    "channel": "telegram",
                    "session_id": f"tg_{chat_id}",
                },
                priority=Priority.NORMAL,
            ))
        elif cmd == "/reload":
            await self._event_bus.publish(Event(
                event_type="user.command",
                source="access",
                payload={
                    "command": "reload",
                    "args": [],
                    "user_id": user_id,
                    "channel": "telegram",
                    "session_id": f"tg_{chat_id}",
                },
                priority=Priority.NORMAL,
            ))
        elif cmd == "/reconfig":
            await self._event_bus.publish(Event(
                event_type="user.command",
                source="access",
                payload={
                    "command": "reconfig",
                    "args": [],
                    "user_id": user_id,
                    "channel": "telegram",
                    "session_id": f"tg_{chat_id}",
                },
                priority=Priority.NORMAL,
            ))
        else:
            # 不认识的命令给出提示
            self._bot.send_message(
                chat_id,
                f"❓ 未知命令 `{cmd}`\n\n"
                "输入 / 查看所有可用命令。"
            )

    async def send_response(self, session_id: str, text: str) -> None:
        """发送响应到 Telegram。"""
        # 从 session_id 提取 chat_id
        if session_id.startswith("tg_"):
            try:
                chat_id = int(session_id.split("_", 1)[1])
                self._bot.send_message(chat_id, text)
            except (ValueError, IndexError):
                pass
