"""事件类型定义。"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Priority(Enum):
    """事件优先级。"""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


@dataclass
class Event:
    """事件数据类。"""
    event_type: str
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    target: Optional[str] = None
    priority: Priority = Priority.NORMAL
    timestamp: Optional[str] = None
    request_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            from datetime import datetime, timezone
            self.timestamp = datetime.now(timezone.utc).isoformat()
