"""security_service 插件 — 安全沙箱与权限管控（简化版）。"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


class SecurityServicePlugin(PluginInterface):
    """安全服务插件（迭代 1 简化版）。
    
    职责：
    - 文件路径白名单检查
    - 敏感配置保护
    - 为 code_tool 提供沙箱验证
    """

    # 读白名单（重构后：agent_framework/plugins/ + agent_framework/shared/）
    ALLOWED_READ_PATHS = [
        "agent_framework/", "roles/", "prd/",
        "tests/", ".suri/",
    ]
    
    # 写白名单
    ALLOWED_WRITE_PATHS = [
        "agent_framework/plugins/", "tests/", "roles/", "prd/",
    ]
    
    # 禁止路径
    FORBIDDEN_PATHS = [
        "~/.suri/config.json", "~/.suri/runtime/",
        "/etc/", "/usr/", "C:/",
    ]

    def __init__(self):
        self._event_bus = None
        self._project_root: Path = None

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        # 项目根目录（agent_framework/ 的父目录）
        self._project_root = Path(__file__).parent.parent.parent.parent

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

    def can_read(self, path: str) -> bool:
        """检查路径是否允许读取。"""
        return self._check_path(path, self.ALLOWED_READ_PATHS)

    def can_write(self, path: str) -> bool:
        """检查路径是否允许写入。"""
        # 禁止写入核心代码
        forbidden_writes = ["agent_framework/core/", "agent_framework/shared/interfaces/", "main.py"]
        for fp in forbidden_writes:
            if fp in path:
                return False
        return self._check_path(path, self.ALLOWED_WRITE_PATHS)

    def _check_path(self, path: str, allowed: List[str]) -> bool:
        """检查路径是否在允许列表内。"""
        # 解析为绝对路径
        try:
            target = Path(path).resolve()
        except Exception:
            return False
        
        # 检查是否在项目根目录下
        try:
            target.relative_to(self._project_root.resolve())
        except ValueError:
            # 不在项目根目录下，检查是否是 ~/.suri/ 下的允许路径
            home = Path.home()
            try:
                target.relative_to(home)
                # 检查禁止路径
                for forbidden in self.FORBIDDEN_PATHS:
                    forbidden_path = Path(forbidden).expanduser().resolve()
                    try:
                        target.relative_to(forbidden_path)
                        return False
                    except ValueError:
                        continue
                return True
            except ValueError:
                return False
        
        # 检查相对路径是否在允许列表
        rel_path = target.relative_to(self._project_root.resolve())
        rel_str = str(rel_path).replace("\\", "/")
        
        for allowed_path in allowed:
            if rel_str.startswith(allowed_path) or rel_str == allowed_path.rstrip("/"):
                return True
        
        return False

    async def _on_tool_call(self, event: Event) -> None:
        """拦截 tool.call 事件进行安全检查。
        
        检查通过后放行（重新发布原始事件让目标插件处理），
        检查不通过则发布 error.tool 事件并阻止调用。
        """
        tool_name = event.payload.get("tool_name", "")
        params = event.payload.get("params", {})
        
        if not tool_name.startswith("code_tool."):
            return  # 非 code_tool 调用，放行
        
        path = params.get("path", "")
        
        # 只读操作检查
        if tool_name in ("code_tool.read_file", "code_tool.list_dir", 
                         "code_tool.grep", "code_tool.stat_project"):
            if not self.can_read(path):
                await self._event_bus.publish(Event(
                    event_type="error.tool",
                    source="security_service",
                    target=event.source,
                    payload={
                        "tool_name": tool_name,
                        "error_code": 1101,
                        "error_message": f"Read access denied: {path}",
                        "retryable": False,
                        "request_id": event.payload.get("request_id"),
                    },
                    priority=Priority.HIGH,
                ))
                return  # 阻止调用
        
        # 写操作检查（迭代 2 启用）
        elif tool_name in ("code_tool.write_file", "code_tool.append_file"):
            if not self.can_write(path):
                await self._event_bus.publish(Event(
                    event_type="error.tool",
                    source="security_service",
                    target=event.source,
                    payload={
                        "tool_name": tool_name,
                        "error_code": 1102,
                        "error_message": f"Write access denied: {path}",
                        "retryable": False,
                        "request_id": event.payload.get("request_id"),
                    },
                    priority=Priority.HIGH,
                ))
                return  # 阻止调用
        
        # 安全检查通过，重新发布原始 tool.call 事件让目标插件（如 code_tool）处理
        # 使用相同的 event_type 和 payload，确保目标插件能正常接收
        await self._event_bus.publish(Event(
            event_type="tool.call",
            source=event.source,
            target="code_tool",
            payload=event.payload.copy(),
            priority=event.priority,
        ))