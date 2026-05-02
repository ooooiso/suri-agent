"""PluginInterface — 所有插件必须实现的接口。"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class PluginInterface(ABC):
    """插件接口基类。
    
    所有插件的主类必须继承此接口，并实现所有抽象方法。
    """

    @abstractmethod
    async def init(self, event_bus: Any, config: Dict[str, Any]) -> None:
        """初始化插件。
        
        Args:
            event_bus: EventBus 实例，用于发布/订阅事件
            config: 插件配置字典
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """启动插件，标记为就绪状态。"""
        pass

    @abstractmethod
    async def pause(self) -> None:
        """暂停插件，停止处理新事件。"""
        pass

    @abstractmethod
    async def resume(self) -> None:
        """恢复插件。"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止插件。"""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源。"""
        pass

    def register_events(self) -> None:
        """注册事件订阅（可选重写）。"""
        pass
