"""log_service 插件 — 分级日志服务。"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


class LogServicePlugin(PluginInterface):
    """日志服务插件。
    
    职责：
    - 记录分级日志
    - 按插件/类别分目录存储
    - 结构化 JSONL 格式
    """

    def __init__(self):
        self._event_bus = None
        self._log_base: Path = None

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        base = config.get("log_base", "~/.suri/runtime/logs/")
        self._log_base = Path(base).expanduser()
        self._log_base.mkdir(parents=True, exist_ok=True)

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
        # 订阅所有事件作为日志源
        self._event_bus.subscribe("*", self._on_event)

    def log(self, level: str, source: str, message: str, 
            extra: Dict[str, Any] = None) -> None:
        """记录日志。"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "source": source,
            "message": message,
        }
        if extra:
            entry["extra"] = extra
        
        # 按源分目录
        source_dir = self._log_base / source
        source_dir.mkdir(exist_ok=True)
        
        # 按日期分文件
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        log_file = source_dir / f"{date_str}.log"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    async def _on_event(self, event: Event) -> None:
        """记录所有事件。"""
        # 避免递归记录日志事件本身
        if event.event_type.startswith("log."):
            return
        
        self.log(
            level="INFO",
            source=event.source or "system",
            message=f"Event: {event.event_type}",
            extra={
                "event_type": event.event_type,
                "priority": event.priority.name,
                "payload_keys": list(event.payload.keys()) if event.payload else [],
            }
        )
