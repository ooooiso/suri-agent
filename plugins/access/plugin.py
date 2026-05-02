"""access 插件 — 统一访问通道入口（迭代 1：CLI）。"""

import asyncio
from typing import Any, Dict, Optional

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority

from .cli import CLISession


class AccessPlugin(PluginInterface):
    """访问通道插件。

    迭代 1：仅支持终端 CLI。
    迭代 2+：增加 Telegram Bot、Web、Lark 等通道。
    """

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._cli: Optional[CLISession] = None

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config

    async def start(self) -> None:
        self._cli = CLISession(self._event_bus)
        asyncio.create_task(self._cli.run())

    async def pause(self) -> None:
        if self._cli:
            self._cli.stop()

    async def resume(self) -> None:
        if self._cli:
            asyncio.create_task(self._cli.run())

    async def stop(self) -> None:
        if self._cli:
            self._cli.stop()

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        self._event_bus.subscribe("llm.result", self._on_llm_result)
        self._event_bus.subscribe("error.tool", self._on_error)
        self._event_bus.subscribe("system.ready", self._on_system_ready)

    async def _on_llm_result(self, event: Event) -> None:
        """显示 LLM 响应。"""
        if event.payload.get("success"):
            content = event.payload.get("content", "")
            print(f"\n[Suri] {content}\n")
        else:
            error = event.payload.get("error_message", "Unknown error")
            print(f"\n[Error] {error}\n")

    async def _on_error(self, event: Event) -> None:
        """显示错误。"""
        error = event.payload.get("error_message", "Unknown error")
        print(f"\n[Error] {error}\n")

    async def _on_system_ready(self, event: Event) -> None:
        """系统就绪提示。"""
        print("[Suri] 系统已就绪，所有插件加载完成。")
