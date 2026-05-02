"""access 插件 — 终端 CLI 访问通道（迭代 1）。"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority


class AccessPlugin(PluginInterface):
    """访问通道插件。
    
    迭代 1：仅支持终端 CLI。
    迭代 2+：增加 Telegram Bot。
    """

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._running = False
        self._session_id: Optional[str] = None

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._config = config
        self._session_id = f"cli_{os.getpid()}"

    async def start(self) -> None:
        self._running = True
        # 启动 CLI 读循环
        asyncio.create_task(self._cli_loop())

    async def pause(self) -> None:
        self._running = False

    async def resume(self) -> None:
        self._running = True
        asyncio.create_task(self._cli_loop())

    async def stop(self) -> None:
        self._running = False

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        # 订阅响应事件
        self._event_bus.subscribe("llm.result", self._on_llm_result)
        self._event_bus.subscribe("error.tool", self._on_error)
        self._event_bus.subscribe("system.ready", self._on_system_ready)

    async def _cli_loop(self) -> None:
        """终端输入循环。"""
        loop = asyncio.get_event_loop()
        print("\n[Suri] CLI 模式已启动。输入 'help' 查看命令，'exit' 退出。\n")
        
        while self._running:
            try:
                line = await loop.run_in_executor(None, input, "> ")
                line = line.strip()
                
                if not line:
                    continue
                if line == "exit":
                    print("Goodbye.")
                    self._running = False
                    break
                if line == "help":
                    self._print_help()
                    continue
                
                # 解析命令
                parts = line.split()
                cmd = parts[0]
                args = parts[1:]
                
                await self._handle_command(cmd, args, line)
                
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nGoodbye.")
                break

    def _print_help(self) -> None:
        """打印帮助信息。"""
        help_text = """
可用命令：
  help                显示帮助
  exit                退出程序
  llm.list            列出所有 LLM 提供商
  llm.switch <p> [m]  切换 LLM 提供商/模型
  config.get [key]    查看配置
  config.set <k> <v>  设置配置
  tool <name> [...]   调用工具（如: tool code_tool.list_dir path=roles/）
  
对话模式：
  直接输入文字 → 发送给 LLM
"""
        print(help_text)

    async def _handle_command(self, cmd: str, args: List[str], raw: str) -> None:
        """处理 CLI 命令。"""
        # 内置命令
        if cmd in ("llm.list", "llm.switch", "config.get", "config.set"):
            await self._event_bus.publish(Event(
                event_type="user.command",
                source="access",
                payload={"command": cmd, "args": args, "session_id": self._session_id},
                priority=Priority.NORMAL,
            ))
            return
        
        # 工具调用
        if cmd == "tool" and len(args) >= 1:
            tool_name = args[0]
            # 解析参数 key=value
            params = {}
            for arg in args[1:]:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    params[k] = v
            
            await self._event_bus.publish(Event(
                event_type="tool.call",
                source="access",
                payload={"tool_name": tool_name, "params": params, "session_id": self._session_id},
                priority=Priority.NORMAL,
            ))
            return
        
        # 默认：作为对话消息发送给 LLM
        await self._event_bus.publish(Event(
            event_type="llm.call",
            source="access",
            payload={
                "messages": [
                    {"role": "system", "content": "You are Suri, an AI assistant."},
                    {"role": "user", "content": raw},
                ],
                "request_id": self._session_id,
            },
            priority=Priority.NORMAL,
        ))

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
