"""code_tool 插件 — 代码操作工具入口（迭代 1：只读）。"""

from pathlib import Path
from typing import Any, Dict

from shared.interfaces.plugin import PluginInterface
from shared.utils.event_types import Event, Priority

from .reader import read_file
from .explorer import list_dir
from .search import grep
from .stats import stat_project


class CodeToolPlugin(PluginInterface):
    """代码工具插件（迭代 1 只读版）。

    支持的操作：
    - read_file: 读取文件内容
    - list_dir: 列出目录内容
    - grep: 在文件中搜索文本
    - stat_project: 统计项目信息
    """

    def __init__(self):
        self._event_bus = None
        self._project_root: Path = None

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        self._project_root = Path(__file__).parent.parent.parent

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def register_events(self) -> None:
        self._event_bus.subscribe("tool.call", self._on_tool_call)

    async def _on_tool_call(self, event: Event) -> None:
        """处理 tool.call 事件。"""
        tool_name = event.payload.get("tool_name", "")
        params = event.payload.get("params", {})
        result = None

        if tool_name == "code_tool.read_file":
            result = read_file(
                self._project_root,
                params.get("path", ""),
                int(params.get("offset", 0)),
                int(params.get("limit", 100)),
            )
        elif tool_name == "code_tool.list_dir":
            result = list_dir(self._project_root, params.get("path", "."))
        elif tool_name == "code_tool.grep":
            result = grep(
                self._project_root,
                params.get("pattern", ""),
                params.get("path", "."),
                params.get("glob", "*"),
            )
        elif tool_name == "code_tool.stat_project":
            result = stat_project(self._project_root, params.get("path", "."))
        else:
            return

        await self._event_bus.publish(Event(
            event_type="tool.result",
            source="code_tool",
            target=event.source,
            payload={
                "tool_name": tool_name,
                "result": result,
                "request_id": event.payload.get("request_id"),
            },
            priority=Priority.NORMAL,
        ))
