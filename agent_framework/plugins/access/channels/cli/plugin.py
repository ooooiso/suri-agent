"""Plugin entry for CLI channel - PluginInterface wrapper for PluginManager loading.

CLI channel extends BaseChannel (not PluginInterface), so this wrapper
provides a minimal PluginInterface that can be loaded by PluginManager.
The actual CLI start/stop is managed by AccessPlugin.
"""
from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.plugins.access.channels.cli.channel import CLIChannelPlugin


class CLIPluginWrapper(PluginInterface):
    """CLI S„ PluginInterface Åh
    
     PluginManager ý }v¡ CLI S„}h
    žE„“eª¯1 CLIChannelPlugin ¡
    """

    def __init__(self):
        self._event_bus = None
        self._channel: CLIChannelPlugin = CLIChannelPlugin()

    async def init(self, event_bus, config: dict) -> None:
        self._event_bus = event_bus
        self._channel = CLIChannelPlugin(event_bus=event_bus)

    def register_events(self) -> None:
        pass

    async def start(self) -> None:
        # CLI channel will be properly started by AccessPlugin
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
    def channel(self) -> CLIChannelPlugin:
        return self._channel


__all__ = ["CLIPluginWrapper"]