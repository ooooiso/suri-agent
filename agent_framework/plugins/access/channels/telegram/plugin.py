"""Plugin entry for Telegram channel - PluginInterface wrapper for PluginManager loading."""
from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.plugins.access.channels.telegram.channel import TelegramChannelPlugin


class TelegramPluginWrapper(PluginInterface):
    """Telegram 通道的 PluginInterface 包装器。"""

    def __init__(self):
        self._event_bus = None
        self._channel: TelegramChannelPlugin = TelegramChannelPlugin()

    async def init(self, event_bus, config: dict) -> None:
        self._event_bus = event_bus
        self._channel = TelegramChannelPlugin(event_bus=event_bus)

    def register_events(self) -> None:
        pass

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        self._channel.stop()

    async def resume(self) -> None:
        pass

    async def stop(self) -> None:
        self._channel.stop()

    async def cleanup(self) -> None:
        pass

    @property
    def channel(self) -> TelegramChannelPlugin:
        return self._channel


__all__ = ["TelegramPluginWrapper"]