"""config_service 插件 — 统一配置中心。"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from agent_framework.shared.interfaces.plugin import PluginInterface
from agent_framework.shared.utils.event_types import Event, Priority


class ConfigServicePlugin(PluginInterface):
    """配置服务插件。
    
    职责：
    - 加载/保存 ~/.suri/config.json
    - 热重载监听
    - 提供配置查询 API
    """

    def __init__(self):
        self._event_bus = None
        self._config: Dict[str, Any] = {}
        self._config_path: Path = None
        self._last_mtime: float = 0

    async def init(self, event_bus, config: Dict[str, Any]) -> None:
        self._event_bus = event_bus
        path = config.get("config_path", "~/.suri/config.json")
        self._config_path = Path(path).expanduser()
        self._load_config()

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
        self._event_bus.subscribe("user.command", self._on_command)
        self._event_bus.subscribe("system.config_changed", self._on_config_changed)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项。"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置项并保存。"""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save_config()

    def get_all(self) -> Dict[str, Any]:
        """获取全部配置。"""
        return self._config.copy()

    def _load_config(self) -> None:
        """从文件加载配置。"""
        if self._config_path.exists():
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                self._last_mtime = self._config_path.stat().st_mtime
            except Exception as e:
                print(f"[ConfigService] Failed to load config: {e}")
                self._config = {}
        else:
            self._config = {}

    def _save_config(self) -> None:
        """保存配置到文件。"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            self._last_mtime = self._config_path.stat().st_mtime
        except Exception as e:
            print(f"[ConfigService] Failed to save config: {e}")

    async def _on_command(self, event: Event) -> None:
        """处理命令。"""
        cmd = event.payload.get("command", "")
        args = event.payload.get("args", [])
        
        if cmd == "reload":
            self._load_config()
            await self._event_bus.publish(Event(
                event_type="system.config_changed",
                source="config_service",
                payload={"reason": "manual_reload"},
                priority=Priority.NORMAL,
            ))
        elif cmd == "config":
            key = args[0] if args else None
            if key:
                value = self.get(key, "<not set>")
                print(f"  {key} = {value}")
            else:
                import json
                print(json.dumps(self._config, indent=2, ensure_ascii=False))

    async def _on_config_changed(self, event: Event) -> None:
        """配置变更时重新加载。"""
        self._load_config()
