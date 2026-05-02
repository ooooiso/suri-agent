"""access CLI 模块 — 终端交互逻辑。"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from shared.utils.event_types import Event, Priority


class CLISession:
    """终端 CLI 会话。"""

    def __init__(self, event_bus, session_id: Optional[str] = None):
        self._event_bus = event_bus
        self._session_id = session_id or f"cli_{os.getpid()}"
        self._running = False

    async def run(self) -> None:
        """启动终端输入循环。"""
        self._running = True
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

                await self._handle_input(line)

            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nGoodbye.")
                break

    def stop(self) -> None:
        self._running = False

    def _print_help(self) -> None:
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

    async def _handle_input(self, raw: str) -> None:
        """处理 CLI 输入。"""
        parts = raw.split()
        cmd = parts[0]
        args = parts[1:]

        # 内置命令路由
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
            params = {}
            for arg in args[1:]:
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    params[k] = v
            await self._event_bus.publish(Event(
                event_type="tool.call",
                source="access",
                payload={
                    "tool_name": tool_name,
                    "params": params,
                    "session_id": self._session_id,
                },
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
