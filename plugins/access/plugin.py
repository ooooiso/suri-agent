"""access 插件 — 统一访问通道入口（迭代 1：CLI + Telegram）。"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority

from plugins.access.cli import CLISession
from plugins.access.telegram import TelegramChannel
from plugins.access.wizard import ConfigWizard
from plugins.access.config_editor import ConfigEditor
from plugins.access.formatter import MessageFormatter


class AccessPlugin(PluginInterface):
    """访问通道插件。

    迭代 1：终端 CLI + Telegram Bot + 首次运行配置向导。
    所有通道共享路由逻辑，按 session_id 分发。
    """

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._cli: Optional[CLISession] = None
        self._telegram: Optional[TelegramChannel] = None
        # 错误去重：session_id: (error_code, timestamp)
        self._last_error_map: Dict[str, tuple] = {}

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

    async def start(self) -> None:
        # 检查是否需要首次运行向导
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            wizard = ConfigWizard()
            new_config = wizard.run()
            if new_config:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(new_config, f, indent=2, ensure_ascii=False)
                # 发布配置变更事件
                await self._event_bus.publish(Event(
                    event_type="system.config_changed",
                    source="access",
                    payload={"reason": "first_run_wizard"},
                    priority=Priority.HIGH,
                ))
            else:
                print("\n[Suri] 配置未完成，使用默认配置启动。\n")

        # 启动 CLI
        self._cli = CLISession(self._event_bus)
        asyncio.create_task(self._cli.run())

        # 启动 Telegram（如配置启用）
        await self._start_telegram()

    async def _start_telegram(self) -> None:
        """根据配置启动 Telegram 通道。"""
        try:
            config_path = Path.home() / ".suri" / "config.json"
            if not config_path.exists():
                return
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            access_cfg = cfg.get("access", {})
            tg_cfg = access_cfg.get("channels", {}).get("telegram", {})
            if tg_cfg.get("enabled"):
                token = tg_cfg.get("bot_token", "")
                if token:
                    self._telegram = TelegramChannel(self._event_bus, token)
                    await self._telegram.start()
        except Exception as e:
            print(f"[Access] Telegram 启动失败: {e}")

    async def pause(self) -> None:
        if self._cli:
            self._cli.stop()
        if self._telegram:
            self._telegram.stop()

    async def resume(self) -> None:
        if self._cli:
            asyncio.create_task(self._cli.run())

    async def stop(self) -> None:
        if self._cli:
            self._cli.stop()
        if self._telegram:
            self._telegram.stop()

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        self._event_bus.subscribe("llm.response", self._on_llm_response)
        self._event_bus.subscribe("llm.error", self._on_llm_error)
        self._event_bus.subscribe("error.tool", self._on_error)
        self._event_bus.subscribe("system.ready", self._on_system_ready)
        self._event_bus.subscribe("user.command", self._on_user_command)

    async def _on_llm_response(self, event: Event) -> None:
        """显示 LLM 响应。同时标记 LLM 为在线状态。"""
        content = event.payload.get("content", "")
        session_id = event.payload.get("session_id", "")

        # LLM 响应成功 → 标记在线
        if self._cli:
            self._cli.set_llm_online(True)

        if session_id.startswith("tg_"):
            if self._telegram:
                await self._telegram.send_response(session_id, content)
        else:
            if content.strip() and self._cli:
                self._cli.print_output(MessageFormatter.format_response(content))

    async def _on_llm_error(self, event: Event) -> None:
        """显示 LLM 错误，附带可操作建议。

        同一 session 的同一错误码在 5 秒内只显示一次，避免重复刷屏。
        对 401/403/3002 等不可恢复错误，弹出交互式恢复菜单。
        同时标记 LLM 为离线状态，后续自然语言输入会提示使用 /xxx 命令。
        """
        import time
        error = event.payload.get("message", "Unknown error")
        error_code = event.payload.get("error_code", 0)
        provider = event.payload.get("provider", "")
        session_id = event.payload.get("session_id", "")

        # LLM 出错 → 标记离线
        if self._cli:
            self._cli.set_llm_online(False)

        # 去重检查
        now = time.time()
        last = self._last_error_map.get(session_id)
        if last and last[0] == error_code and now - last[1] < 5:
            return  # 5 秒内同一错误不重复显示
        self._last_error_map[session_id] = (error_code, now)

        # 使用 formatter 生成错误消息
        provider_name = provider or "当前厂商"
        formatted = MessageFormatter.format_error(error_code, error, provider_name)

        if session_id.startswith("tg_"):
            if self._telegram:
                await self._telegram.send_response(session_id, f"❌ {error}")
        else:
            if self._cli:
                self._cli.print_output(formatted)
                # 对不可恢复错误，弹出恢复菜单
                if error_code in (401, 403, 3002):
                    asyncio.create_task(
                        self._cli._show_recovery_menu(error_code, provider_name)
                    )

    async def _on_error(self, event: Event) -> None:
        """显示错误。"""
        error = event.payload.get("error_message", "Unknown error")
        if self._cli:
            self._cli.print_output(f"[Error] {error}")

    async def _on_system_ready(self, event: Event) -> None:
        """系统就绪提示。"""
        if self._cli:
            self._cli.print_system(MessageFormatter.format_system("系统已就绪。"))

    async def _on_user_command(self, event: Event) -> None:
        """处理 access 层需要响应的命令。"""
        cmd = event.payload.get("command", "")
        channel = event.payload.get("channel", "cli")
        session_id = event.payload.get("session_id", "")

        if cmd == "status":
            msg = MessageFormatter.format_system("系统运行中。输入 /help 查看命令。")
            self._send_response(msg, session_id, channel)
        elif cmd == "model":
            # /model → 转发为 /models 让 llm_gateway 显示厂商列表
            await self._event_bus.publish(Event(
                event_type="user.command",
                source="access",
                payload={
                    "command": "models", "args": [],
                    "channel": channel,
                    "user_id": event.payload.get("user_id", ""),
                    "session_id": session_id,
                },
                priority=Priority.NORMAL,
            ))
        elif cmd == "reload":
            msg = MessageFormatter.format_system("配置已重载。")
            self._send_response(msg, session_id, channel)
        elif cmd == "reconfig":
            asyncio.create_task(self._run_config_editor(session_id, channel))
        elif cmd == "logs":
            import os
            log_path = os.path.expanduser("~/.suri/runtime/logs")
            msg = MessageFormatter.format_system(f"日志目录: {log_path}")
            self._send_response(msg, session_id, channel)
        elif cmd == "clear":
            msg = MessageFormatter.format_system("会话上下文已清空。")
            self._send_response(msg, session_id, channel)

    async def _run_config_editor(self, session_id: str, channel: str) -> None:
        """运行配置编辑器。

        委托给 ConfigEditor 处理，access/plugin.py 只做事件路由。
        """
        config_path = Path.home() / ".suri" / "config.json"
        if not config_path.exists():
            self._send_response("[Suri] 无配置，下次启动进入向导。", session_id, channel)
            return

        # Telegram 模式下暂不支持交互式菜单
        if channel == "telegram":
            self._send_response(
                "配置编辑功能在 Telegram 中暂不支持交互式菜单，"
                "请使用 CLI 或直接编辑 ~/.suri/config.json。",
                session_id, channel,
            )
            return

        # CLI 通道使用 CLI 的异步输入
        if channel == "cli" and self._cli:
            editor = ConfigEditor(self._event_bus, input_func=self._cli._async_input)
        else:
            editor = ConfigEditor(self._event_bus)

        await editor.run_menu()

    def _send_response(self, msg: str, session_id: str, channel: str) -> None:
        """发送响应到对应通道。"""
        if channel == "telegram" and self._telegram:
            asyncio.create_task(self._telegram.send_response(session_id, msg))
        else:
            if self._cli:
                self._cli.print_output(msg)
            else:
                print(msg)
