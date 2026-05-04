"""Web 通道插件 — PRD 严格对齐版

PRD 引用：
- prd/plugins/access/channel-capabilities.md — 能力矩阵
- prd/plugins/access/channels/web.md — Web 通道规范（§二 version = "0.0.0")

关键对齐点（按 PRD）：
- channel_type = "web"（PRD §二）
- version = "0.0.0"（PRD §二 明确要求）
- 全能力通道（PRD §二 能力清单）
- WebSocket 实时通信（PRD §三、四）
"""

import asyncio
from typing import Any, Dict, List, Optional

from agent_framework.plugins.access.session_hub import (
    ChannelCapabilities, SessionMessage, SessionOutput,
    SESSION_ACTIVE,
)
from agent_framework.plugins.access.base import BaseChannel
from agent_framework.shared.utils.event_types import Event, Priority


class WebChannelPlugin(BaseChannel):
    """Web 通道插件（PRD 对齐）。

    channel_type = "web"（PRD §二）。
    全能力通道：富文本、图片、视频、文件、流式输出、富 UI。
    """

    def __init__(self, event_bus=None, session_id: str = ""):
        super().__init__(event_bus, session_id)
        self._running = False
        self._session_id = session_id
        self._session_hub = None
        # {session_id: ws_connection}
        self._ws_connections: Dict[str, Any] = {}

    @property
    def channel_type(self) -> str:
        return "web"

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Web 通道能力矩阵 — PRD §二 全能力。"""
        return ChannelCapabilities(
            text=True, markdown=True, html=True, commands=True,
            # PRD §二 media: images/video/audio/files all true
            images=True, video=True, audio=True, files=True,
            # PRD §二: file_max_size_mb = 100
            file_max_size_mb=100,
            # PRD §二 interaction: buttons/forms true
            buttons=True, forms=True, sliders=True,
            # PRD §二 streaming: all true
            text_stream=True, file_stream=True,
            # PRD §二 ui: rich_ui/notifications/dynamic_content true
            rich_ui=True, notifications=True, dynamic_content=True,
            offline_mode=False, local_storage=False,
            # PRD §二 extras: all true
            clipboard=True, voice=True, location=True, identity=True,
        )

    async def start(self, session_hub=None) -> None:
        """启动 Web 通道并注册到 SessionHub。"""
        self._session_hub = session_hub
        self._running = True

        if session_hub:
            await session_hub.register_channel(
                name="channel.web",
                channel_type="web",
                capabilities=self.capabilities,
                handler=self,
                manifest={
                    # PRD §二: version = "0.0.0"
                    "version": "0.0.0",
                    "description": "Web 端交互通道",
                },
            )

    async def send(self, output: SessionOutput) -> None:
        """发送输出到 WebSocket 连接。"""
        ws = self._ws_connections.get(output.channel_type)
        if ws:
            import json
            await ws.send(json.dumps({
                "type": output.content_type,
                "content": output.content,
                "attachments": output.attachments,
                "streaming": output.streaming,
            }))

    async def send_message(self, content: str, msg_type: str = "text") -> None:
        """发送消息到所有 Web 连接。"""
        import json
        for ws in self._ws_connections.values():
            await ws.send(json.dumps({"type": msg_type, "content": content}))

    async def send_decision(self, decision_id: str, question: str,
                            options: List[str]) -> None:
        """发送决策菜单。"""
        import json
        payload = json.dumps({
            "type": "decision",
            "decision_id": decision_id,
            "question": question,
            "options": options,
        })
        for ws in self._ws_connections.values():
            await ws.send(payload)

    async def send_status(self, status: Dict[str, Any]) -> None:
        """发送状态信息。"""
        import json
        payload = json.dumps({"type": "status", "data": status})
        for ws in self._ws_connections.values():
            await ws.send(payload)

    def stop(self) -> None:
        self._running = False